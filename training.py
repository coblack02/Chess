import chess
import random
import json
from IA_LA_VRAIE import ia_move, learn_from_position, est_coup_important
from gestion_memoire import *
from zobrist import *

def jouer_partie():
    board = chess.Board()
    TT = creer_TT()
    ZP, ZR, ZE, ZT, IP = creer_zobrist()

    while not board.is_game_over():
        if board.turn == chess.WHITE:
            move = ia_move(TT, board, 4, ZP, ZR, ZE, ZT, IP)
        else:
            move = ia_move(TT, board, 4, ZP, ZR, ZE, ZT, IP)

        board.push(move)

        if est_coup_important(board, move):
            learn_from_position(board, 1 if board.turn == chess.BLACK else -1, move)

    result = 1 if board.result() == "1-0" else -1 if board.result() == "0-1" else 0
    return result

def entrainement(nb_parties=10):
    for i in range(nb_parties):
        print(f"Partie {i+1}/{nb_parties}")
        result = jouer_partie()
        print(f"Résultat : {result}")

    save_memoire()

if __name__ == "__main__":
    entrainement(nb_parties=10)
