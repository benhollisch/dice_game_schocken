"""
Regressionstests für die Sechsen-Konversion.

Spielregel: Im ersten und zweiten Wurf dürfen zwei Sechsen zu einer Eins und
drei Sechsen zu zwei Einsen gedreht werden, sofern danach noch ein Wurf im
Budget ist. Gedreht wird nur, um die Eins zu halten. Drehen verpflichtet zum
nächsten Wurf; nach diesem darf wieder gestoppt werden.

Ausführen mit:  pytest src/testing/test_conversion_rules.py -v
"""

import sys

from schocken.state import decide_after_roll, next_states
from schocken.strategies.base import BaseStrategy
from schocken.typedefs import Decision, GameState, RoundContext


class RecordingStrategy(BaseStrategy):
    """
    Zeichnet die angebotenen Optionen auf und wählt eine vorgegebene Aktion.

    Args:
        action: "stop" oder "continue"; bei "continue" wird die Option mit
            den meisten gehaltenen Einsen gewählt.
    """

    def __init__(self, action: str = "stop"):
        self.action = action
        self.offered: list[Decision] | None = None

    def choose(
        self,
        options: list[Decision],
        state: GameState,
        roll: tuple[int, ...],
        context: RoundContext | None = None,
    ) -> Decision:
        self.offered = options
        matching = [o for o in options if o["action"] == self.action]
        return max(matching, key=lambda o: o["state"]["held_ones"])


def state_before_roll(budget: int, rolls_used: int, held_ones: int = 0) -> GameState:
    """Zustand vor einem Wurf bei gegebenem Budget und bisherigem Verbrauch."""
    return GameState(
        held_ones=held_ones,
        rolls_left=budget - rolls_used,
        rolls_used=rolls_used,
        visible_state=(1,) * held_ones if held_ones else None,
        dice_to_roll=3 - held_ones,
    )


def offered_options(state: GameState, roll: tuple[int, ...]) -> list[Decision] | None:
    """Liefert die angebotenen Optionen, oder None, wenn gar keine Wahl bestand."""
    strategy = RecordingStrategy()
    decide_after_roll(state, roll, strategy)
    return strategy.offered


def continue_shapes(options: list[Decision]) -> list[tuple[int, int]]:
    """Fortsetzungsoptionen als (gehaltene Einsen, Würfel im Becher)."""
    return sorted(
        (o["state"]["held_ones"], o["state"]["dice_to_roll"])
        for o in options
        if o["action"] == "continue"
    )


# --------------------------------------------------------------------------
# Kein Drehen ohne weiteren Wurf im Budget
# --------------------------------------------------------------------------


def test_budget_two_second_roll_forces_stop_without_choice():
    """Budget 2, zweiter Wurf: letzter Wurf, keine Wahl, also auch kein Drehen."""
    state = state_before_roll(budget=2, rolls_used=1)
    strategy = RecordingStrategy(action="continue")

    decision = decide_after_roll(state, (6, 6, 3), strategy)

    assert strategy.offered is None
    assert decision["action"] == "stop"
    assert decision["final"] == (6, 6, 3)


def test_budget_one_first_roll_forces_stop_without_choice():
    """Startspieler hat nach einem Wurf gestoppt: auch drei Sechsen bleiben stehen."""
    state = state_before_roll(budget=1, rolls_used=0)
    assert offered_options(state, (6, 6, 6)) is None


def test_budget_three_third_roll_forces_stop_without_choice():
    """Im dritten Wurf darf nie gedreht werden."""
    state = state_before_roll(budget=3, rolls_used=2)
    assert offered_options(state, (6, 6, 3)) is None


def test_next_states_rejects_conversion_without_following_roll():
    """Zweite Absicherung in next_states(): ohne Folgewurf keine Konversion."""
    state = state_before_roll(budget=1, rolls_used=0)
    shapes = sorted(
        (s["held_ones"], s["dice_to_roll"]) for s in next_states(state, (6, 6, 3))
    )
    assert all(held == 0 for held, _ in shapes)


# --------------------------------------------------------------------------
# Drehen ist erlaubt, solange ein weiterer Wurf folgt
# --------------------------------------------------------------------------


def test_budget_two_first_roll_allows_conversion():
    """Budget 2, erster Wurf: Der zweite Wurf folgt noch, Drehen ist erlaubt."""
    options = offered_options(state_before_roll(budget=2, rolls_used=0), (6, 6, 3))
    assert options is not None
    assert continue_shapes(options) == [(0, 3), (1, 2)]


def test_budget_three_second_roll_allows_conversion():
    """Budget 3, zweiter Wurf: Der dritte Wurf folgt noch, Drehen ist erlaubt."""
    options = offered_options(state_before_roll(budget=3, rolls_used=1), (6, 6, 3))
    assert options is not None
    assert continue_shapes(options) == [(0, 3), (1, 2)]


def test_three_sixes_offer_one_or_two_ones():
    """Drei Sechsen: zu einer Eins (zwei Würfel weiter) oder zu zwei Einsen (einer weiter)."""
    options = offered_options(state_before_roll(budget=3, rolls_used=0), (6, 6, 6))
    assert options is not None
    assert continue_shapes(options) == [(0, 3), (1, 2), (2, 1)]


# --------------------------------------------------------------------------
# Gedrehte Einsen werden gehalten
# --------------------------------------------------------------------------


def test_no_conversion_without_holding_the_converted_one():
    """Drehen, ohne die Eins zu halten, ist kein Spielzug."""
    options = offered_options(state_before_roll(budget=3, rolls_used=0), (6, 6, 3))
    assert options is not None
    rerolls = [
        o for o in options if o["action"] == "continue" and o["state"]["held_ones"] == 0
    ]
    assert len(rerolls) == 1


def test_conversion_with_natural_one():
    """(6, 6, 1): gewürfelte Eins halten, zusätzlich drehen, ein Würfel bleibt im Becher."""
    options = offered_options(state_before_roll(budget=3, rolls_used=0), (6, 6, 1))
    assert options is not None
    assert (2, 1) in continue_shapes(options)


def test_stop_option_shows_unconverted_roll():
    """Wer stoppt, stoppt mit dem gewürfelten Bild; gedrehte Bilder gibt es nur beim Weiterwürfeln."""
    options = offered_options(state_before_roll(budget=3, rolls_used=0), (6, 6, 3))
    assert options is not None
    (stop,) = [o for o in options if o["action"] == "stop"]
    assert stop["final"] == (6, 6, 3)


# --------------------------------------------------------------------------
# Drehen verpflichtet nur zum nächsten Wurf
# --------------------------------------------------------------------------


def test_stop_allowed_after_roll_following_conversion():
    """Im ersten Wurf gedreht: Nach dem zweiten Wurf darf gestoppt werden."""
    start = state_before_roll(budget=3, rolls_used=0)
    converted = next(
        s
        for s in next_states(start, (6, 6, 3))
        if s["held_ones"] == 1 and s["dice_to_roll"] == 2
    )

    options = offered_options(converted, (5, 4))
    assert options is not None
    assert any(o["action"] == "stop" for o in options)


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
