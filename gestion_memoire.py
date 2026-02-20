"""
gestion_memoire.py
==================
Chargement et sauvegarde des paramètres persistants de l'IA dans memoire.json.

Ce module est le point central de configuration de l'IA. Il expose les
variables globales utilisées par IA_LA_VRAIE.py :

    VALEURS_PIECES   : valeur matérielle de chaque type de pièce (en centipions).
    TABLES           : tables de bonus de position (piece-square tables, PST).
    MOBILITY_MULTIPLIER, PIN_PENALTY, TEMPO_BONUS : paramètres legacy conservés.
    WEIGHTS          : poids de chaque feature dans la fonction d'évaluation.
                       C'est le seul dictionnaire modifié par le learning.
    PROFONDEURS      : profondeur de recherche alpha-beta par phase de jeu.

Sécurité anti-explosion :
    WEIGHT_CLAMP (50.0) borne les poids au chargement ET à la sauvegarde.
    Si un poids dépasse cette borne au chargement, tout WEIGHTS est remis
    aux valeurs DEFAULT_WEIGHTS, évitant qu'un training instable corrompe
    définitivement le fichier.

Flux typique :
    1. Import du module → load_memoire() appelé → variables globales initialisées.
    2. IA_LA_VRAIE.learn_from_position() modifie WEIGHTS en mémoire.
    3. training.py appelle save_memoire() après chaque partie →
       les WEIGHTS globaux (modifiés) sont écrits dans le JSON.
"""

import json
import os
import chess

MEMOIRE_FILE = "memoire.json"

if os.path.exists(MEMOIRE_FILE):
    with open(MEMOIRE_FILE, "r") as f:
        memoire = json.load(f)

# Valeur absolue maximale autorisée pour un poids.
# Au-delà → le learning a divergé, on reset tout.
WEIGHT_CLAMP = 50.0

# Poids par défaut utilisés en cas de reset ou de JSON manquant.
DEFAULT_WEIGHTS = {
    "material":       1.0,
    "psqt":           1.0,
    "mobility":       0.1,
    "pawn_structure": 1.0,
    "king_safety":    1.0,
    "rook_open_file": 1.0,
    "bishop_pair":    1.0,
}


def _sane_weights(weights: dict) -> dict:
    """
    Vérifie que les poids ne sont pas explosés et les remet à zéro si besoin.

    Un poids est considéré explosé si sa valeur absolue dépasse WEIGHT_CLAMP.
    Dans ce cas, TOUS les poids sont remplacés par DEFAULT_WEIGHTS pour repartir
    d'un état sain (un reset partiel laisserait des incohérences entre features).

    Paramètres
    ----------
    weights : dict
        Dictionnaire feature_name → float à vérifier.

    Retourne
    --------
    dict
        Le dictionnaire original si tout est sain, DEFAULT_WEIGHTS sinon.
    """
    for v in weights.values():
        if abs(v) > WEIGHT_CLAMP:
            print(f" Poids explosé détecté ({v:.2e}) → reset des WEIGHTS aux valeurs par défaut")
            return dict(DEFAULT_WEIGHTS)
    return weights


def load_memoire():
    """
    Charge et retourne tous les paramètres depuis le fichier memoire.json.

    Convertit les clés textuelles du JSON (ex. "PAWN") en constantes
    python-chess (ex. chess.PAWN) pour un accès direct dans le code.
    Applique _sane_weights() sur WEIGHTS avant de les retourner.

    Retourne
    --------
    VALEURS_PIECES : dict[int, float]
        {chess.PAWN: 100, chess.KNIGHT: 320, ...}
    TABLES : dict[int, list[float]]
        {chess.PAWN: [64 valeurs], chess.KNIGHT: [64 valeurs], ...}
    MOBILITY_MULTIPLIER : float
        Multiplicateur de mobilité (legacy).
    PIN_PENALTY : float
        Pénalité pour pièce clouée (legacy).
    TEMPO_BONUS : float
        Bonus de tempo (legacy).
    WEIGHTS : dict[str, float]
        Poids des features d'évaluation, bornés par WEIGHT_CLAMP.
    PROFONDEURS : dict[str, int]
        Profondeur de recherche par phase :
        {'ouverture': 4, 'milieu': 5, 'fin': 6, 'finfin': 9}
    """
    VALEURS_PIECES = {getattr(chess, k): v for k, v in memoire["VALEURS_PIECES"].items()}

    PIECE_MAP = {
        "PAWN":   chess.PAWN,
        "KNIGHT": chess.KNIGHT,
        "BISHOP": chess.BISHOP,
        "ROOK":   chess.ROOK,
        "QUEEN":  chess.QUEEN,
        "KING":   chess.KING,
    }

    TABLES = {
        PIECE_MAP[k]: v
        for k, v in memoire["TABLES_POSITION"].items()
    }

    MOBILITY_MULTIPLIER = memoire.get("MOBILITY_MULTIPLIER", 5)
    PIN_PENALTY         = memoire.get("PIN_PENALTY", 25)
    TEMPO_BONUS         = memoire.get("TEMPO_BONUS", 10)

    raw_weights = memoire.get("WEIGHTS", dict(DEFAULT_WEIGHTS))
    WEIGHTS     = _sane_weights(raw_weights)

    PROFONDEURS = memoire.get("PROFONDEUR", {
        "ouverture": 4,
        "milieu":    5,
        "fin":       6,
        "finfin":    9,
    })

    return VALEURS_PIECES, TABLES, MOBILITY_MULTIPLIER, PIN_PENALTY, TEMPO_BONUS, WEIGHTS, PROFONDEURS


# ── Variables globales chargées au démarrage ──────────────────────────────────
# WEIGHTS est le seul dictionnaire mutable : learn_from_position() le modifie
# en place. Les autres sont considérés comme des constantes en cours d'exécution.
VALEURS_PIECES, TABLES, MOBILITY_MULTIPLIER, PIN_PENALTY, TEMPO_BONUS, WEIGHTS, PROFONDEURS = load_memoire()


def save_memoire():
    """
    Écrit les variables globales courantes dans memoire.json.

    Utilise la variable globale WEIGHTS (potentiellement modifiée par
    learn_from_position) et NON les valeurs lues depuis le fichier.
    C'est ce qui permet au learning de persister entre les parties.

    Applique un clamp individuel sur chaque poids avant l'écriture :
    chaque valeur est bornée à [-WEIGHT_CLAMP, +WEIGHT_CLAMP] pour éviter
    qu'une divergence ponctuelle ne corrompe le fichier.

    Le fichier est réécrit en entier à chaque appel (indent=4 pour la
    lisibilité humaine).
    """
    weights_to_save = {
        k: max(-WEIGHT_CLAMP, min(WEIGHT_CLAMP, v))
        for k, v in WEIGHTS.items()
    }

    memoire["WEIGHTS"] = weights_to_save
    memoire["VALEURS_PIECES"] = {
        chess.piece_name(k).upper(): v for k, v in VALEURS_PIECES.items()
    }
    memoire["TABLES_POSITION"] = {
        chess.piece_name(k).upper(): v for k, v in TABLES.items()
    }
    memoire["PROFONDEUR"] = {
        "ouverture": PROFONDEURS.get("ouverture", 4),
        "milieu":    PROFONDEURS.get("milieu",    5),
        "fin":       PROFONDEURS.get("fin",       6),
        "finfin":    PROFONDEURS.get("finfin",    9),
    }

    with open(MEMOIRE_FILE, "w") as f:
        json.dump(memoire, f, indent=4) 
