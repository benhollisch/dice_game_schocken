"""
Wertfunktion eines Zuges über die Bellman-Rekursion.

W(s) ist der Wert eines Zustands vor dem Wurf, Q(s, r) der Wert nach
beobachtetem Wurf r. Die Induktion ankert bei rolls_left = 1, wo keine
Entscheidung mehr existiert und der Wert allein durch die Zielfunktion
bestimmt ist.
"""

from schocken.core.classification import classify
from schocken.core.state import next_states
from schocken.core.typedefs import GameState
from schocken.probability.enumeration import roll_distribution
from schocken.strategies.optimizer.objectives import ObjectiveFn
from schocken.utils import normalize


def value_before_roll(
    state: GameState,
    objective: ObjectiveFn,
    cache: dict | None = None,
) -> float:
    """
    Berechnet den Wert eines Zustands unmittelbar vor dem Wurf (W(s)).

    Args:
        state: Zustand vor dem nächsten Wurf.
        objective: Zielfunktion über Endergebnisse.
        cache: Optionaler Cache für wiederkehrende Teilzustände.

    Returns:
        Wert des Zustands zwischen 0 und 1.
    """
    if cache is None:
        cache = {}

    key = (
        state["held_ones"],
        state["dice_to_roll"],
        state["rolls_left"],
        state["rolls_used"],
    )
    if key in cache:
        return cache[key]

    total = 0.0
    for roll, probability in roll_distribution(state["dice_to_roll"]).items():
        total += probability * value_after_roll(state, roll, objective, cache)

    cache[key] = total
    return total


def value_after_roll(
    state: GameState,
    roll: tuple[int, ...],
    objective: ObjectiveFn,
    cache: dict | None = None,
) -> float:
    """
    Berechnet den Wert eines Zustands nach beobachtetem Wurf (Q(s, r)).

    Args:
        state: Zustand vor dem Wurf.
        roll: Beobachteter Wurf.
        objective: Zielfunktion über Endergebnisse.
        cache: Optionaler Cache für wiederkehrende Teilzustände.

    Returns:
        Bestmöglicher Wert zwischen 0 und 1.
    """
    if cache is None:
        cache = {}

    candidates = []

    final = normalize((1,) * state["held_ones"] + roll)
    candidates.append(objective(classify(final), state["rolls_used"] + 1))

    if state["rolls_left"] > 1:
        for successor in next_states(state, roll):
            candidates.append(value_before_roll(successor, objective, cache))

    return max(candidates)
