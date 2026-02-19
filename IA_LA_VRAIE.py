import chess
from zobrist import *
from openings import polyglot_move
import random

EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2

VALEURS_PIECES = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 20000
}

# ============================================================
# TABLES DE POSITIONS
# Écrites du point de vue des BLANCS (rang 8 en haut, rang 1 en bas)
# chess.SQUARES : A1=0 ... H8=63 (rang 1 en bas)
# Pour accéder correctement : square ^ 56  pour les blancs
#                              square       pour les noirs (déjà miroir)
# ============================================================

TABLE_PION = [
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    15, 15, 25, 35, 35, 25, 15, 15,
    15, 15, 20, 35, 35, 20, 15, 15,
    15, 15, 20, 25, 25, 20, 15, 15,
    10, 10,  5,  5,  5,  5, 10, 10,
   -37,-37,-47,-75,-75,-47,-37,-37,
     0,  0,  0,  0,  0,  0,  0,  0
]

TABLE_CAVALIER = [
    -60,-50,-40,-40,-40,-40,-50,-60,
    -50,-30,-10,-10,-10,-10,-30,-50,
    -40,-10,  0,  5,  5,  0,-10,-40,
    -40, -5,  5, 10, 10,  5, -5,-40,
    -40, -5,  5, 10, 10,  5, -5,-40,
    -40,-10,  0,  5,  5,  0,-10,-40,
    -50,-30,-10,-10,-10,-10,-30,-50,
    -60,-50,-40,-40,-40,-40,-50,-60
]

TABLE_FOU = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,  10,  10,   5,   0, -10,
    -10,   5,   5,  10,  10,   5,   5, -10,
    -10,   0,  10,  10,  10,  10,   0, -10,
    -10,  10,  10,  10,  10,  10,  10, -10,
    -10,   5,   0,   0,   0,   0,   5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20
]

TABLE_TOUR = [
      0,   0,   0,   0,   0,   0,   0,   0,
      5,  10,  10,  10,  10,  10,  10,   5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
     -5,   0,   0,   0,   0,   0,   0,  -5,
      0,   0,   0,   5,   5,   0,   0,   0
]

TABLE_DAME = [
    -20, -10, -10,  -5,  -5, -10, -10, -20,
    -10,   0,   0,   0,   0,   0,   0, -10,
    -10,   0,   5,   5,   5,   5,   0, -10,
     -5,   0,   5,   5,   5,   5,   0,  -5,
      0,   0,   5,   5,   5,   5,   0,  -5,
    -10,   5,   5,   5,   5,   5,   0, -10,
    -10,   0,   5,   0,   0,   0,   0, -10,
    -20, -10, -10,  -5,  -5, -10, -10, -20
]

TABLE_ROI = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
     20,  20,   0,   0,   0,   0,  20,  20,
     20,  30,  10,   0,   0,  10,  30,  20
]

TABLES = {
    chess.PAWN:   TABLE_PION,
    chess.KNIGHT: TABLE_CAVALIER,
    chess.BISHOP: TABLE_FOU,
    chess.ROOK:   TABLE_TOUR,
    chess.QUEEN:  TABLE_DAME,
    chess.KING:   TABLE_ROI,
}

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

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue

        value = VALEURS_PIECES[piece.piece_type] + get_position_value(piece.piece_type, square, piece.color)

        if piece.color == chess.WHITE:
            score += value
        else:
            score -= value

    # Bonus mobilité (léger)
    mobility = len(list(board.legal_moves)) * 5
    if board.turn == chess.WHITE:
        score += mobility
    else:
        score -= mobility

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
