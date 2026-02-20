"""
zobrist.py
==========
Implémentation du hachage de Zobrist pour les positions d'échecs.

Le hachage de Zobrist est une technique de hachage incrémental qui permet
de représenter une position d'échiquier par un entier 64 bits unique.
Sa propriété clé : mettre à jour le hash après un coup ne nécessite que
quelques XOR, au lieu de recalculer depuis zéro — ce qui rend la table
de transposition extrêmement rapide à utiliser.

Principe :
    - À l'initialisation, chaque (case, pièce) se voit assigner un entier
      aléatoire 64 bits.
    - Le hash d'une position = XOR de tous les entiers correspondant aux
      pièces présentes, plus les droits de roque, l'éventuelle prise en
      passant, et le joueur au trait.
    - Après un coup, on met à jour le hash en XOR-ant uniquement les cases
      qui ont changé (retirer l'ancienne pièce, placer la nouvelle).

Fonctions exportées :
    creer_zobrist()   → tables aléatoires
    hash_zobrist()    → hash complet depuis un board
    update_cle()      → mise à jour incrémentale après un coup
    creer_TT()        → crée une table de transposition vide
    update_TT()       → insère / met à jour une entrée dans la TT
    recuperer_cle_TT()→ calcule la clé Zobrist d'un board (alias)
"""

import chess
import chess.polyglot
import random


def creer_zobrist():
    """
    Génère les tables de nombres aléatoires nécessaires au hachage de Zobrist.

    Retourne
    --------
    ZOBRIST_PIECES : list[list[int]]
        Tableau [64 cases][12 types de pièces] de nombres aléatoires 64 bits.
        Indexé par [square][piece_index] où piece_index suit INDEX_PIECES.
    ZOBRIST_ROQUES : list[int]
        4 nombres pour les droits de roque :
        [0] blanc petit roque, [1] blanc grand roque,
        [2] noir petit roque,  [3] noir grand roque.
    ZOBRIST_EN_PASSANT : list[int]
        8 nombres pour chaque colonne possible d'une prise en passant (a–h).
    ZOBRIST_TOUR : int
        Nombre XOR-é quand c'est au tour des noirs de jouer.
    INDEX_PIECES : dict[str, int]
        Mapping symbole pièce → indice colonne dans ZOBRIST_PIECES.
        Ex. : 'P' → 0, 'K' → 5, 'p' → 6, 'k' → 11.
    """
    ZOBRIST_PIECES     = [[random.getrandbits(64) for _ in range(12)] for _ in range(64)]
    ZOBRIST_ROQUES     = [random.getrandbits(64) for _ in range(4)]
    ZOBRIST_EN_PASSANT = [random.getrandbits(64) for _ in range(8)]
    ZOBRIST_TOUR       = random.getrandbits(64)
    INDEX_PIECES       = {
        'P': 0, 'N': 1, 'B': 2, 'R': 3, 'Q': 4, 'K': 5,
        'p': 6, 'n': 7, 'b': 8, 'r': 9, 'q': 10, 'k': 11
    }

    return ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES


def hash_zobrist(board, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES):
    """
    Calcule le hash de Zobrist complet pour une position donnée.

    Parcourt toutes les cases du plateau et XOR-e les nombres correspondant
    à chaque pièce présente. Ajoute ensuite les composantes contextuelles
    (droits de roque, prise en passant, joueur au trait).

    À utiliser une seule fois par recherche (racine) ; pour les nœuds
    internes, préférer update_cle() qui est O(1).

    Paramètres
    ----------
    board : chess.Board
        Position à hacher.
    ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES
        Tables générées par creer_zobrist().

    Retourne
    --------
    int
        Hash Zobrist 64 bits de la position.
    """
    hachage = 0

    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is not None:
            hachage ^= ZOBRIST_PIECES[square][INDEX_PIECES[piece.symbol()]]

    if board.has_kingside_castling_rights(chess.WHITE):
        hachage ^= ZOBRIST_ROQUES[0]
    if board.has_queenside_castling_rights(chess.WHITE):
        hachage ^= ZOBRIST_ROQUES[1]
    if board.has_kingside_castling_rights(chess.BLACK):
        hachage ^= ZOBRIST_ROQUES[2]
    if board.has_queenside_castling_rights(chess.BLACK):
        hachage ^= ZOBRIST_ROQUES[3]

    if board.ep_square is not None:
        hachage ^= ZOBRIST_EN_PASSANT[chess.square_file(board.ep_square)]

    if board.turn == chess.BLACK:
        hachage ^= ZOBRIST_TOUR

    return hachage


def creer_TT():
    """
    Crée une table de transposition vide.

    La table de transposition (TT) est un dictionnaire Python utilisé comme
    cache des positions déjà évaluées pendant la recherche alpha-beta.
    Clé   : hash Zobrist 64 bits (int).
    Valeur : dict avec les champs 'score', 'profondeur', 'move', 'flag'.

    Retourne
    --------
    dict
        Dictionnaire vide prêt à l'emploi.
    """
    return {}


def update_TT(TT: dict, cle: int, evaluation, move=None, profondeur=None, flag=None):
    """
    Insère ou met à jour une entrée dans la table de transposition.

    On ne remplace une entrée existante que si la nouvelle profondeur est
    supérieure ou égale, car une évaluation à plus grande profondeur est
    plus fiable.

    Paramètres
    ----------
    TT : dict
        Table de transposition à modifier.
    cle : int
        Hash Zobrist de la position.
    evaluation : float
        Score numérique de la position.
    move : chess.Move, optionnel
        Meilleur coup trouvé pour cette position.
    profondeur : int, optionnel
        Profondeur à laquelle l'évaluation a été calculée.
    flag : int, optionnel
        Type de borne : EXACT (0), LOWERBOUND (1), UPPERBOUND (2).
    """
    if cle not in TT or TT[cle]['profondeur'] < profondeur:
        TT[cle] = {
            'score':     evaluation,
            'profondeur': profondeur,
            'move':       move,
            'flag':       flag
        }


def recuperer_cle_TT(board, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES):
    """
    Calcule et retourne la clé Zobrist d'une position.

    Alias de hash_zobrist() conservé pour la compatibilité avec l'ancien code.

    Paramètres
    ----------
    board : chess.Board
        Position à hacher.
    ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES
        Tables générées par creer_zobrist().

    Retourne
    --------
    int
        Hash Zobrist 64 bits.
    """
    return hash_zobrist(board, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES)


def update_cle(board, cle, move, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES):
    """
    Met à jour la clé Zobrist de façon incrémentale après un coup.

    Beaucoup plus rapide que recalculer hash_zobrist() depuis zéro :
    seules les cases modifiées par le coup sont XOR-ées.

    Gère tous les cas spéciaux :
        - Coup normal (déplacement simple).
        - Capture ordinaire.
        - Prise en passant (la pièce capturée n'est pas sur la case d'arrivée).
        - Roque (le roi et la tour bougent tous les deux).
        - Promotion (la pièce arrivante est différente de celle qui partait).
        - Modification des droits de roque (perte après mouvement roi/tour).
        - Nouvel en passant possible (pion avancé de deux cases).
        - Changement du joueur au trait (XOR ZOBRIST_TOUR à chaque coup).

    Paramètres
    ----------
    board : chess.Board
        Position AVANT le coup (le coup n'a pas encore été joué).
    cle : int
        Hash Zobrist de la position avant le coup.
    move : chess.Move
        Coup à appliquer.
    ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES
        Tables générées par creer_zobrist().

    Retourne
    --------
    int
        Hash Zobrist de la position après le coup.
    """
    piece       = board.piece_at(move.from_square)
    piece_index = INDEX_PIECES[piece.symbol()]

    # Retirer l'ancien en passant de la clé
    if board.ep_square is not None:
        cle ^= ZOBRIST_EN_PASSANT[chess.square_file(board.ep_square)]

    # Retirer la pièce de sa case de départ
    cle ^= ZOBRIST_PIECES[move.from_square][piece_index]

    # Capture : retirer la pièce capturée
    if board.is_capture(move):
        if board.is_en_passant(move):
            cap_sq = move.to_square + (-8 if piece.color == chess.WHITE else 8)
        else:
            cap_sq = move.to_square
        captured = board.piece_at(cap_sq)
        cle ^= ZOBRIST_PIECES[cap_sq][INDEX_PIECES[captured.symbol()]]

    # Roque : déplacer aussi la tour
    if board.is_castling(move):
        if move.to_square == chess.G1:
            rook_from, rook_to = chess.H1, chess.F1
        elif move.to_square == chess.C1:
            rook_from, rook_to = chess.A1, chess.D1
        elif move.to_square == chess.G8:
            rook_from, rook_to = chess.H8, chess.F8
        else:
            rook_from, rook_to = chess.A8, chess.D8

        rook  = board.piece_at(rook_from)
        r_idx = INDEX_PIECES[rook.symbol()]
        cle  ^= ZOBRIST_PIECES[rook_from][r_idx]
        cle  ^= ZOBRIST_PIECES[rook_to][r_idx]

    # Placer la pièce sur sa case d'arrivée (promotion → pièce différente)
    if move.promotion:
        promo = chess.Piece(move.promotion, piece.color)
        cle  ^= ZOBRIST_PIECES[move.to_square][INDEX_PIECES[promo.symbol()]]
    else:
        cle ^= ZOBRIST_PIECES[move.to_square][piece_index]

    # Mettre à jour les droits de roque si un roi ou une tour a bougé
    old  = board.castling_rights
    board.push(move)
    new  = board.castling_rights
    board.pop()

    diff = old ^ new
    if diff & chess.BB_H1: cle ^= ZOBRIST_ROQUES[0]
    if diff & chess.BB_A1: cle ^= ZOBRIST_ROQUES[1]
    if diff & chess.BB_H8: cle ^= ZOBRIST_ROQUES[2]
    if diff & chess.BB_A8: cle ^= ZOBRIST_ROQUES[3]

    # Nouvel en passant possible (pion avancé de deux cases)
    if piece.piece_type == chess.PAWN:
        if abs(chess.square_rank(move.from_square) - chess.square_rank(move.to_square)) == 2:
            cle ^= ZOBRIST_EN_PASSANT[chess.square_file(move.to_square)]

    # Changer le joueur au trait
    cle ^= ZOBRIST_TOUR

    return cle
