import chess
from zobrist import *
from openings import polyglot_move
from gestion_memoire import *
import time

EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2

def extract_features(board):
    features = {
        "material": 0,
        "psqt": 0,
        "mobility": 0
    }

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue

        sign = 1 if piece.color == chess.WHITE else -1

        features["material"] += sign * VALEURS_PIECES[piece.piece_type]
        features["psqt"] += sign * get_position_value(
            piece.piece_type, square, piece.color
        )

    mobility = len(list(board.legal_moves))
    features["mobility"] = mobility if board.turn == chess.WHITE else -mobility

    return features

def learn_from_position(board, result, coup=None, lr=0.00001):
    features = extract_features(board)
    prediction = evaluate(board)

    error = result - prediction

    # Mise à jour des poids
    for k in WEIGHTS:
        WEIGHTS[k] += lr * error * features[k]

    # Si le coup est important, on ajuste plus fortement les poids
    if coup and est_coup_important(board, coup):
        for k in WEIGHTS:
            WEIGHTS[k] += lr * error * features[k] * 2  # Double ajustement pour les coups importants

    save_memoire()

def get_position_value(piece_type, square, color):
    table = TABLES[piece_type]
    return table[square ^ 56] if color == chess.WHITE else table[square]


def evaluate(board):
    """Score du point de vue du joueur EN TRAIT (negamax)."""
    if board.is_checkmate():
        return -100000
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue
        value = VALEURS_PIECES[piece.piece_type] + get_position_value(piece.piece_type, square, piece.color)
        if piece.color == board.turn:
            score += value
        else:
            score -= value

    return score


def mvv_lva(board, move):
    """Most Valuable Victim - Least Valuable Attacker."""
    if not board.is_capture(move):
        return 0
    victim = board.piece_at(move.to_square)
    attacker = board.piece_at(move.from_square)
    v = VALEURS_PIECES[victim.piece_type] if victim else 100
    a = VALEURS_PIECES[attacker.piece_type] if attacker else 100
    return 10 * v - a


def quiescence(board, alpha, beta, max_depth=5):
    """Quiescence search avec MVV-LVA."""
    stand_pat = evaluate(board)

    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat
    if max_depth == 0:
        return alpha

    captures = sorted(
        (m for m in board.legal_moves if board.is_capture(m)),
        key=lambda m: mvv_lva(board, m),
        reverse=True
    )

    for move in captures:
        board.push(move)
        score = -quiescence(board, -beta, -alpha, max_depth - 1)
        board.pop()

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha


def alpha_beta(TT, board, depth, alpha, beta,
               ZP, ZR, ZE, ZT, IP, cle,
               killers, history, null_allowed=True):
    """Alpha-Beta negamax avec hash incrémental, NMP, Killers, History."""

    if board.is_game_over():
        return evaluate(board)

    if cle in TT:
        entry = TT[cle]
        if entry["profondeur"] >= depth:
            if entry["flag"] == EXACT:
                return entry["score"]
            elif entry["flag"] == LOWERBOUND:
                alpha = max(alpha, entry["score"])
            elif entry["flag"] == UPPERBOUND:
                beta = min(beta, entry["score"])
            if alpha >= beta:
                return entry["score"]

    if depth == 0:
        return quiescence(board, alpha, beta)

    # Null Move Pruning
    R = 2
    if (null_allowed
            and depth >= R + 1
            and not board.is_check()
            and any(board.pieces(pt, board.turn)
                    for pt in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN])):
        null_cle = cle ^ ZT
        board.push(chess.Move.null())
        null_score = -alpha_beta(TT, board, depth - R - 1, -beta, -beta + 1,
                                 ZP, ZR, ZE, ZT, IP, null_cle,
                                 killers, history, null_allowed=False)
        board.pop()
        if null_score >= beta:
            return beta

    best_score = -float('inf')
    original_alpha = alpha

    def move_priority(m):
        s = mvv_lva(board, m)
        if board.is_capture(m):
            s += 5000
        if m.promotion:
            s += VALEURS_PIECES.get(m.promotion, 0) + 4000
        if m in killers[depth]:
            s += 2000
        s += history.get((board.turn, m.from_square, m.to_square), 0)
        return s

    moves = sorted(board.legal_moves, key=move_priority, reverse=True)

    for move in moves:
        new_cle = update_cle(board, cle, move, ZP, ZR, ZE, ZT, IP)
        board.push(move)
        score = -alpha_beta(TT, board, depth - 1, -beta, -alpha,
                            ZP, ZR, ZE, ZT, IP, new_cle,
                            killers, history)
        board.pop()

        if score > best_score:
            best_score = score

        if score > alpha:
            alpha = score
            if not board.is_capture(move):
                key = (board.turn, move.from_square, move.to_square)
                history[key] = history.get(key, 0) + depth * depth

        if alpha >= beta:
            if not board.is_capture(move):
                killers[depth].add(move)
                if len(killers[depth]) > 2:
                    killers[depth].pop()
            break

    flag = EXACT
    if best_score <= original_alpha:
        flag = UPPERBOUND
    elif best_score >= beta:
        flag = LOWERBOUND

    TT[cle] = {"score": best_score, "profondeur": depth, "flag": flag}
    return best_score


def _recherche_complete(board, depth, root_cle, TT, ZP, ZR, ZE, ZT, IP, killers, history, best_first=None):
    """Recherche avec fenêtre infinie, best_first joué en premier."""
    best_move  = None
    best_score = -float('inf')

    def priority(m):
        if m == best_first:
            return float('inf')
        s = mvv_lva(board, m)
        if board.is_capture(m): s += 5000
        if m.promotion:         s += 4000
        return s

    for move in sorted(board.legal_moves, key=priority, reverse=True):
        new_cle = update_cle(board, root_cle, move, ZP, ZR, ZE, ZT, IP)
        board.push(move)
        score = -alpha_beta(TT, board, depth - 1,
                            -float('inf'), float('inf'),
                            ZP, ZR, ZE, ZT, IP, new_cle, killers, history)
        board.pop()
        if score > best_score:
            best_score = score
            best_move  = move

    return best_move, best_score


def ia_move(TT, board, depth, ZP, ZR, ZE, ZT, IP):
    """
    Iterative Deepening + Aspiration Windows.
    Hash Zobrist incrémental — calculé une seule fois à la racine.
    best_move ne peut jamais être None à la fin.
    """
    # Livre d'ouverture
    book_move = polyglot_move(board)
    if book_move is not None:
        print(f"  📖 Coup de livre : {board.san(book_move)}")
        return book_move

    killers  = [set() for _ in range(depth + 2)]
    history  = {}
    root_cle = hash_zobrist(board, ZP, ZR, ZE, ZT, IP)

    # Initialisation : coup légal par défaut pour garantir qu'on retourne toujours quelque chose
    best_move  = next(iter(board.legal_moves))
    prev_score = 0
    WINDOW     = 50

    for current_depth in range(1, depth+1):

        if current_depth >= 3:
            # Essai avec aspiration window
            alpha = prev_score - WINDOW
            beta  = prev_score + WINDOW

            def priority_root(m):
                if m == best_move: return float('inf')
                s = mvv_lva(board, m)
                if board.is_capture(m): s += 5000
                if m.promotion:         s += 4000
                return s

            iter_best  = None
            iter_score = -float('inf')
            fail       = False

            for move in sorted(board.legal_moves, key=priority_root, reverse=True):
                new_cle = update_cle(board, root_cle, move, ZP, ZR, ZE, ZT, IP)
                board.push(move)
                score = -alpha_beta(TT, board, current_depth - 1, -beta, -alpha,
                                    ZP, ZR, ZE, ZT, IP, new_cle, killers, history)
                board.pop()

                if score > iter_score:
                    iter_score = score
                    iter_best  = move

                if score > alpha:
                    alpha = score
                if alpha >= beta:
                    fail = True
                    break

            # Si on sort de la fenêtre → recherche complète
            if fail or iter_best is None or abs(iter_score - prev_score) > WINDOW:
                iter_best, iter_score = _recherche_complete(
                    board, current_depth, root_cle,
                    TT, ZP, ZR, ZE, ZT, IP, killers, history,
                    best_first=best_move
                )
        else:
            # Profondeurs 1 et 2 : fenêtre infinie directement
            iter_best, iter_score = _recherche_complete(
                board, current_depth, root_cle,
                TT, ZP, ZR, ZE, ZT, IP, killers, history,
                best_first=best_move
            )

        # On ne met à jour que si on a vraiment trouvé un coup
        if iter_best is not None:
            best_move  = iter_best
            prev_score = iter_score

        print(f"  🔍 Profondeur {current_depth} → {board.san(best_move)} (score: {prev_score})")

    return best_move

def est_coup_important(board, move):
    # Retourne True si le coup est considéré comme important
    if board.is_capture(move):
        return True
    if move.promotion:
        return True
    if board.gives_check(move):
        return True
    if board.is_checkmate():
        return True
    return False

def ia_move_with_timer(TT, board, depth, ZP, ZR, ZE, ZT, IP, max_time=0.5):
    start_time = time.time()
    move = ia_move(TT, board, depth, ZP, ZR, ZE, ZT, IP)
    elapsed = time.time() - start_time

    if elapsed > max_time:
        # Enregistrer la position et le coup dans coups.json
        save_coup_to_json(board, move)

    return move

def save_coup_to_json(board, move):
    position = {
        "fen": board.fen(),
        "move": move.uci(),
    }

    try:
        with open("coups.json", "r") as f:
            coups = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        coups = []

    coups.append(position)

    with open("coups.json", "w") as f:
        json.dump(coups, f, indent=4)
