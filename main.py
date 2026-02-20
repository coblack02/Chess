"""
main.py
=======
Point d'entrée principal de l'application d'échecs IA vs IA.

Lance une partie avec interface graphique Tkinter entre deux instances
de JoueurIA (blancs et noirs). À la fermeture de la fenêtre, les coups
importants collectés pendant la partie sont utilisés pour un apprentissage
supervisé, puis memoire.json est sauvegardé.


"""

from tkinter import Tk
from chess import Board, WHITE, BLACK
import chess
from zobrist import creer_TT, creer_zobrist
from IA_LA_VRAIE import ia_move, est_coup_important, learn_from_position, get_game_phase, get_depth_for_phase
from gestion_memoire import load_memoire, save_memoire
from canvas_tkinter import Chess_UI

# ── Configuration ─────────────────────────────────────────────────────────────
TT_MAX_SIZE = 200_000
"""Nombre maximal d'entrées dans la table de transposition par joueur."""

VALEURS_PIECES, TABLES, MOBILITY_MULTIPLIER, PIN_PENALTY, TEMPO_BONUS, WEIGHTS, PROFONDEURS = load_memoire()


class JoueurIA:
    """
    Encapsule toute la logique d'un joueur IA pour une partie avec interface.

    Chaque joueur possède sa propre table de transposition et ses propres
    tables Zobrist — les deux IA sont totalement indépendantes.
    La profondeur de recherche est calculée dynamiquement à chaque coup
    en fonction du matériel restant sur le plateau (phase de jeu).

    Attributs
    ----------
    board : chess.Board
        Référence au plateau partagé de la partie.
    couleur : bool
        chess.WHITE ou chess.BLACK.
    TT : dict
        Table de transposition propre à cette instance.
    ZOBRIST_PIECES, ZOBRIST_ROQUES, ZOBRIST_EN_PASSANT, ZOBRIST_TOUR, INDEX_PIECES
        Tables Zobrist pour le hachage incrémental des positions.
    coups_importants : list[tuple[str, str]]
        Liste de (fen, move_uci) collectés pendant la partie pour
        l'apprentissage post-partie.
    """

    def __init__(self, board: Board, couleur: bool):
        """
        Initialise le joueur IA.

        Paramètres
        ----------
        board : chess.Board
            Plateau de jeu partagé.
        couleur : bool
            chess.WHITE ou chess.BLACK — détermine l'affichage des logs.
        """
        self.board   = board
        self.couleur = couleur
        self.TT      = creer_TT()
        self.ZOBRIST_PIECES, self.ZOBRIST_ROQUES, \
            self.ZOBRIST_EN_PASSANT, self.ZOBRIST_TOUR, \
            self.INDEX_PIECES = creer_zobrist()
        self.coups_importants = []
        print(f" JoueurIA initialisé ({'Blanc' if couleur == WHITE else 'Noir'})")

    def coup(self) -> str:
        """
        Calcule le meilleur coup pour la position courante et le retourne
        en notation SAN.

        Étapes :
            1. Détermination de la phase de jeu et de la profondeur.
            2. Appel à ia_move() pour le calcul alpha-beta.
            3. Fallback aléatoire si ia_move retourne None (sécurité).
            4. Enregistrement dans coups_importants si le coup est notable.

        Retourne
        --------
        str
            Coup en notation SAN (ex. 'e4', 'Nf3', 'O-O', 'exd5').
        """

        phase      = get_game_phase(self.board)
        profondeur = get_depth_for_phase(phase)

        couleur = 'Blancs' if self.board.turn == WHITE else 'Noirs'
        print(f"\n {couleur} — phase: {phase} | profondeur: {profondeur} | TT: {len(self.TT)}")

        move = ia_move(
            self.TT,
            self.board,
            profondeur,
            self.ZOBRIST_PIECES,
            self.ZOBRIST_ROQUES,
            self.ZOBRIST_EN_PASSANT,
            self.ZOBRIST_TOUR,
            self.INDEX_PIECES
        )

        if move is None:
            print("  Aucun coup trouvé — coup aléatoire")
            import random
            move = random.choice(list(self.board.legal_moves))

        san = self.board.san(move)

        if self.board.is_capture(move):
            print(f"    Capture : {san}")

        if est_coup_important(self.board, move):
            self.coups_importants.append((self.board.fen(), move.uci()))

        print(f"   {couleur} jouent : {san}")
        return san


def main() -> None:
    """
    Point d'entrée principal.

    Crée le plateau, les deux joueurs IA et l'interface graphique, puis
    lance la boucle Tkinter. À la fermeture :
        1. Calcule le résultat final de la partie.
        2. Appelle learn_from_position() sur tous les coups importants
           collectés par les deux IA, avec le vrai résultat comme cible.
        3. Sauvegarde memoire.json.
    """
    print("Lancement de la partie d'échecs...\n")

    root  = Tk()
    root.title("IA d'Échecs")
    board = Board()

    print("  Création IA Blancs...")
    ia_blanc = JoueurIA(board, WHITE)

    print("  Création IA Noirs...")
    ia_noir  = JoueurIA(board, BLACK)

    print("\n Chargement de l'interface...")
    ui = Chess_UI(root, board, ia_blanc, ia_noir)
    root.mainloop()

    # ── Apprentissage post-partie ─────────────────────────────────────────────
    res_str = board.result()
    result  = 1 if res_str == "1-0" else -1 if res_str == "0-1" else 0

    for ia in (ia_blanc, ia_noir):
        for fen, move_uci in ia.coups_importants:
            board.set_fen(fen)
            learn_from_position(board, result, chess.Move.from_uci(move_uci))

    save_memoire()
    print(" Mémoire sauvegardée.")


main()
