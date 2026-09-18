"""
Berechnung von Rangverteilungen für Schocken-Zustände.

Enthält die Enumeration des Entscheidungsbaums eines Zuges unter einer
gegebenen Politik sowie Hilfsfunktionen zur Weiterverarbeitung der
resultierenden Verteilungen.
"""

from collections import defaultdict
from itertools import product
from math import comb, factorial
from bisect import bisect_right

from schocken.state import decide_after_roll
from schocken.strategies.base import BaseStrategy
from schocken.types import GameState
from schocken.utils import normalize


def roll_distribution(n_dice: int) -> dict[tuple[int, ...], float]:
    """
    Berechnet die Wahrscheinlichkeitsverteilung über alle Würfe mit n Würfeln.

    Würfelbilder werden normalisiert, sodass permutationsgleiche Ergebnisse
    zusammenfallen und ihre Wahrscheinlichkeiten addiert werden.

    Args:
        n_dice: Anzahl der geworfenen Würfel.

    Returns:
        Dictionary von normalisiertem Würfelbild auf Wahrscheinlichkeit.
    """
    outcomes: dict[tuple[int, ...], float] = defaultdict(float)
    weight = 1 / 6**n_dice

    for combination in product(range(1, 7), repeat=n_dice):
        outcomes[normalize(combination)] += weight

    return dict(outcomes)


def _cache_key(state: GameState) -> tuple:
    """
    Erzeugt einen hashbaren Schlüssel aus den ergebnisrelevanten Zustandsfeldern.

    rolls_used und visible_state werden ausgelassen, da sie die Rangverteilung
    nicht beeinflussen.

    Args:
        state: Zustand vor dem nächsten Wurf.

    Returns:
        Tuple als Cache-Schlüssel.
    """
    return (
        state["held_ones"],
        state["dice_to_roll"],
        state["rolls_left"],
        state["must_continue"],
    )


def rank_distribution(
    state: GameState,
    strategy: BaseStrategy,
    cache: dict | None = None,
) -> dict[tuple[int, ...], float]:
    """
    Berechnet die Verteilung der Endränge ab einem Zustand unter einer Politik.

    Enumeriert den vollständigen Entscheidungsbaum: über alle möglichen Würfe
    gewichtet mit ihrer Wahrscheinlichkeit, an Entscheidungsknoten gemäß der
    übergebenen Strategie.

    TODO: decide_after_roll wird ohne public_table_state aufgerufen. Für
    reaktive Strategien liefert die Enumeration dadurch eine Verteilung, die
    nicht dem tatsächlichen Spielverhalten entspricht. Aktuell liegt es in der
    Verantwortung des Aufrufers, nur tischunabhängige Politiken zu übergeben.

    Args:
        state: Zustand unmittelbar vor dem nächsten Wurf.
        strategy: Politik die an Entscheidungsknoten angewandt wird.
        cache: Optionaler Cache für wiederkehrende Teilzustände.

    Returns:
        Dictionary von Rang auf Wahrscheinlichkeit.
    """
    if cache is None:
        cache = {}

    key = _cache_key(state)
    if key in cache:
        return cache[key]

    distribution: dict[tuple[int, ...], float] = defaultdict(float)

    for roll, probability in roll_distribution(state["dice_to_roll"]).items():
        decision = decide_after_roll(state, roll, strategy)

        if decision["action"] == "stop":
            distribution[decision["rank"]] += probability
        else:
            sub = rank_distribution(decision["state"], strategy, cache)
            for rank, p in sub.items():
                distribution[rank] += probability * p

    result = dict(distribution)
    cache[key] = result
    return result


def joint_distribution(
    state: GameState,
    strategy: BaseStrategy,
    cache: dict | None = None,
) -> dict[tuple[tuple[int, ...], int], float]:
    """
    Berechnet die gemeinsame Verteilung über Endrang und verbrauchte Wurfzahl.

    Im Unterschied zu rank_distribution wird die Wurfzahl nicht wegaggregiert,
    da sie für die Auflösung von Gleichständen benötigt wird.

    TODO: decide_after_roll wird ohne public_table_state aufgerufen. Für
    reaktive Strategien entspricht die Verteilung daher nicht dem tatsächlichen
    Spielverhalten.

    Args:
        state: Zustand unmittelbar vor dem nächsten Wurf.
        strategy: Politik die an Entscheidungsknoten angewandt wird.
        cache: Optionaler Cache für wiederkehrende Teilzustände.

    Returns:
        Dictionary von (Rang, Wurfzahl) auf Wahrscheinlichkeit.
    """
    if cache is None:
        cache = {}

    key = (_cache_key(state), state["rolls_used"])
    if key in cache:
        return cache[key]

    distribution: dict[tuple[tuple[int, ...], int], float] = defaultdict(float)

    for roll, probability in roll_distribution(state["dice_to_roll"]).items():
        decision = decide_after_roll(state, roll, strategy)

        if decision["action"] == "stop":
            outcome = (decision["rank"], decision["state"]["rolls_used"])
            distribution[outcome] += probability
        else:
            sub = joint_distribution(decision["state"], strategy, cache)
            for outcome, p in sub.items():
                distribution[outcome] += probability * p

    result = dict(distribution)
    cache[key] = result
    return result


def increment_distribution(n_dice: int) -> dict[int, float]:
    """
    Berechnet die Verteilung des Einsen-Zuwachses in einem einzelnen Wurf.

    Berücksichtigt die Konversion von Sechsen: zwei Sechsen ergeben eine
    zusätzliche Eins, drei Sechsen ergeben zwei. Basiert auf der gemeinsamen
    Multinomialverteilung von Einsen und Sechsen.

    Args:
        n_dice: Anzahl der geworfenen Würfel.

    Returns:
        Dictionary von Zuwachs auf Wahrscheinlichkeit.
    """
    conversion = {0: 0, 1: 0, 2: 1, 3: 2}
    distribution: dict[int, float] = defaultdict(float)

    for ones in range(n_dice + 1):
        for sixes in range(n_dice - ones + 1):
            rest = n_dice - ones - sixes
            weight = (
                factorial(n_dice)
                / (factorial(ones) * factorial(sixes) * factorial(rest))
                * (1 / 6) ** ones
                * (1 / 6) ** sixes
                * (4 / 6) ** rest
            )
            distribution[ones + conversion.get(sixes, 0)] += weight

    return dict(distribution)


def ones_distribution(
    n_dice: int, n_rolls: int, with_conversion: bool = True
) -> dict[int, float]:
    """
    Berechnet die Verteilung der Einsenanzahl nach n_rolls Würfen.

    Analytische Kontrollrechnung zur Validierung der Enumeration. Unterstellt,
    dass in jedem Wurf alle Einsen herausgelegt und die verbleibenden Würfel
    erneut geworfen werden.

    Args:
        n_dice: Anzahl der Würfel zu Beginn.
        n_rolls: Anzahl der Würfe.
        with_conversion: Ob die Sechsen-Konversion berücksichtigt wird.

    Returns:
        Dictionary von Einsenanzahl auf Wahrscheinlichkeit.
    """
    distribution: dict[int, float] = {0: 1.0}

    for _ in range(n_rolls):
        updated: dict[int, float] = defaultdict(float)

        for held, p_held in distribution.items():
            remaining = n_dice - held

            if remaining == 0:
                updated[held] += p_held
                continue

            if with_conversion:
                increments = increment_distribution(remaining)
            else:
                increments = {
                    k: comb(remaining, k) * (1 / 6) ** k * (5 / 6) ** (remaining - k)
                    for k in range(remaining + 1)
                }

            for increment, p_increment in increments.items():
                updated[min(held + increment, n_dice)] += p_held * p_increment

        distribution = dict(updated)

    return distribution


def opponent_distribution(
    n_rolls: int,
    strategy: BaseStrategy,
    n_dice: int = 3,
) -> dict[tuple[int, ...], float]:
    """
    Berechnet die Rangverteilung eines Gegners mit n_rolls Würfen.

    Unterstellt einen Gegner, der noch nicht gewürfelt hat und die übergebene
    Referenzstrategie spielt.

    Args:
        n_rolls: Anzahl der Würfe, die dem Gegner zur Verfügung stehen.
        strategy: Referenzstrategie des Gegners.
        n_dice: Anzahl der Würfel zu Beginn.

    Returns:
        Dictionary von Rang auf Wahrscheinlichkeit.
    """
    start = GameState(
        held_ones=0,
        rolls_left=n_rolls,
        rolls_used=0,
        visible_state=None,
        must_continue=False,
        dice_to_roll=n_dice,
    )
    return rank_distribution(start, strategy)


def cumulative_table(
    distribution: dict[tuple[int, ...], float],
) -> tuple[list[tuple[int, ...]], list[float]]:
    """
    Wandelt eine Rangverteilung in eine kumulierte Tabelle für Tailsummen um.

    Die Ränge werden aufsteigend sortiert (bessere Ränge zuerst). Die
    Präfixsummen enthalten an Position i die aufsummierte Wahrscheinlichkeit
    aller Ränge vor Position i.

    Args:
        distribution: Dictionary von Rang auf Wahrscheinlichkeit.

    Returns:
        Tuple aus sortierter Rangliste und zugehörigen Präfixsummen.
    """
    ranks = sorted(distribution)

    prefix = [0.0]
    for rank in ranks:
        prefix.append(prefix[-1] + distribution[rank])

    return ranks, prefix


def survival_probability(
    table: tuple[list[tuple[int, ...]], list[float]],
    rank: tuple[int, ...],
) -> float:
    """
    Berechnet die Wahrscheinlichkeit, dass ein Gegner schlechter abschneidet.

    Entspricht P(Rang_Gegner > rank), also der Tailsumme oberhalb des
    übergebenen Rangs. Gleichstand zählt nicht als Erfolg, da der Tie-Break
    über die Wurfzahl separat zu behandeln ist.

    Args:
        table: Kumulierte Tabelle aus cumulative_table().
        rank: Eigener Rang, gegen den verglichen wird.

    Returns:
        Wahrscheinlichkeit zwischen 0 und 1.
    """
    ranks, prefix = table
    index = bisect_right(ranks, rank)
    return prefix[-1] - prefix[index]


def survival_probability_with_ties(
    distribution: dict[tuple[tuple[int, ...], int], float],
    rank: tuple[int, ...],
    rolls_used: int,
    acts_first: bool,
) -> float:
    """
    Berechnet die Wahrscheinlichkeit, gegen einen Gegner nicht zu verlieren.

    Berücksichtigt beide Tie-Break-Stufen: Bei gleichem Rang gewinnt die
    geringere Wurfzahl, bei gleicher Wurfzahl die frühere Position.

    Args:
        distribution: Gemeinsame Verteilung aus joint_distribution().
        rank: Eigener Rang.
        rolls_used: Eigene verbrauchte Wurfzahl.
        acts_first: Ob man vor dem betrachteten Gegner an der Reihe war.

    Returns:
        Wahrscheinlichkeit zwischen 0 und 1.
    """
    total = 0.0

    for (opponent_rank, opponent_rolls), p in distribution.items():
        if opponent_rank > rank:
            total += p
        elif opponent_rank == rank:
            if opponent_rolls > rolls_used:
                total += p
            elif opponent_rolls == rolls_used and acts_first:
                total += p

    return total


def opponent_tables(
    strategy: BaseStrategy,
    max_rolls: int = 3,
    n_dice: int = 3,
) -> dict[int, tuple[list[tuple[int, ...]], list[float]]]:
    """
    Tabelliert die kumulierten Rangverteilungen für alle Wurfzahlen.

    Wird einmal vorberechnet und anschließend für Lookups verwendet, da die
    Verteilungen weder vom Tischzustand noch vom eigenen Würfelbild abhängen.

    Args:
        strategy: Referenzstrategie der Gegner.
        max_rolls: Höchste zu tabellierende Wurfzahl.
        n_dice: Anzahl der Würfel zu Beginn.

    Returns:
        Dictionary von Wurfzahl auf kumulierte Tabelle.
    """
    return {
        m: cumulative_table(opponent_distribution(m, strategy, n_dice))
        for m in range(1, max_rolls + 1)
    }
