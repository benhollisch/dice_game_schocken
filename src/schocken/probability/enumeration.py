"""
Rangverteilungen durch Enumeration.

Enthält die Enumeration des Entscheidungsbaums eines Zuges unter einer
gegebenen Politik sowie die exakte Verteilung verdeckter Vorgänger.
"""

from collections import defaultdict
from itertools import product

from schocken.core.state import decide_after_roll, initial_state
from schocken.strategies.base import BaseStrategy
from schocken.core.typedefs import GameState, RoundContext
from schocken.core.dice import normalize
from schocken.core.classification import classify


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
    )


def rank_distribution(
    state: GameState,
    strategy: BaseStrategy,
    context: RoundContext | None = None,
    cache: dict | None = None,
) -> dict[tuple[int, ...], float]:
    """
    Berechnet die Verteilung der Endränge ab einem Zustand unter einer Politik.

    Enumeriert den vollständigen Entscheidungsbaum: über alle möglichen Würfe
    gewichtet mit ihrer Wahrscheinlichkeit, an Entscheidungsknoten gemäß der
    übergebenen Strategie.

    Die Verteilung gilt für den übergebenen Tischzustand, und ohne Kontext ist sie nur für tischunabhängige Strategien korrekt.

    Args:
        state: Zustand unmittelbar vor dem nächsten Wurf.
        strategy: Politik die an Entscheidungsknoten angewandt wird.
        context: Kontext für reaktive Strategien.
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
        decision = decide_after_roll(state, roll, strategy, context)
        if decision["action"] == "stop":
            distribution[decision["rank"]] += probability  # type: ignore
        else:
            sub = rank_distribution(decision["state"], strategy, context, cache)
            for rank, p in sub.items():
                distribution[rank] += probability * p

    result = dict(distribution)
    cache[key] = result
    return result


def joint_distribution(
    state: GameState,
    strategy: BaseStrategy,
    context: RoundContext | None = None,
    cache: dict | None = None,
) -> dict[tuple[tuple[int, ...], int], float]:
    """
    Berechnet die gemeinsame Verteilung über Endrang und verbrauchte Wurfzahl.

    Im Unterschied zu rank_distribution wird die Wurfzahl nicht wegaggregiert,
    da sie für die Auflösung von Gleichständen benötigt wird.

    Die Verteilung gilt für den übergebenen Tischzustand, und ohne Kontext ist sie nur für tischunabhängige Strategien korrekt.

    Args:
        state: Zustand unmittelbar vor dem nächsten Wurf.
        strategy: Politik die an Entscheidungsknoten angewandt wird.
        context: Kontext für reaktive Strategien.
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
        decision = decide_after_roll(state, roll, strategy, context)

        if decision["action"] == "stop":
            outcome = (decision["rank"], decision["state"]["rolls_used"])
            distribution[outcome] += probability  # type: ignore
        else:
            sub = joint_distribution(decision["state"], strategy, context, cache)
            for outcome, p in sub.items():
                distribution[outcome] += probability * p

    result = dict(distribution)
    cache[key] = result
    return result


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
    start = initial_state(n_rolls=n_rolls, n_dice=n_dice)
    return rank_distribution(start, strategy)


def hidden_distribution(
    held_ones: int,
    rolls_used: int,
    n_dice: int = 3,
) -> dict[tuple[tuple[int, ...], int], float]:
    """
    Berechnet die bedingte Verteilung eines Vorgängers mit verdecktem letzten Wurf.

    Wer sein Wurfbudget ausschöpft, zeigt nur die herausgelegten Einsen; der
    letzte Wurf mit den übrigen n_dice - held_ones Würfeln bleibt verdeckt.
    Deckt teilverdeckte (held_ones > 0) und verdeckte Vorgänger (held_ones = 0) ab.

    Die Verteilung ist exakt und hängt nicht von der Strategie des Vorgängers
    ab: Seine Entscheidungen stecken vollständig in held_ones, der letzte Wurf
    ist ein frischer Wurf, und im letzten Wurf ist keine Konversion erlaubt.

    Args:
        held_ones: Anzahl der sichtbar herausgelegten Einsen.
        rolls_used: Verbrauchte Wurfzahl des Vorgängers, also das Wurfbudget.
        n_dice: Anzahl der Würfel im Spiel.

    Returns:
        Dictionary von (Rang, Wurfzahl) auf Wahrscheinlichkeit, im selben
        Format wie joint_distribution().
    """
    distribution: dict[tuple[tuple[int, ...], int], float] = defaultdict(float)

    for roll, probability in roll_distribution(n_dice - held_ones).items():
        final = normalize((1,) * held_ones + roll)
        distribution[(classify(final), rolls_used)] += probability

    return dict(distribution)
