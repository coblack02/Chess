from zobrist import *
from openings import polyglot_move
from gestion_memoire import *
import random

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

def learn_from_position(board, result, lr=0.00001):
    features = extract_features(board)
    prediction = evaluate(board)

    error = result - prediction

    for k in WEIGHTS:
        WEIGHTS[k] += lr * error * features[k]

def get_position_value(piece_type, square, color):
    """
    Retourne la valeur positionnelle d'une pièce.
    - Pour les BLANCS : on miroir verticalement (square ^ 56) car nos tables
      sont écrites rang8→rang1 mais chess.SQUARES a rang1 en bas.
    - Pour les NOIRS  : on utilise square directement (le miroir annule).
    """
    table = TABLES[piece_type]
    if color == chess.WHITE:
        return table[square ^ 56]
    else:
        return table[square]


def evaluate(board):
    """
    Fonction d'évaluation avec tables de positions correctement orientées.
    Retourne un score du point de vue des BLANCS.
    """
    if board.is_checkmate():
        return -100000 if board.turn == chess.WHITE else 100000
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0

    features = extract_features(board)

    score = 0
    for name, value in features.items():
        score += WEIGHTS[name] * value

    return score


def quiescence(board, alpha, beta, max_depth=4):
    """Recherche de quiescence pour éviter l'effet horizon"""
    stand_pat = evaluate(board)

    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat

    if max_depth == 0:
        return alpha

    for move in board.legal_moves:
        if not board.is_capture(move):
            continue

        board.push(move)
        score = -quiescence(board, -beta, -alpha, max_depth - 1)
        board.pop()

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha


def alpha_beta(TT, board, depth, alpha, beta, ZP, ZR, ZE, ZT, IP):
    """Alpha-Beta avec table de transposition"""

    if board.is_game_over():
        return evaluate(board)

    cle = hash_zobrist(board, ZP, ZR, ZE, ZT, IP)

    # Vérifier la TT
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

    best_score = -float('inf')
    original_alpha = alpha

    # Tri des coups : captures > échecs > promotions > reste
    moves = sorted(
        board.legal_moves,
        key=lambda m: (
            board.is_capture(m),
            board.gives_check(m),
            m.promotion is not None
        ),
        reverse=True
    )

    for move in moves:
        board.push(move)
        score = -alpha_beta(TT, board, depth - 1, -beta, -alpha, ZP, ZR, ZE, ZT, IP)
        board.pop()

        if score > best_score:
            best_score = score

        alpha = max(alpha, score)
        if alpha >= beta:
            break

    # Stocker dans TT
    flag = EXACT
    if best_score <= original_alpha:
        flag = UPPERBOUND
    elif best_score >= beta:
        flag = LOWERBOUND

    TT[cle] = {
        "score": best_score,
        "profondeur": depth,
        "flag": flag
    }

    return best_score


def ia_move(TT, board, depth, ZP, ZR, ZE, ZT, IP):
    """
    Trouve le meilleur coup à jouer.
    Utilise d'abord openings.py (polyglot_move) pour le livre d'ouverture,
    puis bascule sur alpha-beta si aucun coup de livre n'est disponible.
    """
    # --- Livre d'ouverture via openings.py ---
    book_move = polyglot_move(board)
    if book_move is not None:
        print(f"   Coup de livre : {board.san(book_move)}")
        return book_move

    # --- Recherche alpha-beta ---
    best_move = None
    best_score = -float('inf')

    moves = sorted(
        board.legal_moves,
        key=lambda m: (
            board.is_capture(m),
            board.gives_check(m),
            m.promotion is not None
        ),
        reverse=True
    )

    for move_candidate in moves:
        board.push(move_candidate)
        score = -alpha_beta(TT, board, depth - 1, -float('inf'), float('inf'), ZP, ZR, ZE, ZT, IP)
        board.pop()

        if score > best_score:
            best_score = score
            best_move = move_candidate

    return best_move
