"""
Erwartungswertoptimale Politik durch Rückwärtsinduktion.

Bewertet jede Option über die Bellman-Wertfunktion aus bellman.py und wählt
die beste. Die Zielfunktion aus objectives.py wird pro Zug aus dem
Rundenkontext aufgebaut.
"""

from typing import Literal

from schocken.core.classification import classify
from schocken.core.typedefs import (
    Decision,
    GameState,
    PublicPlayerState,
    RoundContext,
)
from schocken.probability.enumeration import hidden_distribution
from schocken.strategies.base import BaseStrategy
from schocken.strategies.optimizer.bellman import value_before_roll
from schocken.strategies.optimizer.objectives import (
    ExpectedLidsObjective,
    JointDistribution,
    Objective,
    ObjectiveFn,
    split_predecessors,
)


class OptimalStrategy(BaseStrategy):
    """
    Strategie, die jede Option über die Bellman-Wertfunktion bewertet.

    Die Zielfunktion wird pro Zug aus dem Rundenkontext aufgebaut.

    Args:
        follower_distributions: Tabellierte Nachfolgerverteilungen je Wurfbudget.
        objective: "not_lose" (Option A) oder "expected_lids" (Option B).
        max_rolls: Wurfbudget, falls der Kontext noch keines festlegt.
        fallback_players: Spielerzahl, falls kein Kontext übergeben wird
            (z.B. bei der Enumeration in enumeration.py). Im Spiel ohne Wirkung.
    """

    def __init__(
        self,
        follower_distributions: dict[int, JointDistribution],
        objective: Literal["not_lose", "expected_lids"] = "not_lose",
        max_rolls: int = 3,
        fallback_players: int = 2,
    ):
        self.follower_distributions = follower_distributions
        self.objective = objective
        self.max_rolls = max_rolls
        self.fallback_players = fallback_players

    def choose(
        self,
        options: list[Decision],
        state: GameState,
        roll: tuple[int, ...],
        context: RoundContext | None = None,
    ) -> Decision:
        objective = self.build_objective(context)
        cache: dict = {}

        best: Decision | None = None
        best_value = float("-inf")

        for option in options:
            if option["action"] == "stop":
                value = objective(option["rank"], option["state"]["rolls_used"])  # type: ignore
            else:
                value = value_before_roll(option["state"], objective, cache)

            if value > best_value:
                best_value = value
                best = option

        if best is None:
            raise RuntimeError("Keine gültige Option verfügbar.")
        return best

    def build_objective(self, context: RoundContext | None) -> ObjectiveFn:
        """
        Baut die Zielfunktion aus dem aktuellen Rundenkontext.

        Ohne Kontext (Enumeration in enumeration.py) fehlen Pot und
        Deckelstände; dann wird auch für Option B die Zielfunktion von
        Option A verwendet.

        Args:
            context: Rundenkontext aus Sicht des Spielers am Zug.

        Returns:
            Zielfunktion für die Bewertung von Endergebnissen.
        """
        table = context["public_table_state"] if context else []
        n_active = context["n_active"] if context else self.fallback_players
        round_budget = context["max_rolls"] if context else None
        max_rolls = round_budget if round_budget is not None else self.max_rolls
        position = len(table)

        if self.objective == "expected_lids" and context is not None:
            return self._build_expected_lids(context, table, n_active, max_rolls)

        open_predecessors, hidden_predecessors = split_predecessors(table)

        return Objective(
            open_predecessors=open_predecessors,
            hidden_predecessors=hidden_predecessors,
            n_followers=n_active - position - 1,
            follower_distributions=self.follower_distributions,
            is_opener=position == 0,
            max_rolls=max_rolls,
        )

    def _build_expected_lids(
        self,
        context: RoundContext,
        table: list[PublicPlayerState],
        n_active: int,
        max_rolls: int,
    ) -> ExpectedLidsObjective:
        """Baut die Zielfunktion für Option B."""
        lids = context["lids"]
        position = len(table)
        opponents: list[tuple[int, int, JointDistribution | None]] = []

        for entry in table:
            visible = entry["visible_state"]
            seat = entry["turn_order"]
            if visible is not None and len(visible) == 3:
                distribution = {(classify(visible), entry["rolls_used"]): 1.0}
            else:
                held_ones = len(visible) if visible else 0
                distribution = hidden_distribution(held_ones, entry["rolls_used"])
            opponents.append((seat, lids[seat], distribution))

        for seat in range(position + 1, n_active):
            opponents.append((seat, lids[seat], None))

        return ExpectedLidsObjective(
            opponents=opponents,
            position=position,
            n_positions=n_active,
            pot=context["pot"],
            own_lids=lids[position],
            total_lids=context["pot"] + sum(lids),
            follower_distributions=self.follower_distributions,
            is_opener=position == 0,
            max_rolls=max_rolls,
        )
