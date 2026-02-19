import chess
import chess.polyglot


BOOK_PATH = "book.bin"

def polyglot_move(board):
    try:
        with chess.polyglot.open_reader(BOOK_PATH) as reader:
            entries = list(reader.find_all(board))
            if not entries:
                return None

            best = max(entries, key=lambda e: e.weight)
            return best.move
    except FileNotFoundError:
        return None
