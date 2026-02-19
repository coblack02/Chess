import json
import os
import chess

MEMOIRE_FILE = "memoire.json"

if os.path.exists(MEMOIRE_FILE):
    with open(MEMOIRE_FILE, "r") as f:
        memoire = json.load(f)

VALEURS_PIECES = {getattr(chess, k): v for k, v in memoire["VALEURS_PIECES"].items()}
PIECE_MAP = {
    "PAWN": chess.PAWN,
    "KNIGHT": chess.KNIGHT,
    "BISHOP": chess.BISHOP,
    "ROOK": chess.ROOK,
    "QUEEN": chess.QUEEN,
    "KING": chess.KING
}

TABLES = {
    PIECE_MAP[k]: v
    for k, v in memoire["TABLES_POSITION"].items()
}

MOBILITY_MULTIPLIER = memoire.get("MOBILITY_MULTIPLIER", 5)
PIN_PENALTY = memoire.get("PIN_PENALTY", 25)
TEMPO_BONUS = memoire.get("TEMPO_BONUS", 10)
WEIGHTS = memoire.get("WEIGHTS", {"material": 1.0, "psqt": 1.0, "mobility": 5.0})

def save_memoire():
    memoire["WEIGHTS"] = WEIGHTS
    memoire["VALEURS_PIECES"] = {
        chess.piece_name(k).upper(): v for k, v in VALEURS_PIECES.items()
    }
    memoire["TABLES_POSITION"] = {
        chess.piece_name(k).upper(): v for k, v in TABLES.items()
    }

    with open(MEMOIRE_FILE, "w") as f:
        json.dump(memoire, f, indent=4)
