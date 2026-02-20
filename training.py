"""
training.py
===========
Entraînement headless de l'IA d'échecs, sans interface graphique.

Lance des parties IA vs IA en boucle infinie jusqu'à ce que l'utilisateur
arrête le processus avec Ctrl+C. À la fin de chaque partie, les poids de
la fonction d'évaluation (WEIGHTS dans memoire.json) sont mis à jour via
learn_from_position() puis sauvegardés sur disque.

Flux d'une partie :
    1. Création de deux JoueurIAHeadless (blancs et noirs).
    2. Boucle de jeu : chaque IA calcule son coup via ia_move(),
       en utilisant la profondeur adaptée à la phase de jeu.
    3. Les coups importants (captures, promotions, échecs) sont stockés
       au fur et à mesure (fen + move_uci).
    4. Fin de partie : le résultat final (1 / 0 / -1) est connu.
       learn_from_position() est appelée sur chaque coup stocké avec
       ce résultat → l'apprentissage utilise la vraie issue de la partie.
    5. save_memoire() écrit les WEIGHTS modifiés dans memoire.json.

Arrêt propre :
    Ctrl+C déclenche KeyboardInterrupt, capturé pour forcer une dernière
    sauvegarde avant de quitter et afficher le bilan final.

Usage :
    python training.py          # boucle infinie
"""

import time
import chess
from IA_LA_VRAIE import ia_move, learn_from_position, est_coup_important, get_game_phase, get_depth_for_phase
from gestion_memoire import save_memoire
from zobrist import creer_TT, creer_zobrist

# ── Constantes ────────────────────────────────────────────────────────────────
TT_MAX_SIZE = 150_000
"""Nombre maximum d'entrées dans la table de transposition avant nettoyage."""

MAX_MOVES = 300
"""
Limite de coups par partie. Au-delà, la partie est déclarée nulle
pour éviter les boucles infinies en cas de positions répétitives.
"""


class JoueurIAHeadless:
    """
    Version allégée du JoueurIA de main.py, sans aucune dépendance Tkinter.

    Encapsule une table de transposition et des tables Zobrist propres à
    chaque instance (les deux IA ne partagent pas leur TT).

    Attributs
    ----------
    board : chess.Board
        Référence au plateau partagé de la partie en cours.
    couleur : bool
        chess.WHITE ou chess.BLACK.
    TT : dict
        Table de transposition (cache des positions évaluées).
    ZP, ZR, ZE, ZT, IP
        Tables Zobrist générées à l'initialisation.
    coups_importants : list[tuple[str, str]]
        Liste de (fen, move_uci) pour les coups importants joués.
        Utilisée après la partie pour l'apprentissage avec le vrai résultat.
    """

    def __init__(self, board: chess.Board, couleur: bool):
        """
        Initialise le joueur IA headless.

        Paramètres
        ----------
        board : chess.Board
            Plateau de jeu partagé entre les deux joueurs.
        couleur : bool
            chess.WHITE ou chess.BLACK.
        """
        self.board   = board
        self.couleur = couleur
        self.TT      = creer_TT()
        self.ZP, self.ZR, self.ZE, self.ZT, self.IP = creer_zobrist()
        self.coups_importants = []

    def _nettoyer_TT(self) -> None:
        """
        Supprime la moitié des entrées de la TT si elle dépasse TT_MAX_SIZE.

        Évite une consommation mémoire illimitée sur de longues sessions
        d'entraînement. Les entrées supprimées sont les plus anciennes
        (ordre d'insertion du dict Python).
        """
        if len(self.TT) > TT_MAX_SIZE:
            cles = list(self.TT.keys())
            for cle in cles[:len(cles) // 2]:
                del self.TT[cle]

    def coup(self) -> chess.Move:
        """
        Calcule et retourne le meilleur coup pour la position courante.

        La profondeur de recherche est déterminée dynamiquement par
        get_game_phase() + get_depth_for_phase(), ce qui adapte l'effort
        de calcul à la phase de jeu (ouverture → fin de partie).

        Les coups importants (capture, promotion, échec, mat) sont
        enregistrés dans coups_importants pour l'apprentissage différé.

        Retourne
        --------
        chess.Move
            Meilleur coup trouvé, ou un coup aléatoire si ia_move retourne None
            (ne devrait pas arriver en pratique).
        """
        self._nettoyer_TT()
        phase      = get_game_phase(self.board)
        profondeur = get_depth_for_phase(phase)

        move = ia_move(
            self.TT, self.board, profondeur,
            self.ZP, self.ZR, self.ZE, self.ZT, self.IP
        )

        if move is None:
            import random
            move = random.choice(list(self.board.legal_moves))

        if est_coup_important(self.board, move):
            self.coups_importants.append((self.board.fen(), move.uci()))

        return move


def jouer_partie(numero: int) -> int:
    """
    Joue une partie complète IA vs IA et déclenche l'apprentissage.

    Étapes :
        1. Initialisation du plateau et des deux IA.
        2. Boucle jusqu'à fin de partie ou MAX_MOVES coups.
        3. Détermination du résultat (1 / 0 / -1).
        4. Apprentissage : learn_from_position() sur chaque coup important
           des deux IA, avec le résultat final comme cible.
        5. Sauvegarde immédiate de memoire.json.

    Paramètres
    ----------
    numero : int
        Numéro de la partie (pour l'affichage console).

    Retourne
    --------
    int
        1  si les blancs gagnent,
        -1 si les noirs gagnent,
        0  en cas de nulle ou de partie tronquée (MAX_MOVES).
    """
    board    = chess.Board()
    ia_blanc = JoueurIAHeadless(board, chess.WHITE)
    ia_noir  = JoueurIAHeadless(board, chess.BLACK)

    nb_coups = 0
    debut    = time.time()

    while not board.is_game_over():
        if nb_coups >= MAX_MOVES:
            print(f"Limite de {MAX_MOVES} coups atteinte — nulle")
            break

        ia   = ia_blanc if board.turn == chess.WHITE else ia_noir
        move = ia.coup()
        board.push(move)
        nb_coups += 1

    res_str = board.result()
    if res_str == "1-0":
        result, label = 1,  "Blancs gagnent"
    elif res_str == "0-1":
        result, label = -1, "Noirs gagnent"
    else:
        result, label = 0,  "Nulle"

    duree = time.time() - debut
    print(f"  Partie {numero:>4} | {nb_coups:>3} coups | {duree:>5.1f}s | {label}")

    # Apprentissage avec le VRAI résultat final
    for ia in (ia_blanc, ia_noir):
        for fen, move_uci in ia.coups_importants:
            b = chess.Board(fen)
            learn_from_position(b, result, chess.Move.from_uci(move_uci))

    # Sauvegarde à chaque partie
    save_memoire()

    return result


def entrainement() -> None:
    """
    Lance des parties en boucle infinie jusqu'à l'arrêt par Ctrl+C.

    Affiche un bilan (victoires blancs / noirs / nulles) toutes les 10 parties.
    En cas d'interruption (KeyboardInterrupt), effectue une dernière sauvegarde
    de memoire.json avant de quitter proprement.
    """
    stats = {"1-0": 0, "0-1": 0, "nulle": 0}
    i     = 0

    print(f"\n{'═'*55}")
    print(f"ENTRAÎNEMENT HEADLESS — boucle infinie")
    print(f"  Arrêt propre : Ctrl+C")
    print(f"{'═'*55}\n")

    debut_total = time.time()

    try:
        while True:
            i     += 1
            result = jouer_partie(i)

            if result == 1:
                stats["1-0"] += 1
            elif result == -1:
                stats["0-1"] += 1
            else:
                stats["nulle"] += 1

            # Bilan intermédiaire tous les 10 parties
            if i % 10 == 0:
                total = stats["1-0"] + stats["0-1"] + stats["nulle"]
                duree = time.time() - debut_total
                print(f"\n  Bilan après {i} parties ({duree/60:.1f} min) :")
                print(f"     Blancs : {stats['1-0']:>4} ({100*stats['1-0']//total:>3}%)")
                print(f"     Noirs  : {stats['0-1']:>4} ({100*stats['0-1']//total:>3}%)")
                print(f"     Nulles : {stats['nulle']:>4} ({100*stats['nulle']//total:>3}%)\n")

    except KeyboardInterrupt:
        print(f"\n\n  Arrêt demandé — sauvegarde en cours...")
        save_memoire()

        duree_totale = time.time() - debut_total
        total        = max(i, 1)
        print(f"\n{'═'*55}")
        print(f"  ENTRAÎNEMENT ARRÊTÉ après {i} parties ({duree_totale/60:.1f} min)")
        print(f"  Résultats finaux :")
        print(f"     Blancs : {stats['1-0']:>4} ({100*stats['1-0']//total:>3}%)")
        print(f"     Noirs  : {stats['0-1']:>4} ({100*stats['0-1']//total:>3}%)")
        print(f"     Nulles : {stats['nulle']:>4} ({100*stats['nulle']//total:>3}%)")
        print(f"{'═'*55}\n")


if __name__ == "__main__":
    entrainement()

