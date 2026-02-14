import chess
from zobrist import *

def mini_max (board, profondeur, maximizing: bool):
    """
    Ce truc ne ne sert à rien mais nous aidera pour construire l'algorithme alpha-beta
    """

    if profondeur == 0:
        return evaluation (board)
    else:
        best_score = -float('inf') if maximizing else float('inf')
        best_move = None
        for move in board.legal_moves():
            board.push(move)
            score = mini_max(board, profondeur - 1)
            board.pop()
            if maximizing:
                best_score = max(best_score, score)
                best_move = move
            else:
                best_score = min(best_score, score)
                best_move = move
        return best_score, best_move

#on fera une fonction qui va utiliser des coefficients puis l'ia les modifiera pour les optimiser

VALEURS_PIECES = {
    'p': 100,
    'n': 320,
    'b': 330,
    'r': 500,
    'q': 900,
    'k': 20000
}

VALEURS_POSITIONS_BLANCHES = {
    'P': [
        0, 0, 0, 0, 0, 0, 0, 0,
        50, 50, 50, 50, 50, 50, 50, 50,
        10, 10, 20, 30, 30, 20, 10, 10,
        5, 5, 10, 25, 25 , 10 , 5 , 5,
        -10,-10,-20,-25,-25,-20,-10,-10,
        -25,-25,-35,-45,-45,-35,-25,-25,
        -37.5,-37.5,-47.5,-75,-75,-47.5,-37.5,-37.5,
        -50 ,-50,-50,-50,-50,-50,-50,-50
    ],

    'N': [
        -50,-40,-30,-30,-30,-30,-40,-50,
        -40,-20,0,0,0,0,-20,-40,    
        -30,0,10,15,15,10,0,-30,
        -30,5,15,20,20,15,5,-30,
        -30,0,15,20,20,15,0,-30,
        -30,5,10,15,15,10,5,-30,
        -40,-20,0,5,5,0,-20,-40,
        -50,-40,-30,-30,-30,-30,-40,-50
    ],

    'B': [
        -20, -10, -10, -10, -10, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 10, 10, 5, 0, -10,
        -10, 5, 5, 10, 10, 5, 5, -10,
        -10, 0, 10, 10, 10, 10, 0, -10,
        -10, 10, 10, 10, 10, 10, 10, -10,
        -10, 5, 0, 0, 0, 0, 5, -10,
        -20, -10, -10, -10, -10, -10, -10, -20
    ],

    'R': [
        5, 7.5, 10, 10, 10, 10, 7.5, 5,
        -20, 5, 5, 5, 5, 5, 5, -20,
        -50, 0, 0, 0, 0, 0, 0, -50,
        -50, 0, 0, 0, 0, 0, 0, -50,
        -50, 0, 0, 0, 0, 0, 0, -50,
        -50 , 0 , 0 , 0 , 0 , 0 , 0 , -50,
        -50 , -5 , -5 , -5 , -5 , -5 , -5 , -50,
        -20 ,-20,-10 ,-5 ,-5 ,-10 ,-10 ,-20
    ],

    'Q': [
        -20, -10, -10, -5, -5, -10, -10, -20,
        -10, 0, 0, 0, 0, 0, 0, -10,
        -10, 0, 5, 5, 5, 5, 0, -10,
        -5 , 0 , 5 , 5 , 5 , 5 , 0 , -5,
        0 , 0 , 5 , 5 , 5 , 5 , 0 , -10,
        -10 , 5 , 5 , 5 , 5 , 5 , 0 ,-10,
        -10 , 0 , 5 , 0 , 0 , 0 , 0 ,-10,
        -20 ,-10 ,-10 ,-5 ,-5 ,-10 ,-10 ,-20
    ],

    'K': [
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30, -40, -40, -50, -50, -40, -40, -30,
        -30 , 0 , 0 , 0 , 0 , 0 , 0 , -30,
        -20 , 20 , 20 , 20 , 20 , 20 , 20 ,-20,
        -10 ,-20 ,-20 ,-20 ,-20 ,-20 ,-20 ,-10,
        20 , 20 , 0 , 0 , 0 , 0 , 20 , 20,
        20 , 30 , 10 , 0 , 0 , 10 , 30 , 20
     ]
}

#SURTOUT POUR L'EARLY GAME, IL FAUDRA UTILISER UN COEFFCIENT QUI SE REDUIT AU FUR ET A MESURE

VALEURS_POSITIONS_NOIR = {
    'p': VALEURS_POSITIONS_BLANCHES['P'][::-1],
    'n': VALEURS_POSITIONS_BLANCHES['N'][::-1],
    'b': VALEURS_POSITIONS_BLANCHES['B'][::-1],
    'r': VALEURS_POSITIONS_BLANCHES['R'][::-1],
    'q': VALEURS_POSITIONS_BLANCHES['Q'][::-1],
    'k': VALEURS_POSITIONS_BLANCHES['K'][::-1]
}


def evaluation (board):
    """
    Évalue la position du plateau et retourne un score.
    Un score positif indique un avantage pour les blancs, tandis qu'un score négatif indique un avantage pour les noirs.
    L'évaluation prend en compte la valeur des pièces et leur position sur le plateau.
    On va utiliser cette évaluation avec l'algorithme mini-max pour que notre IA puisse choisir le meilleur coup à jouer.
    """
    score = 0

    if board.is_checkmate():   
        return -float('inf') if board.turn else float('inf')
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
        
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is not None:
            piece_value = VALEURS_PIECES[piece.symbol().lower()]
            if piece.color == chess.WHITE:
                score += piece_value + VALEURS_POSITIONS_BLANCHES[piece.symbol()][square]
            else:
                score -= piece_value + VALEURS_POSITIONS_NOIR[piece.symbol()][square]
    return score

def alpha_beta (TT, board, profondeur:int , cle, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES, alpha: float = -float('inf'), beta: float = float('inf'), maximizing: bool = True) -> tuple:
    """
    Ordre:
    - Regarde la mémoire pour voir si la position a déjà été évaluée
        - Si oui, retourne l'évaluation
    - Si non, évalue la position (avec mini_max)
    """

    moves = list(board.legal_moves)
    moves.sort(key=lambda move: board.is_capture(move), reverse=maximizing) #regarde d'abord les captures, trouvant peut etre des moves plus interessants comme le mat ou la prise d'une piece importante
    
    #print ('Profondeur :', profondeur, 'Nombre de coups possibles :', len(moves), 'Alpha :', alpha, 'Beta :', beta)

    if cle in TT:
        if TT[cle]['move'] in moves and TT[cle]['profondeur'] >= profondeur: #si le move stocke est dans la table et que le move est possible (car on peux avoir plusieurs positions qui ont la meme cle) alors on retourne l'evaluation stockee
            return TT[cle]['score'], TT[cle]['move'], update_cle(board, cle, TT[cle]['move'], ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES) #on met à jour la clé pour la position après le coup joué
        
    if profondeur == 0 or board.is_game_over():
        return evaluation (board), None, cle
    
    if maximizing: #si coup joueur blanc
        best_score = -float('inf')
        best_move = None
        for move in moves:
            
            nouvelle_cle = update_cle(board, cle, move, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES)
            board.push(move)
            score, _, _ = alpha_beta(TT, board, profondeur -1 , nouvelle_cle, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES, maximizing= board.turn == chess.WHITE ) 
            board.pop() #retourne en arriere pour tester le coup suivant

            if score > best_score:
                best_score = score
                best_move = move

            alpha = max(alpha, best_score)

            if alpha >= beta: #il gagne, pas besoin de continuer à chercher
                break

    else: #si coup joueur noir
        best_score = float('inf')
        best_move = None
        for move in moves:
            
            nouvelle_cle = update_cle(board, cle, move, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES)
            board.push(move)
            score, _, _ = alpha_beta(TT, board, profondeur -1 , nouvelle_cle, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES, maximizing= board.turn == chess.WHITE) 
            board.pop()
            
            if score < best_score:
                best_score = score
                best_move = move
            
            beta = min(beta, best_score)

            if alpha >= beta: 
                break

    if best_score <= alpha:
        flag = UPPERBOUND
    elif best_score >= beta:
        flag = LOWERBOUND
    else:
        flag = EXACT

    #print ('Mis à jour dans la TT : Profondeur :', profondeur, 'Meilleur coup :', best_move, 'Meilleur score :', best_score, 'Flag :', flag)
    update_TT(TT, cle, best_score, best_move, profondeur, flag) #on stocke dans la memoire vive (TT)
    return best_score, best_move, nouvelle_cle

def ia_move(TT, board, profondeur, cle, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES, maximizing):
    """
    Fonction qui retourne le meilleur coup à jouer pour l'IA en utilisant l'algorithme alpha-beta
    """

    score, move, _ = alpha_beta(TT, board, profondeur, cle, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES, -float('inf'), float('inf'), board.turn == chess.WHITE)
    return move

EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2

if __name__ == "__main__":
    board = chess.Board()
    Z = creer_TT()
    ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES = creer_zobrist()
    premiere_cle = recuperer_cle_TT(board, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES) #on calcule la clé de la position actuelle du plateau pour pouvoir la stocker dans la table de transposition
    for i in range(1000):
        move = ia_move(Z, board, profondeur=3, cle=premiere_cle, ZOBRIST_PIECES=ZOBRIST_PIECES, ZOBRIST_ROQUES=ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT=ZOBRIST_EN_PASSANT, ZOBRIST_TOUR=ZOBRIST_TOUR, INDEX_PIECES=INDEX_PIECES, maximizing=board.turn == chess.WHITE)
        print("IA joue :", move, "Round :" , i+1, board.turn == chess.WHITE),
        print ("Evaluation de la position :", evaluation(board))
        board.push(move)
        print(board)
        if board.is_game_over(): break
    print ("table de zobrist :", len(Z))
    print ("Partie terminée :", board.result())


