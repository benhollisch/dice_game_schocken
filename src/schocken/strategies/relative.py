"""
Relative Strategien für das Schocken-Spiel.

Enthält Strategien die den öffentlichen Tischzustand in ihre Entscheidung einbeziehen.
"""

from schocken.types import GameState, Decision, PublicPlayerState
from schocken.strategies.base import BaseStrategy, worst_public_rank, total_danger


class PublicThresholdStrategy(BaseStrategy):
    """
    Stoppt nur wenn der eigene Rang besser ist als der schlechteste öffentliche Rang.

    Orientiert sich ausschließlich am öffentlichen Tischzustand.
    """

    def choose(
        self,
        options: list[Decision],
        state: GameState,
        roll: tuple[int, ...],
        public_table_state: list[PublicPlayerState] | None = None,
    ) -> Decision:
        stop_option = next((o for o in options if o["action"] == "stop"), None)
        worst_public = worst_public_rank(public_table_state)

        if stop_option is not None and worst_public is not None:
            if stop_option["rank"] < worst_public:  # type: ignore
                return stop_option

        continues = [o for o in options if o["action"] == "continue"]
        if not continues:
            if stop_option is None:
                raise RuntimeError("Keine gültige Option verfügbar.")
            return stop_option

        return max(continues, key=lambda o: o["state"]["held_ones"])


class AdaptiveGreedyStrategy(BaseStrategy):
    """
    Spielt aggressiv wenn keine öffentlichen Informationen vorliegen.
    Orientiert sich sonst am schlechtesten öffentlichen Rang.
    """

    def choose(
        self,
        options: list[Decision],
        state: GameState,
        roll: tuple[int, ...],
        public_table_state: list[PublicPlayerState] | None = None,
    ) -> Decision:
        stop_option = next((o for o in options if o["action"] == "stop"), None)
        continues = [o for o in options if o["action"] == "continue"]
        worst_public = worst_public_rank(public_table_state)

        if worst_public is None:
            if stop_option is not None and stop_option["rank"] == (0, 0):
                return stop_option
        else:
            if stop_option is not None and stop_option["rank"] < worst_public:  # type: ignore
                return stop_option

        if not continues:
            if stop_option is None:
                raise RuntimeError("Keine gültige Option verfügbar.")
            return stop_option

        return max(continues, key=lambda o: o["state"]["held_ones"])


class HybridThresholdStrategy(BaseStrategy):
    """
    Kombiniert statischen Threshold mit öffentlichem Tischzustand.

    Ohne öffentliche Informationen wird der Threshold verwendet.
    Mit öffentlichen Informationen wird nur eine sichere Niederlage vermieden.

    Args:
        threshold: Rang-Tuple unterhalb dessen gestoppt wird wenn kein public state vorliegt.
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
        continues = [o for o in options if o["action"] == "continue"]
        worst_public = worst_public_rank(public_table_state)

        if worst_public is None:
            if stop_option is not None and stop_option["rank"] <= self.threshold:  # type: ignore
                return stop_option
        else:
            if stop_option is not None and stop_option["rank"] < worst_public:  # type: ignore
                return stop_option

        if not continues:
            if stop_option is None:
                raise RuntimeError("Keine gültige Option verfügbar.")
            return stop_option

        return max(continues, key=lambda o: o["state"]["held_ones"])


class DangerAwareStrategy(BaseStrategy):
    """
    Berücksichtigt den Gefahrenwert des Tisches bei der Entscheidung.

    Spielt aggressiver wenn der Gefahrenwert hoch ist.

    Args:
        threshold: Rang-Tuple unterhalb dessen gestoppt wird.
        risk_aversion: Gefahrenschwelle ab der aggressiver gespielt wird.
    """

    def __init__(self, threshold: tuple[int, ...], risk_aversion: float = 0.5):
        self.threshold = threshold
        self.risk_aversion = risk_aversion

    def choose(
        self,
        options: list[Decision],
        state: GameState,
        roll: tuple[int, ...],
        public_table_state: list[PublicPlayerState] | None = None,
    ) -> Decision:
        stop_option = next((o for o in options if o["action"] == "stop"), None)
        continues = [o for o in options if o["action"] == "continue"]

        if stop_option is None:
            return max(continues, key=lambda o: o["state"]["held_ones"])

        if stop_option["rank"] > self.threshold:  # type: ignore
            return max(continues, key=lambda o: o["state"]["held_ones"])

        if total_danger(public_table_state) > self.risk_aversion:  # type: ignore
            return max(continues, key=lambda o: o["state"]["held_ones"])

        return stop_option
