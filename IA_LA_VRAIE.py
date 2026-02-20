"""
IA_LA_VRAIE.py
==============
Moteur de recherche alpha-beta et fonction d'évaluation de l'IA d'échecs.

Ce module contient trois grandes parties :

1. Détection de phase (get_game_phase, get_depth_for_phase)
   Analyse le matériel restant sur le plateau pour déterminer la phase
   de jeu (ouverture / milieu / fin / finfin) et adapter la profondeur.

2. Évaluation (extract_features, evaluate, learn_from_position)
   Système extensible de features pondérées. Chaque feature est une
   fonction indépendante qui retourne un score du point de vue du joueur
   EN TRAIT. Les poids sont stockés dans memoire.json et mis à jour par
   apprentissage supervisé (descente de gradient avec normalisation sigmoïde).

   Pour ajouter une feature :
       a. Écrire _feature_montruc(board) → float
       b. L'ajouter dans FEATURE_FUNCTIONS
       c. Ajouter sa clé dans WEIGHTS (memoire.json), ex: "montruc": 1.0

3. Recherche (mvv_lva, quiescence, alpha_beta, ia_move)
   Alpha-beta negamax avec :
       - Iterative Deepening
       - Aspiration Windows
       - Null Move Pruning (NMP)
       - Killer Moves
       - History Heuristic
       - Quiescence Search (MVV-LVA)
       - Table de transposition (Zobrist hashing incrémental)
       - Livre d'ouverture Polyglot (prioritaire sur le calcul)

Constantes de flag TT :
    EXACT      = 0  : score exact
    LOWERBOUND = 1  : borne inférieure (alpha)
    UPPERBOUND = 2  : borne supérieure (beta)
"""

import chess
from zobrist import *
from openings import polyglot_move
from gestion_memoire import *
import time

EXACT      = 0
"""Flag TT : le score stocké est exact."""
LOWERBOUND = 1
"""Flag TT : borne inférieure — le vrai score est >= valeur stockée."""
UPPERBOUND = 2
"""Flag TT : borne supérieure — le vrai score est <= valeur stockée."""

# ══════════════════════════════════════════════════════════════════════════════
# DÉTECTION DE PHASE
# ══════════════════════════════════════════════════════════════════════════════

def get_game_phase(board: chess.Board) -> str:
    """
    Détecte la phase de jeu en comptant le matériel non-pion restant.

    Seuls les cavaliers, fous, tours et dames sont comptés (pas les rois
    ni les pions), car ce sont les pièces mineures/majeures dont la disparition
    marque les transitions de phase.

    Seuils (valeur totale des deux camps) :
        >= 5800 → 'ouverture'   (ex. toutes pièces présentes ≈ 7800)
        >= 3200 → 'milieu'      (quelques échanges effectués)
        >= 1300 → 'fin'         (majorité des pièces échangées)
        <  1300 → 'finfin'      (finale pure : tours/fous/cavaliers seuls)

    Paramètres
    ----------
    board : chess.Board
        Position courante.

    Retourne
    --------
    str
        Une des quatre valeurs : 'ouverture', 'milieu', 'fin', 'finfin'.
    """
    material = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue
        if piece.piece_type in (chess.KING, chess.PAWN):
            continue
        material += VALEURS_PIECES[piece.piece_type]

    if material >= 5800:
        return "ouverture"
    elif material >= 3200:
        return "milieu"
    elif material >= 1300:
        return "fin"
    else:
        return "finfin"


def get_depth_for_phase(phase: str) -> int:
    """
    Retourne la profondeur de recherche alpha-beta pour une phase de jeu.

    Les profondeurs sont configurables dans memoire.json (clé "PROFONDEUR").
    Valeurs par défaut : ouverture=4, milieu=5, fin=6, finfin=9.

    Paramètres
    ----------
    phase : str
        Phase retournée par get_game_phase() :
        'ouverture', 'milieu', 'fin' ou 'finfin'.

    Retourne
    --------
    int
        Profondeur maximale de recherche en demi-coups (plies).
    """
    return PROFONDEURS[phase]


# ══════════════════════════════════════════════════════════════════════════════
# TABLES DE POSITION
# ══════════════════════════════════════════════════════════════════════════════

def get_position_value(piece_type: int, square: int, color: bool) -> float:
    """
    Retourne le bonus de position d'une pièce sur une case donnée.

    Les tables (piece-square tables) sont stockées du point de vue des blancs
    (rang 8 en index 0). Pour les noirs, on inverse avec XOR 56 afin d'avoir
    une symétrie parfaite par rapport à l'axe horizontal.

    Paramètres
    ----------
    piece_type : int
        Constante chess.PAWN, chess.KNIGHT, etc.
    square : int
        Case de 0 (a1) à 63 (h8) au format python-chess.
    color : bool
        chess.WHITE ou chess.BLACK.

    Retourne
    --------
    float
        Bonus de position en centipions (peut être négatif).
    """
    table = TABLES[piece_type]
    return table[square ^ 56] if color == chess.WHITE else table[square]


# ══════════════════════════════════════════════════════════════════════════════
# EXTRACTION DE FEATURES — SYSTÈME EXTENSIBLE
# ══════════════════════════════════════════════════════════════════════════════
#
# Pour ajouter une nouvelle feature :
#   1. Ajouter la clé dans WEIGHTS (memoire.json), ex: "pawn_structure": 1.0
#   2. Écrire une fonction  _feature_<nom>(board) -> float  (positif = bon pour le joueur EN TRAIT)
#   3. L'enregistrer dans FEATURE_FUNCTIONS ci-dessous.
#
# C'est tout. evaluate() et learn_from_position() s'adaptent automatiquement.
# ─────────────────────────────────────────────────────────────────────────────

def _feature_material(board: chess.Board) -> float:
    """
    Calcule l'avantage matériel du joueur EN TRAIT.

    Somme algébrique des valeurs de toutes les pièces :
    pièces du joueur en trait comptées positivement,
    pièces adverses négativement.

    Retourne
    --------
    float
        Différence de matériel en centipions.
        Positif = avantage pour le joueur en trait.
    """
    score = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue
        sign = 1 if piece.color == board.turn else -1
        score += sign * VALEURS_PIECES[piece.piece_type]
    return score


def _feature_psqt(board: chess.Board) -> float:
    """
    Calcule le bonus de position global (Piece-Square Tables) du joueur EN TRAIT.

    Pour chaque pièce sur le plateau, lit son bonus de position dans la table
    correspondante (TABLES). Les pièces du joueur en trait sont comptées
    positivement, les adverses négativement.

    Retourne
    --------
    float
        Score positionnel net en centipions.
        Positif = meilleures positions pour le joueur en trait.
    """
    score = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None:
            continue
        sign = 1 if piece.color == board.turn else -1
        score += sign * get_position_value(piece.piece_type, square, piece.color)
    return score


def _feature_mobility(board: chess.Board) -> float:
    """
    Retourne le nombre de coups légaux du joueur EN TRAIT.

    La mobilité est un indicateur de liberté d'action et d'activité des pièces.
    Plus un joueur a de coups disponibles, plus ses pièces sont actives.

    Note : cette feature est symétrique — elle ne mesure que la mobilité
    du joueur au trait, pas la différence avec l'adversaire.

    Retourne
    --------
    float
        Nombre de coups légaux (toujours >= 0, sauf mat/pat détectés avant).
    """
    return len(list(board.legal_moves))


def _feature_pawn_structure(board: chess.Board) -> float:
    """
    Évalue la structure de pions des deux camps.

    Critères pris en compte :
        - Pions doublés  : plusieurs pions sur la même colonne → pénalité -20.
        - Pions isolés   : aucun pion ami sur les colonnes adjacentes → pénalité -15.
        - Pions passés   : aucun pion adverse devant lui sur sa colonne
                           ni les colonnes adjacentes → bonus croissant avec
                           l'avancement (plus fort en fin de partie).

    Le bonus des pions passés est amplifié en phase 'fin' et 'finfin' car
    un pion passé avancé est quasi décisif dans les finales.

    Retourne
    --------
    float
        Score de structure nette du point de vue du joueur en trait.
        Positif = meilleure structure pour le joueur en trait.
    """
    phase = get_game_phase(board)
    score = 0

    for color in (board.turn, not board.turn):
        sign             = 1 if color == board.turn else -1
        pawns            = board.pieces(chess.PAWN, color)
        files_with_pawns = [chess.square_file(sq) for sq in pawns]

        for sq in pawns:
            f         = chess.square_file(sq)
            r         = chess.square_rank(sq)
            neighbors = [c for c in (f - 1, f + 1) if 0 <= c <= 7]

            if files_with_pawns.count(f) > 1:
                score -= sign * 20

            if not any(c in files_with_pawns for c in neighbors):
                score -= sign * 15

            enemy_pawns = board.pieces(chess.PAWN, not color)
            blocked = any(
                chess.square_file(eq) in ([f] + neighbors)
                and ((color == chess.WHITE and chess.square_rank(eq) > r)
                     or (color == chess.BLACK and chess.square_rank(eq) < r))
                for eq in enemy_pawns
            )

            if not blocked:
                advance = r if color == chess.WHITE else (7 - r)
                if phase in ("fin", "finfin"):
                    score += sign * (20 + advance * 20)
                else:
                    score += sign * (10 + advance * 8)

    return score


def _feature_king_safety(board: chess.Board) -> float:
    """
    Évalue la sécurité du roi, adaptée à la phase de jeu.

    Ouverture / milieu de partie :
        Pénalise le roi exposé (peu de pions boucliers devant lui).
        Chaque pion manquant dans les 2 rangées devant le roi coûte -18.
        Maximum -54 si le roi n'a aucun bouclier.

    Fin de partie :
        Le roi doit être actif, pas caché.
        Bonus pour la proximité au centre (roi centralisé).
        Si on a l'avantage matériel : bonus supplémentaire si le roi
        s'approche du roi adverse (pour forcer le mat).
        Si on est en désavantage : bonus si le roi s'éloigne du roi
        adverse (pour maximiser les chances de nulle).

    Retourne
    --------
    float
        Score de sécurité/activité du roi, du point de vue du joueur en trait.
    """
    phase    = get_game_phase(board)
    score    = 0
    king_w   = board.king(chess.WHITE)
    king_b   = board.king(chess.BLACK)

    for color in (board.turn, not board.turn):
        sign    = 1 if color == board.turn else -1
        king_sq = board.king(color)
        if king_sq is None:
            continue

        kf = chess.square_file(king_sq)
        kr = chess.square_rank(king_sq)

        if phase in ("ouverture", "milieu"):
            shield        = 0
            shield_ranks  = [kr + 1, kr + 2] if color == chess.WHITE else [kr - 1, kr - 2]
            shield_files  = [f for f in (kf - 1, kf, kf + 1) if 0 <= f <= 7]
            for sq in board.pieces(chess.PAWN, color):
                if chess.square_file(sq) in shield_files and chess.square_rank(sq) in shield_ranks:
                    shield += 1
            score -= sign * (3 - min(shield, 3)) * 18

        else:
            center_dist = abs(kf - 3.5) + abs(kr - 3.5)
            score += sign * int((7 - center_dist) * 8)

            if king_w is not None and king_b is not None:
                enemy_king = king_b if color == chess.WHITE else king_w
                ekf        = chess.square_file(enemy_king)
                ekr        = chess.square_rank(enemy_king)
                dist_kings = abs(kf - ekf) + abs(kr - ekr)

                my_material = sum(
                    VALEURS_PIECES[p.piece_type]
                    for sq in chess.SQUARES
                    for p in [board.piece_at(sq)]
                    if p and p.color == color and p.piece_type != chess.KING
                )
                enemy_material = sum(
                    VALEURS_PIECES[p.piece_type]
                    for sq in chess.SQUARES
                    for p in [board.piece_at(sq)]
                    if p and p.color != color and p.piece_type != chess.KING
                )

                if my_material >= enemy_material:
                    score += sign * (14 - dist_kings) * 5
                else:
                    score += sign * dist_kings * 3

    return score


def _feature_rook_open_file(board: chess.Board) -> float:
    """
    Évalue le placement des tours sur colonnes ouvertes ou semi-ouvertes.

    Une colonne est :
        - Ouverte      : aucun pion (ni ami ni adverse) → bonus +20.
        - Semi-ouverte : pas de pion ami mais un pion adverse → bonus +10.
                         (la tour peut exercer une pression sur le pion ennemi)

    Retourne
    --------
    float
        Score des tours du joueur en trait moins celui de l'adversaire.
    """
    score = 0
    for color in (board.turn, not board.turn):
        sign = 1 if color == board.turn else -1
        for sq in board.pieces(chess.ROOK, color):
            f              = chess.square_file(sq)
            own_pawn_on_f  = any(chess.square_file(p) == f for p in board.pieces(chess.PAWN, color))
            enemy_pawn_on_f = any(chess.square_file(p) == f for p in board.pieces(chess.PAWN, not color))
            if not own_pawn_on_f and not enemy_pawn_on_f:
                score += sign * 20
            elif not own_pawn_on_f:
                score += sign * 10
    return score


def _feature_bishop_pair(board: chess.Board) -> float:
    """
    Attribue un bonus pour la possession de la paire de fous.

    La paire de fous (deux fous de couleurs opposées) est généralement
    considérée comme un avantage stratégique dans les positions ouvertes
    ou semi-ouvertes, car les deux fous couvrent l'ensemble du plateau.

    Retourne
    --------
    float
        +30 si le joueur en trait a la paire, -30 si c'est l'adversaire,
        0 si les deux ou aucun ne l'ont.
    """
    score = 0
    for color in (board.turn, not board.turn):
        sign = 1 if color == board.turn else -1
        if len(board.pieces(chess.BISHOP, color)) >= 2:
            score += sign * 30
    return score



# ─────────────────────────────────────────────────────────────────────────────
# Registre des features  →  clé dans WEIGHTS : fonction(board)
# Pour EN AJOUTER UNE : ajoutez juste une ligne ici + la clé dans memoire.json
# ─────────────────────────────────────────────────────────────────────────────
FEATURE_FUNCTIONS = {
    "material":        _feature_material,
    "psqt":            _feature_psqt,
    "mobility":        _feature_mobility,
    "pawn_structure":  _feature_pawn_structure,
    "king_safety":     _feature_king_safety,
    "rook_open_file":  _feature_rook_open_file,
    "bishop_pair":     _feature_bishop_pair,
}


def extract_features(board: chess.Board) -> dict:
    """
    Calcule toutes les features actives pour une position donnée.

    Seules les features dont la clé est présente dans WEIGHTS (memoire.json)
    sont calculées — les autres sont ignorées. Cela permet d'activer ou de
    désactiver une feature simplement en l'ajoutant ou la retirant du JSON,
    sans modifier le code.

    Paramètres
    ----------
    board : chess.Board
        Position à évaluer.

    Retourne
    --------
    dict[str, float]
        Dictionnaire feature_name → valeur numérique.
        Ex. : {'material': 150, 'psqt': 40, 'mobility': 28, ...}
    """
    features = {}
    for key, fn in FEATURE_FUNCTIONS.items():
        if key in WEIGHTS:
            features[key] = fn(board)
    return features


# ══════════════════════════════════════════════════════════════════════════════
# ÉVALUATION PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

def evaluate(board: chess.Board) -> float:
    """
    Retourne le score de la position du point de vue du joueur EN TRAIT.

    Convention negamax : un score positif est toujours favorable au joueur
    dont c'est le tour, quelle que soit sa couleur.

    Cas terminaux gérés en priorité :
        - Mat → -100 000 (le joueur en trait vient de perdre)
        - Pat / matériel insuffisant → 0 (nulle)
        - Répétition de position (≥ 2×) → pénalité pour éviter les boucles
          (plus forte en finale où la nulle est généralement mauvaise)

    Sinon : combinaison linéaire des features pondérées.

    Retourne
    --------
    float
        Score en centipions. Positif = avantageux pour le joueur en trait.
    """
    if board.is_checkmate():
        return -100_000
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    if board.is_repetition(2):
        phase = get_game_phase(board)
        if phase in ("fin", "finfin"):
            return -200
        return -80

    features = extract_features(board)
    score    = sum(WEIGHTS.get(k, 1.0) * v for k, v in features.items())
    return score


# ══════════════════════════════════════════════════════════════════════════════
# APPRENTISSAGE
# ══════════════════════════════════════════════════════════════════════════════

def _sigmoid(x: float, scale: float = 400.0) -> float:
    """
    Normalise un score brut d'évaluation vers l'intervalle [-1, +1].

    La sigmoïde centrée sur 0 permet de ramener des scores d'évaluation
    arbitrairement grands (centaines, milliers de centipions) à la même
    échelle que les résultats de partie (-1 / 0 / +1), rendant le calcul
    de l'erreur stable et borné.

    Formule : 2 / (1 + exp(-x / scale)) - 1

    Paramètres
    ----------
    x : float
        Score brut d'évaluation (en centipions).
    scale : float
        Facteur d'étirement. Avec scale=400 :
            x =  100 (pion d'avantage)  → ≈ +0.22
            x =  400                    → ≈ +0.76
            x = 1000                    → ≈ +0.98
            x →  ±∞                     → ±1

    Retourne
    --------
    float
        Valeur normalisée dans [-1, +1].
    """
    import math
    return 2.0 / (1.0 + math.exp(-x / scale)) - 1.0


def learn_from_position(board: chess.Board, result: int, coup: chess.Move = None, lr: float = 0.01) -> None:
    """
    Met à jour les poids WEIGHTS par descente de gradient (style TD-leaf).

    La cible est le résultat final de la partie (1 / 0 / -1).
    La prédiction est le score courant normalisé par sigmoïde → [-1, +1].
    L'erreur est donc bornée dans [-2, +2], ce qui stabilise l'apprentissage
    et évite l'explosion des poids (problème rencontré avec des scores bruts).

    Règle de mise à jour pour chaque poids w_k :
        w_k ← w_k + lr × (result - σ(score)) × feature_k

    Si le coup est important (capture, promotion, échec, mat), l'ajustement
    est doublé pour renforcer l'apprentissage sur les moments décisifs.

    Note : save_memoire() est appelée en fin de fonction. En pratique,
    training.py appelle learn_from_position plusieurs fois par partie
    (une par coup important) puis save_memoire() une fois à la fin de la
    partie — la sauvegarde dans cette fonction est donc redondante mais
    inoffensive.

    Paramètres
    ----------
    board : chess.Board
        Position à partir de laquelle les features sont calculées.
    result : int
        Résultat final de la partie du point de vue des blancs :
        1 = victoire blancs, -1 = victoire noirs, 0 = nulle.
    coup : chess.Move, optionnel
        Coup joué dans cette position (pour le double ajustement).
    lr : float
        Taux d'apprentissage. Valeur par défaut 0.01 adaptée à la
        normalisation sigmoïde (ordre de grandeur correct avec WEIGHT_CLAMP=50).
    """
    features   = extract_features(board)
    raw_score  = sum(WEIGHTS.get(k, 1.0) * v for k, v in features.items())
    prediction = _sigmoid(raw_score)
    error      = result - prediction

    for k in WEIGHTS:
        if k in features:
            WEIGHTS[k] += lr * error * features[k]

    if coup and est_coup_important(board, coup):
        for k in WEIGHTS:
            if k in features:
                WEIGHTS[k] += lr * error * features[k]

    save_memoire()


# ══════════════════════════════════════════════════════════════════════════════
# RECHERCHE
# ══════════════════════════════════════════════════════════════════════════════

def mvv_lva(board: chess.Board, move: chess.Move) -> int:
    """
    Score d'ordonnancement MVV-LVA (Most Valuable Victim - Least Valuable Attacker).

    Utilisé pour trier les captures dans alpha_beta et quiescence afin
    d'examiner d'abord les captures les plus prometteuses (gain de matériel
    maximal probable), ce qui améliore le pruning.

    Formule : 10 × valeur(victime) - valeur(attaquant)
    Ex. : Pion prend Dame → 10×900 - 100 = 8900 (très prioritaire)
          Dame prend Pion →  10×100 - 900 = 100  (peu prioritaire)

    Paramètres
    ----------
    board : chess.Board
        Position courante.
    move : chess.Move
        Coup à évaluer.

    Retourne
    --------
    int
        Score MVV-LVA (0 si le coup n'est pas une capture).
    """
    if not board.is_capture(move):
        return 0
    victim   = board.piece_at(move.to_square)
    attacker = board.piece_at(move.from_square)
    v = VALEURS_PIECES[victim.piece_type]   if victim   else 100
    a = VALEURS_PIECES[attacker.piece_type] if attacker else 100
    return 10 * v - a


def quiescence(board: chess.Board, alpha: float, beta: float, max_depth: int = 5) -> float:
    """
    Recherche de quiescence : étend la recherche sur les captures pour éviter
    l'effet horizon.

    Lorsque la recherche principale atteint depth=0, on ne s'arrête pas sur
    une position tactiquement instable. On continue en ne cherchant que les
    captures (triées par MVV-LVA) jusqu'à ce que la position soit calme
    (stand-pat) ou que max_depth soit atteint.

    Stand-pat : si le score statique de la position est déjà suffisant pour
    produire un cutoff (score >= beta), on retourne sans chercher davantage.

    Paramètres
    ----------
    board : chess.Board
        Position courante.
    alpha, beta : float
        Fenêtre alpha-beta courante.
    max_depth : int
        Profondeur maximale de la quiescence (défaut 5 plies supplémentaires).

    Retourne
    --------
    float
        Score de la position depuis le point de vue du joueur en trait.
    """
    stand_pat = evaluate(board)

    if stand_pat >= beta:
        return beta
    if alpha < stand_pat:
        alpha = stand_pat
    if max_depth == 0:
        return alpha

    captures = sorted(
        (m for m in board.legal_moves if board.is_capture(m)),
        key=lambda m: mvv_lva(board, m),
        reverse=True
    )

    for move in captures:
        board.push(move)
        score = -quiescence(board, -beta, -alpha, max_depth - 1)
        board.pop()

        if score >= beta:
            return beta
        if score > alpha:
            alpha = score

    return alpha


def alpha_beta(TT, board, depth, alpha, beta,
               ZP, ZR, ZE, ZT, IP, cle,
               killers, history, null_allowed=True):
    """
    Recherche alpha-beta negamax avec toutes les optimisations.

    Optimisations implémentées :
        Table de transposition (TT) :
            Avant de chercher, vérifie si la position a déjà été évaluée
            à une profondeur >= depth. Utilise le flag (EXACT/LOWER/UPPER)
            pour affiner les bornes ou retourner directement.

        Null Move Pruning (NMP) :
            Si le joueur "passe son tour" (coup nul) et que le score reste
            >= beta malgré ce désavantage, la position est probablement si
            bonne qu'on peut couper (réduction R=2). Désactivé en échec et
            si le joueur n'a que des pions/roi (risque de zugzwang).

        Killer Moves :
            Mémorise les 2 derniers coups non-captures qui ont produit un
            cutoff à chaque profondeur. Ces coups sont testés en priorité.

        History Heuristic :
            Compteur (couleur, from, to) incrémenté de depth² pour les coups
            qui améliorent alpha. Influence l'ordre d'exploration.

        Ordonnancement des coups :
            1. Captures triées MVV-LVA (+5000)
            2. Promotions (+4000 + valeur pièce)
            3. Killer moves (+2000)
            4. History score

    Paramètres
    ----------
    TT : dict
        Table de transposition.
    board : chess.Board
        Position courante.
    depth : int
        Profondeur restante (0 → quiescence).
    alpha, beta : float
        Fenêtre de recherche courante.
    ZP, ZR, ZE, ZT, IP
        Tables Zobrist (voir zobrist.py).
    cle : int
        Hash Zobrist de la position courante (mis à jour incrémentalement).
    killers : list[set]
        killers[d] = ensemble des 2 coups tueurs à la profondeur d.
    history : dict
        history[(couleur, from, to)] = score cumulé.
    null_allowed : bool
        False pour désactiver NMP sur le coup suivant un coup nul.

    Retourne
    --------
    float
        Score de la position du point de vue du joueur en trait.
    """
    if board.is_game_over():
        return evaluate(board)

    if cle in TT:
        entry = TT[cle]
        if entry["profondeur"] >= depth:
            if entry["flag"] == EXACT:
                return entry["score"]
            elif entry["flag"] == LOWERBOUND:
                alpha = max(alpha, entry["score"])
            elif entry["flag"] == UPPERBOUND:
                beta = min(beta, entry["score"])
            if alpha >= beta:
                return entry["score"]

    if depth == 0:
        return quiescence(board, alpha, beta)

    R = 2
    if (null_allowed
            and depth >= R + 1
            and not board.is_check()
            and any(board.pieces(pt, board.turn)
                    for pt in [chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN])):
        null_cle = cle ^ ZT
        board.push(chess.Move.null())
        null_score = -alpha_beta(TT, board, depth - R - 1, -beta, -beta + 1,
                                 ZP, ZR, ZE, ZT, IP, null_cle,
                                 killers, history, null_allowed=False)
        board.pop()
        if null_score >= beta:
            return beta

    best_score     = -float('inf')
    original_alpha = alpha

    def move_priority(m):
        """Score d'ordonnancement d'un coup pour la recherche alpha-beta."""
        s = mvv_lva(board, m)
        if board.is_capture(m):
            s += 5000
        if m.promotion:
            s += VALEURS_PIECES.get(m.promotion, 0) + 4000
        if m in killers[depth]:
            s += 2000
        s += history.get((board.turn, m.from_square, m.to_square), 0)
        return s

    moves = sorted(board.legal_moves, key=move_priority, reverse=True)

    for move in moves:
        new_cle = update_cle(board, cle, move, ZP, ZR, ZE, ZT, IP)
        board.push(move)
        score = -alpha_beta(TT, board, depth - 1, -beta, -alpha,
                            ZP, ZR, ZE, ZT, IP, new_cle,
                            killers, history)
        board.pop()

        if score > best_score:
            best_score = score

        if score > alpha:
            alpha = score
            if not board.is_capture(move):
                key = (board.turn, move.from_square, move.to_square)
                history[key] = history.get(key, 0) + depth * depth

        if alpha >= beta:
            if not board.is_capture(move):
                killers[depth].add(move)
                if len(killers[depth]) > 2:
                    killers[depth].pop()
            break

    flag = EXACT
    if best_score <= original_alpha:
        flag = UPPERBOUND
    elif best_score >= beta:
        flag = LOWERBOUND

    TT[cle] = {"score": best_score, "profondeur": depth, "flag": flag}
    return best_score


def _recherche_complete(board, depth, root_cle, TT, ZP, ZR, ZE, ZT, IP, killers, history, best_first=None):
    """
    Recherche à fenêtre infinie (-∞, +∞) sur tous les coups légaux.

    Utilisée pour les profondeurs 1-2 (où les aspiration windows n'apportent
    pas de gain) et comme fallback quand les aspiration windows ratent.
    Si best_first est fourni, ce coup est placé en tête de liste pour
    bénéficier du meilleur pruning possible (principe du meilleur coup
    de la profondeur précédente en iterative deepening).

    Paramètres
    ----------
    board : chess.Board
        Position racine.
    depth : int
        Profondeur de recherche.
    root_cle : int
        Hash Zobrist de la position racine.
    TT, ZP, ZR, ZE, ZT, IP, killers, history
        Tables de recherche (voir alpha_beta).
    best_first : chess.Move, optionnel
        Coup à examiner en premier (meilleur de la profondeur précédente).

    Retourne
    --------
    tuple[chess.Move, float]
        (meilleur_coup, meilleur_score) ou (None, -∞) si aucun coup légal.
    """
    best_move  = None
    best_score = -float('inf')

    def priority(m):
        if m == best_first:
            return float('inf')
        s = mvv_lva(board, m)
        if board.is_capture(m): s += 5000
        if m.promotion:         s += 4000
        return s

    for move in sorted(board.legal_moves, key=priority, reverse=True):
        new_cle = update_cle(board, root_cle, move, ZP, ZR, ZE, ZT, IP)
        board.push(move)
        score = -alpha_beta(TT, board, depth - 1,
                            -float('inf'), float('inf'),
                            ZP, ZR, ZE, ZT, IP, new_cle, killers, history)
        board.pop()
        if score > best_score:
            best_score = score
            best_move  = move

    return best_move, best_score


def ia_move(TT, board, depth, ZP, ZR, ZE, ZT, IP, max_time: float = 10.0) -> chess.Move:
    """
    Calcule le meilleur coup via Iterative Deepening + Aspiration Windows.

    Algorithme :
        1. Consulte d'abord le livre d'ouverture Polyglot. Si un coup est
           trouvé, le retourne immédiatement sans calcul.
        2. Initialise killers, history et la clé Zobrist racine.
        3. Pour chaque profondeur de 1 à depth (iterative deepening) :
           - Profondeur 1-2 : recherche complète à fenêtre infinie.
           - Profondeur >= 3 : essai avec aspiration window [prev ± 50].
             Si le score sort de la fenêtre (fail high/low), relance une
             recherche complète avec le meilleur coup précédent en tête.
        4. S'arrête dès que max_time (adapté à la phase) est dépassé.
        5. Retourne toujours un coup valide (initialisation avec le premier
           coup légal comme fallback de sécurité).

    Limites de temps par phase :
        ouverture → 2s, milieu → 4s, fin → 5s, finfin → 6s

    Paramètres
    ----------
    TT : dict
        Table de transposition (partagée sur toute la session).
    board : chess.Board
        Position à partir de laquelle chercher.
    depth : int
        Profondeur maximale (plafond de l'iterative deepening).
    ZP, ZR, ZE, ZT, IP
        Tables Zobrist de l'instance courante.
    max_time : float
        Temps maximum en secondes (remplacé par les limites par phase).

    Retourne
    --------
    chess.Move
        Meilleur coup trouvé. Ne retourne jamais None.
    """
    book_move = polyglot_move(board)
    if book_move is not None:
        print(f"  Coup de livre : {board.san(book_move)}")
        return book_move

    phase      = get_game_phase(board)
    time_limits = {
        "ouverture": 2.0,
        "milieu":    4.0,
        "fin":       5.0,
        "finfin":    6.0,
    }
    max_time = time_limits[phase]

    killers    = [set() for _ in range(depth + 2)]
    history    = {}
    root_cle   = hash_zobrist(board, ZP, ZR, ZE, ZT, IP)
    best_move  = next(iter(board.legal_moves))
    prev_score = 0
    WINDOW     = 50
    start_time = time.time()

    for current_depth in range(1, depth + 1):

        if current_depth >= 3:
            alpha = prev_score - WINDOW
            beta  = prev_score + WINDOW

            def priority_root(m):
                """Priorité racine : best_move en premier, puis MVV-LVA."""
                if m == best_move: return float('inf')
                s = mvv_lva(board, m)
                if board.is_capture(m): s += 5000
                if m.promotion:         s += 4000
                return s

            iter_best  = None
            iter_score = -float('inf')
            fail       = False

            for move in sorted(board.legal_moves, key=priority_root, reverse=True):
                new_cle = update_cle(board, root_cle, move, ZP, ZR, ZE, ZT, IP)
                board.push(move)
                score = -alpha_beta(TT, board, current_depth - 1, -beta, -alpha,
                                    ZP, ZR, ZE, ZT, IP, new_cle, killers, history)
                board.pop()

                if score > iter_score:
                    iter_score = score
                    iter_best  = move

                if score > alpha:
                    alpha = score
                if alpha >= beta:
                    fail = True
                    break

            if fail or iter_best is None or abs(iter_score - prev_score) > WINDOW:
                iter_best, iter_score = _recherche_complete(
                    board, current_depth, root_cle,
                    TT, ZP, ZR, ZE, ZT, IP, killers, history,
                    best_first=best_move
                )
        else:
            iter_best, iter_score = _recherche_complete(
                board, current_depth, root_cle,
                TT, ZP, ZR, ZE, ZT, IP, killers, history,
                best_first=best_move
            )

        if iter_best is not None:
            best_move  = iter_best
            prev_score = iter_score

        elapsed = time.time() - start_time


        if elapsed > max_time:
            print(f"  Temps écoulé ({elapsed:.2f}s), arrêt à profondeur {current_depth}")
            break

    return best_move


def est_coup_important(board: chess.Board, move: chess.Move) -> bool:
    """
    Détermine si un coup est "important" pour l'apprentissage.

    Un coup est considéré important s'il modifie significativement l'état
    de la partie : prise de matériel, transformation, mise en échec ou mat.
    Ces coups sont mémorisés pendant la partie et utilisés comme points
    d'apprentissage après que le résultat final est connu.

    Paramètres
    ----------
    board : chess.Board
        Position AVANT que le coup soit joué.
    move : chess.Move
        Coup à évaluer.

    Retourne
    --------
    bool
        True si le coup est une capture, promotion, échec ou mat.
    """
    if board.is_capture(move):
        return True
    if move.promotion:
        return True
    if board.gives_check(move):
        return True
    if board.is_checkmate():
        return True
    return False
