import chess
from zobrist import *
import tkinter as tk
from PIL import Image, ImageTk
import os
import json

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
        0, 0, 0, 5, 5, 0, 0, 0,
        -5,-5,-15,-15,-15,-15,-5,-5,
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

def is_pinned(board, square):
    """Retourne True si la pièce sur square est clouée contre le roi adverse."""
    piece = board.piece_at(square)
    if piece is None:
        return False

    king_square = board.king(not piece.color)
    if king_square is None:
        return False

    rank1, file1 = chess.square_rank(square), chess.square_file(square)
    rank2, file2 = chess.square_rank(king_square), chess.square_file(king_square)

    delta_rank = rank2 - rank1
    delta_file = file2 - file1

    step_rank = 0 if delta_rank == 0 else (delta_rank // abs(delta_rank))
    step_file = 0 if delta_file == 0 else (delta_file // abs(delta_file))

    if step_rank == 0 and step_file == 0:
        return False

    r, f = rank1 + step_rank, file1 + step_file
    blockers = 0
    while (r, f) != (rank2, file2):
        if not (0 <= r <= 7 and 0 <= f <= 7):
            break  # carré hors plateau
        sq = chess.square(f, r)
        if board.piece_at(sq) is not None:
            blockers += 1
        r += step_rank
        f += step_file

    return blockers == 1

def evaluation (board):
    """
    Évalue la position du plateau et retourne un score.
    Un score positif indique un avantage pour les blancs, tandis qu'un score négatif indique un avantage pour les noirs.
    L'évaluation prend en compte la valeur des pièces et leur position sur le plateau.
    On va utiliser cette évaluation avec l'algorithme mini-max pour que notre IA puisse choisir le meilleur coup à jouer.
    """
    score = 0

    # Fin de partie
    if board.is_checkmate():
        return -float('inf') if board.turn else float('inf')
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    num_moves_played = board.fullmove_number
    total_pieces = sum(1 for sq in chess.SQUARES if board.piece_at(sq) is not None)
    early_game_coeff = min(1, total_pieces / 32)

    # Pré-calcul mobilité
    mobility = {sq:0 for sq in chess.SQUARES}
    for move in board.legal_moves:
        mobility[move.from_square] += 1

    # Pré-calcul attaquants
    attackers_white = {sq: board.attackers(chess.WHITE, sq) for sq in chess.SQUARES}
    attackers_black = {sq: board.attackers(chess.BLACK, sq) for sq in chess.SQUARES}

    # Cases centrales
    CENTER = [chess.D4, chess.E4, chess.D5, chess.E5]

    # Boucle principale sur toutes les pièces
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue

        symbol = piece.symbol()
        value = VALEURS_PIECES[symbol.lower()]
        table_value = (VALEURS_POSITIONS_BLANCHES[symbol][square] if piece.color == chess.WHITE
                       else VALEURS_POSITIONS_NOIR[symbol.lower()][square])
        table_value *= early_game_coeff

        piece_score = value + table_value

        # Mobilité pondérée
        piece_score += mobility[square] * (1 if symbol.lower() in ['p','n','b'] else 3)

        # Protégé / attaqué
        defenders = attackers_white[square] if piece.color == chess.WHITE else attackers_black[square]
        attackers_set = attackers_black[square] if piece.color == chess.WHITE else attackers_white[square]
        if defenders:
            piece_score *= 1.1
        if attackers_set:
            piece_score *= 0.9

        # Développement début de partie
        if num_moves_played <= 12:
            if piece.color == chess.WHITE:
                if symbol in ['N','B','R','Q'] and square in [chess.B1,chess.G1,chess.C1,chess.F1,chess.D1,chess.E1,chess.A1,chess.H1]:
                    piece_score += 30
                elif symbol == 'P' and square in [chess.C2,chess.D2,chess.E2,chess.F2]:
                    piece_score += 20
            else:
                if symbol in ['n','b','r','q'] and square in [chess.B8,chess.G8,chess.C8,chess.F8,chess.D8,chess.E8,chess.A8,chess.H8]:
                    piece_score += 30
                elif symbol == 'p' and square in [chess.C7,chess.D7,chess.E7,chess.F7]:
                    piece_score += 20

        # Contrôle du centre
        if square in CENTER:
            piece_score += 10 if piece.color == chess.WHITE else -10

        # Avancement des pions centraux
        if symbol.lower() == 'p':
            rank = chess.square_rank(square)
            if piece.color == chess.WHITE and rank >= 3:
                piece_score += 5
            elif piece.color == chess.BLACK and rank <= 4:
                piece_score += 5

        # Pins
        if is_pinned(board, square):
            piece_score += 20 if piece.color == chess.WHITE else -20

        score += piece_score if piece.color == chess.WHITE else -piece_score

    # Pions doublés / passés
    for file in range(8):
        pawns_white = [sq for sq in chess.SQUARES if board.piece_at(sq) and board.piece_at(sq).symbol() == 'P' and chess.square_file(sq) == file]
        pawns_black = [sq for sq in chess.SQUARES if board.piece_at(sq) and board.piece_at(sq).symbol() == 'p' and chess.square_file(sq) == file]

        # Doublés
        if len(pawns_white) > 1:
            score -= 10 * (len(pawns_white)-1)
        if len(pawns_black) > 1:
            score += 10 * (len(pawns_black)-1)

        # Pions passés
        for sq in pawns_white:
            is_passed = True
            for f in range(max(0,file-1), min(8,file+2)):
                for r in range(chess.square_rank(sq)+1, 8):
                    p = board.piece_at(chess.square(f,r))
                    if p and p.color == chess.BLACK and p.symbol().lower() == 'p':
                        is_passed = False
            if is_passed:
                score += 20
        for sq in pawns_black:
            is_passed = True
            for f in range(max(0,file-1), min(8,file+2)):
                for r in range(0, chess.square_rank(sq)):
                    p = board.piece_at(chess.square(f,r))
                    if p and p.color == chess.WHITE and p.symbol().lower() == 'p':
                        is_passed = False
            if is_passed:
                score -= 20

    # Bonus tactiques
    if board.turn == chess.WHITE:
        score += 50 if board.is_check() else 0
    else:
        score -= 50 if board.is_check() else 0

    # Fourchettes
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if not piece:
            continue
        attacks = board.attacks(square)
        important_targets = [t for t in attacks if board.piece_at(t) and board.piece_at(t).symbol().lower() in ['k','q','r','b','n']]
        if len(important_targets) >= 2:
            if piece.color == chess.WHITE:
                score += 50
            else:
                score -= 50

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

    _ , move, _ = alpha_beta(TT, board, profondeur, cle, ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES, -float('inf'), float('inf'), board.turn == chess.WHITE)
    return move


EXACT = 0
LOWERBOUND = 1
UPPERBOUND = 2

TAILLE_CASE = 80
IMG_DIR = "img"

def charger_image(nom, mult_size=1):
    chemin = os.path.join(IMG_DIR, nom)
    img = Image.open(chemin).resize((int(TAILLE_CASE * mult_size), int(TAILLE_CASE * mult_size)))
    return ImageTk.PhotoImage(img)


MEMOIRE_FILE = "memoire.json"

def load_memoire():
    if os.path.exists(MEMOIRE_FILE):
        try:
            with open(MEMOIRE_FILE, "r") as f:
                memoire = json.load(f)
        except json.JSONDecodeError:
            print("Mémoire corrompue. Nouvelle mémoire créée.")
            memoire = {}
    else:
        memoire = {}
    return memoire

def save_memoire(memoire):
    with open(MEMOIRE_FILE, "w") as f:
        json.dump(memoire, f, indent=2)

def update_memory(memoire,board, move, eval_score):
    uci = move.uci()
    if board not in memoire:
        memoire[board] = {"moves": {}}
    if "moves" not in memoire[board]:
        memoire[board]["moves"] = {}
    if uci not in memoire[board]["moves"]:
        memoire[board]["moves"][uci] = []
    memoire[board]["moves"][uci].append(eval_score)

def find_move_memory(memoire,board):
    if board in memoire and "moves" in memoire[board]:
        score_max=0
        move_max=None
        for move in memoire[board]["moves"]:
            if move[move.uci()]>score_max:
                score_max=move[move.uci()]
                move_max=move
        return move_max
    return None



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

        self.plateau = charger_image("plateau.png",8)

        self.canvas = tk.Canvas(
            root,
            width=8*TAILLE_CASE,
            height=8*TAILLE_CASE
        )
        self.canvas.pack()

        self.draw()

    def draw(self):
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.plateau, anchor="nw")

        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece:
                col = chess.square_file(square)
                row = 7 - chess.square_rank(square)
                self.canvas.create_image(
                    col*TAILLE_CASE,
                    row*TAILLE_CASE,
                    image=self.images[piece.symbol()],
                    anchor="nw"
                )

    def jouer_un_coup(self):
        if self.board.is_game_over():
            print("Partie terminée :", self.board.result())
            return

        move = ia_move(
            self.TT, self.board, 3, self.cle,
            self.ZP, self.ZR, self.ZE, self.ZT, self.IP,
            maximizing=self.board.turn == chess.WHITE
        )

        if move is None:
            return

        self.cle = update_cle(
            self.board, self.cle, move,
            self.ZP, self.ZR, self.ZE, self.ZT, self.IP
        )

        self.board.push(move)
        self.draw()

        self.root.after(300, self.jouer_un_coup)

# =======================
# MAIN
# =======================

if __name__ == "__main__":
    board = chess.Board()

    TT = creer_TT()
    zobrist = creer_zobrist()
    cle = recuperer_cle_TT(board, *zobrist)

    root = tk.Tk()
    root.title("IA Échecs – Alpha Beta")

    gui = ChessGUI(root, board, cle, TT, zobrist)

    root.after(500, gui.jouer_un_coup)
    root.mainloop()

"""
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
"""
