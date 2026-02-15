import chess
import chess.polyglot 
import random

def creer_zobrist():
    """
    Crée une table de Zobrist pour le jeu d'échecs.
    La table de Zobrist est une table de hachage utilisée pour représenter les positions de plateau de manière efficace.
    Elle est utilisée pour éviter de réévaluer les positions déjà évaluées lors de l'exploration de l'arbre de recherche.
    La table de Zobrist est un tableau à deux dimensions où chaque entrée correspond à une pièce et une case du plateau. 
    Chaque entrée contient un nombre aléatoire unique qui représente la présence ou l'absence d'une pièce sur cette case.
    """
    ZOBRIST_PIECES = [[random.getrandbits(64) for _ in range(12)] for _ in range(64)]
    ZOBRIST_ROQUES = [random.getrandbits(64) for _ in range(4)]
    ZOBRIST_EN_PASSANT = [random.getrandbits(64) for _ in range(8)]
    ZOBRIST_TOUR = random.getrandbits(64)
    INDEX_PIECES = { 'P': 0, 'N': 1, 'B': 2, 'R': 3, 'Q': 4, 'K': 5, 'p': 6, 'n': 7, 'b': 8, 'r': 9, 'q': 10, 'k': 11 }

    return ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES


def hash_zobrist(board, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES): 
    """
    Calcule le hachage de Zobrist pour une position de plateau donnée.
    Le hachage de Zobrist est calculé en effectuant un XOR entre les valeurs correspondantes dans la table de Zobrist pour chaque pièce présente sur le plateau, ainsi que pour les droits de roque, les cases d'en passant et le tour de jeu.
    """

    hachage = 0

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is not None:
            piece_index = INDEX_PIECES[piece.symbol()]
            hachage ^= ZOBRIST_PIECES[square][piece_index]

    # droits de roque
    if board.has_kingside_castling_rights(chess.WHITE):
        hachage ^= ZOBRIST_ROQUES[0]
    if board.has_queenside_castling_rights(chess.WHITE):
        hachage ^= ZOBRIST_ROQUES[1]
    if board.has_kingside_castling_rights(chess.BLACK):
        hachage ^= ZOBRIST_ROQUES[2]
    if board.has_queenside_castling_rights(chess.BLACK):
        hachage ^= ZOBRIST_ROQUES[3]

    # cases d'en passant
    if board.ep_square is not None:
        file = chess.square_file(board.ep_square)
        hachage ^= ZOBRIST_EN_PASSANT[file]

    # tour de jeu
    if board.turn == chess.BLACK:
        hachage ^= ZOBRIST_TOUR

    return hachage

def creer_TT():
    """
    Cree une table de transposition pour stocker les positions deja evaluees et eviter de les reevaluer
    La table de transposition est un dictionnaire où les clés sont des positions de plateau de nombre en 64 bits (Zobrist hashing) et les valeurs sont les évaluations correspondantes.
    Cette derniere sert surtout de memoire vive
    """
    return {}

def update_TT(TT: dict, cle: int, evaluation, move = None, profondeur = None, flag = None):
    """
    Met à jour l'évaluation d'une position de plateau dans la table de transposition
    Si la position est déjà dans la table, on ne met à jour que si l'évaluation est meilleure.
    En effet la cle peut parfois etre la meme on garde alors la plus grande profondeur
    Parametres:
    - TT: la table de transposition
    - cle: la clé de la position à mettre à jour    
    - evaluation: le score de la position
    - move: le meilleur coup pour cette position
    - profondeur: la profondeur à laquelle l'évaluation a été faite
    - flag: le type d'évaluation (exact(0), lower bound(1), upper bound(2))
    """

    if cle not in TT or TT[cle]['profondeur'] < profondeur: #si la position n'est pas dans la table ou si la profondeur de l'evaluation est plus grande que celle stockee alors on met a jour
        TT[cle] = {'score': evaluation, 'profondeur': profondeur, 'move': move, 'flag': flag} #a jouter les lower bound et upper bound pour faire du alpha-beta avec table de transposition

def recuperer_cle_TT(board, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES):
    """
    Récupère l'évaluation d'une position de plateau à partir de la table de transposition.
    """     
    return hash_zobrist(board, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES)

def update_cle(board, cle, move, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT,  ZOBRIST_TOUR, INDEX_PIECES):
    """
    Met à jour la clé de la table de transposition en fonction du coup joue
    On utilise le Zobrist hashing pour mettre à jour la clé en fonction du coup joué
    C'est BEAUCOUP plus rapide que de recalculer la clé à partir de la position du plateau à chaque fois
    """

    piece = board.piece_at(move.from_square)
    piece_index = INDEX_PIECES[piece.symbol()]

    # enlever ancien en passant 
    if board.ep_square is not None:
        cle ^= ZOBRIST_EN_PASSANT[chess.square_file(board.ep_square)]

    #  enlever pièce de départ 
    cle ^= ZOBRIST_PIECES[move.from_square][piece_index]

    # capture 
    if board.is_capture(move):
        if board.is_en_passant(move):
            cap_sq = move.to_square + (-8 if piece.color == chess.WHITE else 8)
        else:
            cap_sq = move.to_square
        captured = board.piece_at(cap_sq)
        cle ^= ZOBRIST_PIECES[cap_sq][INDEX_PIECES[captured.symbol()]]

    #  roque : déplacement tour et roi
    if board.is_castling(move):
        if move.to_square == chess.G1:
            rook_from, rook_to = chess.H1, chess.F1
        elif move.to_square == chess.C1:
            rook_from, rook_to = chess.A1, chess.D1
        elif move.to_square == chess.G8:
            rook_from, rook_to = chess.H8, chess.F8
        else:
            rook_from, rook_to = chess.A8, chess.D8

        rook = board.piece_at(rook_from)
        r_idx = INDEX_PIECES[rook.symbol()]
        cle ^= ZOBRIST_PIECES[rook_from][r_idx]
        cle ^= ZOBRIST_PIECES[rook_to][r_idx]

    #  arrivée pièce 
    if move.promotion:
        promo = chess.Piece(move.promotion, piece.color)
        cle ^= ZOBRIST_PIECES[move.to_square][INDEX_PIECES[promo.symbol()]]
    else:
        cle ^= ZOBRIST_PIECES[move.to_square][piece_index]

    #  droits de roque 
    old = board.castling_rights
    board.push(move)
    new = board.castling_rights
    board.pop()

    diff = old ^ new
    if diff & chess.BB_H1: cle ^= ZOBRIST_ROQUES[0]
    if diff & chess.BB_A1: cle ^= ZOBRIST_ROQUES[1]
    if diff & chess.BB_H8: cle ^= ZOBRIST_ROQUES[2]
    if diff & chess.BB_A8: cle ^= ZOBRIST_ROQUES[3]

    # nouvel en passant 
    if piece.piece_type == chess.PAWN:
        if abs(chess.square_rank(move.from_square) -chess.square_rank(move.to_square)) == 2:
            file = chess.square_file(move.to_square)
            cle ^= ZOBRIST_EN_PASSANT[file]


    # tour de jeu
    cle ^= ZOBRIST_TOUR

    return cle #on fait un XOR entre la clé actuelle et le hash du coup joué pour obtenir la nouvelle clé de la position après le coup joué
