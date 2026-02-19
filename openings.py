import chess
import chess.polyglot
import random

BOOK_PATH = "komodo.bin"

def polyglot_move(board):
    """
    Retourne un coup du livre d'ouverture pour la position donnée.
    Utilise une sélection pondérée aléatoire parmi les coups disponibles
    pour varier le jeu entre les parties (plutôt que toujours le même coup).
    Retourne None si aucun coup n'est trouvé ou si le fichier est absent.
    """
    try:
        with chess.polyglot.open_reader(BOOK_PATH) as reader:
            entries = list(reader.find_all(board))
            if not entries:
                return None

            # Sélection pondérée : les coups avec un poids élevé sont
            # favorisés mais pas toujours choisis → variété entre parties
            total = sum(e.weight for e in entries)
            if total == 0:
                return random.choice(entries).move

            r     = random.randint(0, total - 1)
            cumul = 0
            for e in entries:
                cumul += e.weight
                if r < cumul:
                    return e.move

            return entries[-1].move  # fallback

    except FileNotFoundError:
        return None
    except Exception:
        return None
