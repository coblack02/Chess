from tkinter import Tk
from chess import Board, WHITE, BLACK
from zobrist import *
from IA_LA_VRAIE import ia_move_with_timer, est_coup_important, learn_from_position
from gestion_memoire import *
from canvas_tkinter import Chess_UI

# Taille maximale de la table de transposition
TT_MAX_SIZE = 200000

class JoueurIA:
    """
    Classe qui encapsule TOUTE la logique de l'IA.
    La TT est stockée dans l'INSTANCE (pas en global).
    """
    def __init__(self, board, couleur):
        self.board = board
        self.couleur = couleur
        self.TT = creer_TT()
        self.ZOBRIST_PIECES, self.ZOBRIST_ROQUES, self.ZOBRIST_EN_PASSANT, self.ZOBRIST_TOUR, self.INDEX_PIECES = creer_zobrist()
        self.profondeur = 6
        self.coups_importants = []  # Stocke les coups importants sous forme (fen, move_uci)
        print(f" JoueurIA initialisé ({'Blanc' if couleur == WHITE else 'Noir'})")

    def _nettoyer_TT(self):
        """Vide la moitié de la TT quand elle devient trop grande."""
        if len(self.TT) > TT_MAX_SIZE:
            cles = list(self.TT.keys())
            for cle in cles[:len(cles) // 2]:
                del self.TT[cle]
            print(f"🧹 TT nettoyée : {len(self.TT)} entrées restantes")

    def calculer_profondeur_dynamique(self):
        """Calcule la profondeur de recherche en fonction de la phase de jeu."""
        if self.board.fullmove_number < 10:  # Ouverture
            return 4
        elif 10 <= self.board.fullmove_number < 30:  # Milieu de jeu
            return 5
        else:  # Fin de partie
            return 6

    def coup(self):
        """Calcule et retourne le meilleur coup en notation SAN."""
        self.profondeur = self.calculer_profondeur_dynamique()
        couleur = 'Blancs' if self.board.turn == WHITE else 'Noirs'
        print(f" Calcul pour {couleur} (profondeur {self.profondeur}, TT: {len(self.TT)})...")

        move = ia_move_with_timer(
            self.TT,
            self.board,
            self.profondeur,
            self.ZOBRIST_PIECES,
            self.ZOBRIST_ROQUES,
            self.ZOBRIST_EN_PASSANT,
            self.ZOBRIST_TOUR,
            self.INDEX_PIECES,
            max_time=0.5
        )

        if move is None:
            print(" Aucun coup trouvé, coup aléatoire")
            import random
            move = random.choice(list(self.board.legal_moves))

        san = self.board.san(move)

        # Stocker les coups importants pour un apprentissage ultérieur
        if est_coup_important(self.board, move):
            self.coups_importants.append((self.board.fen(), move.uci()))

        print(f" {couleur} jouent : {san}")
        return san

if __name__ == "__main__":
    print("Lancement du tournoi d'échecs...\n")

    root = Tk()
    root.title("IA d'Échecs")

    board = Board()

    print(" Création IA Blancs...")
    ia_blanc = JoueurIA(board, WHITE)

    print(" Création IA Noirs...")
    ia_noir = JoueurIA(board, BLACK)

    print("\n Chargement de l'interface...")
    print(" Lancement de la partie!\n")

    ui = Chess_UI(root, board, ia_blanc, ia_noir)
    root.mainloop()

    # Résultat final de la partie
    result = 1 if board.result() == "1-0" else -1 if board.result() == "0-1" else 0

    # Apprendre uniquement à partir des coups importants
    for ia in [ia_blanc, ia_noir]:
        for fen, move_uci in ia.coups_importants:
            board.set_fen(fen)
            move = chess.Move.from_uci(move_uci)
            learn_from_position(board, result, move)

    save_memoire()
