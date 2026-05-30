"""
Absolute Strategien für das Schocken-Spiel.

Enthält Strategien die unabhängig vom öffentlichen Tischzustand entscheiden.
"""

from schocken.types import GameState, Decision, PublicPlayerState
from schocken.strategies.base import BaseStrategy


class GreedyAllIn(BaseStrategy):
    """
    Maximiert die Anzahl der gehaltenen Einsen.

    Stoppt nur bei Schock-Out, würfelt ansonsten immer weiter.
    Ignoriert den öffentlichen Tischzustand.
    """

    def choose(
        self,
        options: list[Decision],
        state: GameState,
        roll: tuple[int, ...],
        public_table_state: list[PublicPlayerState] | None = None,
    ) -> Decision:
        stop_option = next((o for o in options if o["action"] == "stop"), None)

        if stop_option is not None and stop_option["rank"] == (0, 0):
            return stop_option

        continues = [o for o in options if o["action"] == "continue"]
        return max(continues, key=lambda o: o["state"]["held_ones"])


class StaticThresholdStrategy(BaseStrategy):
    """
    Stoppt wenn der eigene Rang den Threshold erreicht oder unterschreitet.

    Ignoriert den öffentlichen Tischzustand.

    Args:
        threshold: Rang-Tuple unterhalb dessen gestoppt wird.
    """

    def __init__(self, threshold: tuple[int, ...]):
        self.threshold = threshold

    def choose(
        self,
        options: list[Decision],
        state: GameState,
        roll: tuple[int, ...],
        public_table_state: list[PublicPlayerState] | None = None,
    ) -> Decision:
        stop_option = next((o for o in options if o["action"] == "stop"), None)

        if stop_option is not None and stop_option["rank"] <= self.threshold:  # type: ignore
            return stop_option

        continues = [o for o in options if o["action"] == "continue"]
        if not continues:
            return stop_option  # type: ignore

        return max(continues, key=lambda o: o["state"]["held_ones"])
