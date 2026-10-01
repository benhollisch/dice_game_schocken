"""
Zustandslogik im Schocken-Spiel.

Enthält Funktionen zur Berechnung möglicher Folgezustände nach einem Wurf
sowie die Entscheidungslogik für den weiteren Spielverlauf.
"""

from schocken.utils import normalize
from schocken.core.classification import classify
from schocken.core.typedefs import (
    GameState,
    Decision,
    RoundContext,
)


def next_states(state: GameState, roll: tuple[int, ...]) -> list[GameState]:
    """
    Berechnet alle möglichen Folgezustände nach einem Wurf.

    Berücksichtigt die Möglichkeit, Sechsen in Einsen zu konvertieren
    sowie das Herauslegen von Einsen.

    Args:
        state: Aktueller Spielzustand.
        roll: Gewürfeltes Ergebnis als normalisiertes Tuple.

    Returns:
        Liste aller möglichen Folgezustände.
    """
    rolls_used = state["rolls_used"] + 1
    rolls_left = state["rolls_left"] - 1

    ones = roll.count(1)
    sixes = roll.count(6)

    possible_conversions = [0]
    if sixes >= 2:
        possible_conversions.append(1)
    if sixes == 3:
        possible_conversions.append(2)

    new_states: list[GameState] = []
    for k in possible_conversions:
        if k > 0 and rolls_left < 1:
            continue

        total_ones = ones + k
        max_keep = total_ones if rolls_left > 0 else 0

        # Gedrehte Einsen werden immer gehalten: Gedreht wird nur, um sie zu halten.
        for keep in range(k, max_keep + 1):
            held_ones = state["held_ones"] + keep

            visible_state = (1,) * held_ones if held_ones > 0 else None

            new_states.append(
                GameState(
                    held_ones=held_ones,
                    rolls_left=rolls_left,
                    rolls_used=rolls_used,
                    visible_state=visible_state,
                    dice_to_roll=state["dice_to_roll"] - keep,
                )
            )

    return new_states


def decide_after_roll(
    state: GameState,
    roll: tuple[int, ...],
    strategy,
    context: RoundContext | None = None,
) -> Decision:
    """
    Trifft eine Entscheidung nach einem Wurf basierend auf der gewählten Strategie.

    Args:
        state: Aktueller Spielzustand.
        roll: Gewürfeltes Ergebnis als normalisiertes Tuple.
        strategy: Strategie-Objekt mit einer choose()-Methode.
        context: Kontext der laufenden Runde.

    Returns:
        Entscheidungs-Dictionary mit Aktion, finalem Würfelbild und Rang.
    """
    final = normalize((1,) * state["held_ones"] + roll)

    if state["rolls_left"] == 1:
        return Decision(
            action="stop",
            final=final,
            rank=classify(final),
            state={
                **state,
                "rolls_used": state["rolls_used"] + 1,
                "rolls_left": state["rolls_left"] - 1,
                "visible_state": state["visible_state"],
            },
        )

    options: list[Decision] = []
    options.append(
        Decision(
            action="stop",
            final=final,
            rank=classify(final),
            state={
                **state,
                "rolls_used": state["rolls_used"] + 1,
                "rolls_left": state["rolls_left"] - 1,
                "visible_state": final,
            },
        )
    )

    for next_state in next_states(state, roll):
        options.append(
            Decision(action="continue", state=next_state, final=None, rank=None)
        )

    return strategy.choose(options, state, roll, context)
