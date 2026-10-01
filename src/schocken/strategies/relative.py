"""
Relative Strategien für das Schocken-Spiel.

Enthält Strategien die den Rundenkontext in ihre Entscheidung einbeziehen.
"""

from schocken.strategies.base import (
    BaseStrategy,
    parse_threshold,
    total_danger,
    worst_public_rank,
)
from schocken.core.typedefs import (
    Decision,
    GameState,
    RoundContext,
)


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
        context: RoundContext | None = None,
    ) -> Decision:
        table = context["public_table_state"] if context else []

        stop_option = next((o for o in options if o["action"] == "stop"), None)
        worst_public = worst_public_rank(table)

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
        context: RoundContext | None = None,
    ) -> Decision:
        table = context["public_table_state"] if context else []

        stop_option = next((o for o in options if o["action"] == "stop"), None)
        continues = [o for o in options if o["action"] == "continue"]
        worst_public = worst_public_rank(table)

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
        threshold: Schwelle als Würfelbild oder als Rang, unterhalb derer
            gestoppt wird wenn keine öffentlichen Informationen vorliegen.
    """

    def __init__(self, threshold: tuple[int, ...]):
        self.threshold = parse_threshold(threshold)

    def choose(
        self,
        options: list[Decision],
        state: GameState,
        roll: tuple[int, ...],
        context: RoundContext | None = None,
    ) -> Decision:
        table = context["public_table_state"] if context else []

        stop_option = next((o for o in options if o["action"] == "stop"), None)
        continues = [o for o in options if o["action"] == "continue"]
        worst_public = worst_public_rank(table)

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

    Spielt aggressiver wenn der Gefahrenwert hoch ist oder wenn noch keine
    öffentlichen Informationen vorliegen.

    Args:
        threshold: Schwelle als Würfelbild oder als Rang, unterhalb derer
            gestoppt wird.
        risk_aversion: Gefahrenschwelle ab der aggressiver gespielt wird.
    """

    def __init__(self, threshold: tuple[int, ...], risk_aversion: float = 0.5):
        self.threshold = parse_threshold(threshold)
        self.risk_aversion = risk_aversion

    def choose(
        self,
        options: list[Decision],
        state: GameState,
        roll: tuple[int, ...],
        context: RoundContext | None = None,
    ) -> Decision:
        table = context["public_table_state"] if context else []

        stop_option = next((o for o in options if o["action"] == "stop"), None)
        continues = [o for o in options if o["action"] == "continue"]

        if stop_option is None:
            return max(continues, key=lambda o: o["state"]["held_ones"])

        if stop_option["rank"] > self.threshold:  # type: ignore
            return max(continues, key=lambda o: o["state"]["held_ones"])

        if not table or total_danger(table) > self.risk_aversion:
            return max(continues, key=lambda o: o["state"]["held_ones"])

        return stop_option
