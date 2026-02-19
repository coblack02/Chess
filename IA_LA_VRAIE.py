import chess
from zobrist import *
import tkinter as tk
from PIL import Image, ImageTk
import os
import json
from openings import polyglot_move

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

TABLE_PION = [
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    15, 15, 25, 35, 35, 25, 15, 15,
    15, 15, 20, 35, 35, 20, 15, 15,
    15, 15, 20, 25, 25, 20, 15, 15,
    10, 10,  5,  5,  5,  5, 10, 10,
   -37,-37,-47,-75,-75,-47,-37,-37,
   -50,-50,-50,-50,-50,-50,-50,-50
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

TABLES = {
    chess.PAWN: TABLE_PION,
    chess.KNIGHT: TABLE_CAVALIER
}

def evaluate(board):
    if board.is_checkmate():
        return -100000 if board.turn else 100000
    if board.is_stalemate():
        return 0

    values = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 0
    }

    score = 0
    for piece_type in values:
        score += len(board.pieces(piece_type, chess.WHITE)) * values[piece_type]
        score -= len(board.pieces(piece_type, chess.BLACK)) * values[piece_type]

    return score

def quiescence(board, alpha, beta):
    stand_pat = evaluate(board)
    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat

    moves = list(board.legal_moves)
    moves.sort(key=lambda m: (
    board.is_capture(m),
    board.gives_check(m),
    m.promotion is not None
    ), reverse=True)

    for move in moves:
        if board.is_capture(move):
            board.push(move)
            score = -quiescence(board, -beta, -alpha)
            board.pop()

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

    return alpha

def alpha_beta(TT, board, depth, alpha, beta, ZP, ZR, ZE, ZT, IP):
    cle = hash_zobrist(board, ZP, ZR, ZE, ZT, IP)

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

    if depth == 0 or board.is_game_over():
        return evaluate(board)

    best_score = -float('inf')
    original_alpha = alpha

    moves = sorted(
        board.legal_moves,
        key=lambda m: (board.is_capture(m), board.gives_check(m), m.promotion is not None),
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



def ia_move(board, depth, ZP, ZR, ZE, ZT, IP):
    move = None
    try:
        import chess.polyglot
        with chess.polyglot.open_reader("book.bin") as reader:
            entries = list(reader.find_all(board))
            if entries:
                move = random.choice(entries).move
    except Exception:
        pass

    if move:
        return move

    TT = {}
    best_move = None
    best_score = -float('inf')

    moves = list(board.legal_moves)
    moves.sort(key=lambda m: (board.is_capture(m), board.gives_check(m), m.promotion is not None), reverse=True)

    for move_candidate in moves:
        board.push(move_candidate)
        score = -alpha_beta(TT, board, depth - 1, -float('inf'), float('inf'), ZP, ZR, ZE, ZT, IP)
        board.pop()

        if score > best_score:
            best_score = score
            best_move = move_candidate

    return best_move

TAILLE_CASE = 80
IMG_DIR = "img"

def charger_image(nom, mult=1):
    p = os.path.join(IMG_DIR, nom)
    img = Image.open(p).resize((int(TAILLE_CASE * mult), int(TAILLE_CASE * mult)))
    return ImageTk.PhotoImage(img)

class ChessGUI:
    def __init__(self, root, board, cle, TT, zobrist):
        self.root = root
        self.board = board
        self.cle = cle
        self.TT = TT
        self.ZP, self.ZR, self.ZE, self.ZT, self.IP = zobrist

        self.images = {
            'P': charger_image("pion_blanc.png"),
            'p': charger_image("pion_noir.png"),
            'R': charger_image("tour_blanche.png"),
            'r': charger_image("tour_noire.png"),
            'N': charger_image("cavalier_blanc.png"),
            'n': charger_image("cavalier_noir.png"),
            'B': charger_image("fou_blanc.png"),
            'b': charger_image("fou_noir.png"),
            'Q': charger_image("reine_blanche.png"),
            'q': charger_image("reine_noire.png"),
            'K': charger_image("roi_blanc.png"),
            'k': charger_image("roi_noir.png"),
        }

        self.plateau = charger_image("plateau.png", 8)
        self.canvas = tk.Canvas(root, width=8*TAILLE_CASE, height=8*TAILLE_CASE)
        self.canvas.pack()
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.plateau, anchor="nw")
        for sq in chess.SQUARES:
            p = self.board.piece_at(sq)
            if p:
                x = chess.square_file(sq) * TAILLE_CASE
                y = (7 - chess.square_rank(sq)) * TAILLE_CASE
                self.canvas.create_image(x, y, image=self.images[p.symbol()], anchor="nw")

    def jouer_un_coup(self):
        if self.board.is_game_over():
            return
        move = ia_move(self.board, 3, self.ZP, self.ZR, self.ZE, self.ZT, self.IP)
        if not move:
            return
        self.cle = update_cle(self.board, self.cle, move, self.ZP, self.ZR, self.ZE, self.ZT, self.IP)
        self.board.push(move)
        self.draw()
        self.root.after(100, self.jouer_un_coup)

if __name__ == "__main__":
    board = chess.Board()
    TT = creer_TT()
    zobrist = creer_zobrist()
    cle = recuperer_cle_TT(board, *zobrist)

    root = tk.Tk()
    root.title("IA Échecs")

    gui = ChessGUI(root, board, cle, TT, zobrist)
    root.after(500, gui.jouer_un_coup)
    root.mainloop()
