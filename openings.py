"""
openings.py
===========
Consultation des livres d'ouverture au format Polyglot (.bin).

Ce module fournit une interface unifiée vers plusieurs livres d'ouverture.
Au lieu de suivre un seul livre de façon déterministe, il fusionne les
coups de tous les livres disponibles et effectue une sélection pondérée
aléatoire. Cela permet à l'IA de varier son jeu en ouverture et d'être
moins prévisible.

Livres utilisés (par ordre de priorité de lecture) :
    - gm2001.bin  : répertoire de parties de grands maîtres
    - rodent.bin  : livre de l'engine Rodent
    - komodo.bin  : livre de l'engine Komodo

Format Polyglot :
    Chaque entrée contient un coup et un poids (weight). Les coups avec
    un poids élevé sont des ouvertures très jouées / recommandées.
    La sélection pondérée reproduit ce comportement probabiliste.

Utilisation :
    move = polyglot_move(board)
    if move is not None:
        board.push(move)   # coup de livre
    else:
        # pas de coup dans les livres → calcul IA normal
"""

import chess
import chess.polyglot
import random

# Chemins vers les fichiers de livre d'ouverture Polyglot.
# Les fichiers manquants sont ignorés silencieusement (avertissement console).
BOOK_PATHS = [
    "gm2001.bin",
    "rodent.bin",
    "komodo.bin",
]


def polyglot_move(board: chess.Board):
    """
    Retourne un coup issu des livres d'ouverture pour la position donnée.

    Algorithme :
        1. Parcourt chaque livre de BOOK_PATHS.
        2. Collecte tous les coups trouvés et cumule leurs poids
           (si un coup apparaît dans plusieurs livres, les poids s'additionnent).
        3. Effectue une sélection pondérée aléatoire parmi les coups collectés.
           Un coup avec weight=100 a deux fois plus de chances d'être choisi
           qu'un coup avec weight=50.
        4. Retourne None si aucun livre ne contient de coup pour cette position.

    La sélection pondérée garantit que l'IA joue principalement les
    ouvertures "recommandées" tout en conservant une variabilité naturelle.

    Paramètres
    ----------
    board : chess.Board
        Position courante pour laquelle chercher un coup de livre.

    Retourne
    --------
    chess.Move ou None
        Coup sélectionné, ou None si la position est hors du répertoire
        de tous les livres.
    """
    all_entries = {}  # move_uci (str) → (chess.Move, poids cumulé)

    for book_path in BOOK_PATHS:
        try:
            with chess.polyglot.open_reader(book_path) as reader:
                for entry in reader.find_all(board):
                    key = entry.move.uci()
                    if key in all_entries:
                        all_entries[key] = (entry.move, all_entries[key][1] + entry.weight)
                    else:
                        all_entries[key] = (entry.move, entry.weight)
        except FileNotFoundError:
            print(f"  Livre introuvable : {book_path}")
        except Exception as e:
            print(f"  Erreur lecture {book_path} : {e}")

    if not all_entries:
        return None

    entries = list(all_entries.values())   # liste de (chess.Move, poids)
    total   = sum(w for _, w in entries)

    if total == 0:
        # Tous les poids sont nuls → sélection uniforme
        return random.choice(entries)[0]

    # Sélection pondérée par roulette
    r     = random.randint(0, total - 1)
    cumul = 0
    for move, weight in entries:
        cumul += weight
        if r < cumul:
            return move

    return entries[-1][0]   # fallback de sécurité (ne devrait pas arriver)
