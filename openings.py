import chess
import chess.polyglot
import random

# Les 4 livres d'ouverture, dans l'ordre de priorité
BOOK_PATHS = [
    "gm2001.bin",
    "rodent.bin",
    "komodo.bin"
]

def polyglot_move(board):
    """
    Retourne un coup du livre d'ouverture pour la position donnée.
    Consulte les 4 livres et fusionne tous les coups trouvés.
    Utilise une sélection pondérée aléatoire pour varier le jeu.
    Retourne None si aucun coup n'est trouvé dans aucun livre.
    """
    all_entries = {}  # move_uci -> poids cumulé

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
            print(f" Livre introuvable : {book_path}")
        except Exception as e:
            print(f"  Erreur lecture {book_path} : {e}")

    if not all_entries:
        return None

    entries = list(all_entries.values())  # liste de (move, poids)
    total = sum(w for _, w in entries)

    if total == 0:
        return random.choice(entries)[0]

    # Sélection pondérée
    r = random.randint(0, total - 1)
    cumul = 0
    for move, weight in entries:
        cumul += weight
        if r < cumul:
            return move

    return entries[-1][0]  # fallback
