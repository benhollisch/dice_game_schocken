"""
Zielfunktionen der OptimalStrategy über Endergebnisse eines Zuges.

Option A (Objective) ist die Wahrscheinlichkeit, die Runde nicht zu
verlieren. Man verliert nur, wenn jeder Gegner besser abschneidet:

    P(nicht Verlierer) = 1 - Π_j (1 - S_j)

mit S_j der Wahrscheinlichkeit, dass Gegner j schlechter abschneidet. Die
Gegner zerfallen in drei Gruppen:

- offene Vorgänger: alle Würfel sichtbar, Rang bekannt, S_j ist 0 oder 1
- (teil)verdeckte Vorgänger: nur herausgelegte Einsen sichtbar, der letzte
  Wurf ist verdeckt; S_j aus der exakten bedingten Verteilung
- ausstehende Nachfolger: noch nicht gewürfelt; S_j aus der Verteilung einer
  unterstellten Referenzstrategie beim geltenden Wurfbudget

Option B (ExpectedLidsObjective) ist die negative erwartete Veränderung des
eigenen Deckelstands.
"""

from collections.abc import Callable

import numpy as np

from schocken.core.classification import classify
from schocken.probability.enumeration import (
    hidden_distribution,
    roll_distribution,
)
from schocken.probability.survival import survival_probability_with_ties
from schocken.core.typedefs import PublicPlayerState

Outcome = tuple[tuple[int, ...], int]
JointDistribution = dict[Outcome, float]
ObjectiveFn = Callable[[tuple[int, ...], int], float]


def beats(
    rank: tuple[int, ...],
    rolls_used: int,
    opponent_rank: tuple[int, ...],
    opponent_rolls: int,
    acts_first: bool,
) -> bool:
    """
    Prüft, ob ein Ergebnis gegen ein bekanntes Gegnerergebnis besteht.

    Tie-Breaks: bei gleichem Rang gewinnt die geringere Wurfzahl, bei gleicher
    Wurfzahl die frühere Position.

    Args:
        rank: Eigener Rang.
        rolls_used: Eigene Wurfzahl.
        opponent_rank: Rang des Gegners.
        opponent_rolls: Wurfzahl des Gegners.
        acts_first: Ob man vor dem Gegner an der Reihe war.

    Returns:
        True, wenn der Gegner schlechter abschneidet.
    """
    if rank != opponent_rank:
        return rank < opponent_rank
    if rolls_used != opponent_rolls:
        return rolls_used < opponent_rolls
    return acts_first


def split_predecessors(
    table: list[PublicPlayerState],
    n_dice: int = 3,
) -> tuple[list[Outcome], list[tuple[int, int]]]:
    """
    Teilt die Vorgänger nach Sichtbarkeit ihres Endbilds auf.

    Die Unterscheidung läuft über visible_state, nicht über die Wurfzahl: Auch
    ein Startspieler, der nach einem Wurf stoppt, hat sein Budget formal
    ausgeschöpft, zeigt aber sein vollständiges Bild.

    Args:
        table: Öffentlich sichtbare Zustände der Vorgänger.
        n_dice: Anzahl der Würfel im Spiel.

    Returns:
        Tuple aus offenen Vorgängern als (Rang, Wurfzahl) und (teil)verdeckten
        Vorgängern als (gehaltene Einsen, Wurfzahl).
    """
    open_predecessors: list[Outcome] = []
    hidden_predecessors: list[tuple[int, int]] = []

    for entry in table:
        visible = entry["visible_state"]
        if visible is not None and len(visible) == n_dice:
            open_predecessors.append((classify(visible), entry["rolls_used"]))
        else:
            held_ones = len(visible) if visible else 0
            hidden_predecessors.append((held_ones, entry["rolls_used"]))

    return open_predecessors, hidden_predecessors


class Objective:
    """
    Zielfunktion: Wahrscheinlichkeit, die Runde nicht zu verlieren (Option A).

    Args:
        open_predecessors: Offene Vorgänger als (Rang, Wurfzahl).
        hidden_predecessors: (Teil)verdeckte Vorgänger als
            (gehaltene Einsen, Wurfzahl).
        n_followers: Anzahl der ausstehenden Nachfolger.
        follower_distributions: Gemeinsame Verteilungen über Rang und Wurfzahl
            eines Nachfolgers, je Wurfbudget.
        is_opener: Ob die eigene Wurfzahl das Budget der Nachfolger setzt.
        max_rolls: Wurfbudget der Runde, sofern bereits festgelegt.
    """

    def __init__(
        self,
        open_predecessors: list[Outcome],
        hidden_predecessors: list[tuple[int, int]],
        n_followers: int,
        follower_distributions: dict[int, JointDistribution],
        is_opener: bool,
        max_rolls: int = 3,
    ):
        self.open_predecessors = open_predecessors
        self.hidden_distributions = [
            hidden_distribution(held_ones, rolls)
            for held_ones, rolls in hidden_predecessors
        ]
        self.n_followers = n_followers
        self.follower_distributions = follower_distributions
        self.is_opener = is_opener
        self.max_rolls = max_rolls
        self._memo: dict[Outcome, float] = {}

    def __call__(self, rank: tuple[int, ...], rolls_used: int) -> float:
        """
        Bewertet ein Endergebnis.

        Args:
            rank: Erreichter Endrang.
            rolls_used: Verbrauchte Wurfzahl.

        Returns:
            Wahrscheinlichkeit, die Runde nicht zu verlieren.
        """
        key = (rank, rolls_used)
        if key not in self._memo:
            self._memo[key] = self._evaluate(rank, rolls_used)
        return self._memo[key]

    def _evaluate(self, rank: tuple[int, ...], rolls_used: int) -> float:
        # Einen offenen Vorgänger zu schlagen genügt: Man ist sicher nicht Verlierer.
        for opponent_rank, opponent_rolls in self.open_predecessors:
            if beats(rank, rolls_used, opponent_rank, opponent_rolls, acts_first=False):
                return 1.0

        has_opponents = (
            bool(self.open_predecessors)
            or bool(self.hidden_distributions)
            or self.n_followers > 0
        )
        if not has_opponents:
            return 1.0

        # Wahrscheinlichkeit, dass jeder Gegner besser abschneidet.
        p_all_better = 1.0

        for distribution in self.hidden_distributions:
            survival = survival_probability_with_ties(
                distribution, rank, rolls_used, acts_first=False
            )
            p_all_better *= 1.0 - survival

        if self.n_followers > 0:
            budget = rolls_used if self.is_opener else self.max_rolls
            survival = survival_probability_with_ties(
                self.follower_distributions[budget], rank, rolls_used, acts_first=True
            )
            p_all_better *= (1.0 - survival) ** self.n_followers

        return 1.0 - p_all_better


# --------------------------------------------------------------------------
# Option B: erwartete Deckelveränderung
# --------------------------------------------------------------------------

SHOCK_OUT: tuple[int, ...] = (0, 0)

Key = tuple[tuple[int, ...], int, int]


def rank_lid_value(rank: tuple[int, ...]) -> int:
    """
    Deckelwert eines Rangs, analog zu classification.lid_value().

    Schock mit Beizahl a: a Deckel, General: 3, Straße: 2, Hausnummer: 1.
    Schock-Out wird von der Zielfunktion gesondert behandelt; hier liefert er
    wie lid_value() den Wert 1.

    Args:
        rank: Rang aus classify().

    Returns:
        Anzahl der zu verteilenden Deckel.
    """
    category = rank[0]
    if category == 0:
        return 1 if rank == SHOCK_OUT else 7 - rank[1]
    if category == 1:
        return 3
    if category == 2:
        return 2
    return 1


def build_key_universe(
    n_positions: int, max_rolls: int = 3, n_dice: int = 3
) -> tuple[list[Key], dict[Key, int]]:
    """
    Nummeriert alle Vergleichsschlüssel (Rang, Wurfzahl, Position) aufsteigend.

    Kleiner ist besser, wie in compare_results(). Da jede Position höchstens
    einem Spieler gehört, ist die Ordnung unter allen Spielern strikt.

    Args:
        n_positions: Anzahl der Sitzplätze in der Runde.
        max_rolls: Höchste mögliche Wurfzahl.
        n_dice: Anzahl der Würfel im Spiel.

    Returns:
        Sortierte Schlüsselliste und Zuordnung Schlüssel → Index.
    """
    ranks = sorted({classify(roll) for roll in roll_distribution(n_dice)})
    keys = sorted(
        (rank, rolls, position)
        for rank in ranks
        for rolls in range(1, max_rolls + 1)
        for position in range(n_positions)
    )
    return keys, {key: i for i, key in enumerate(keys)}


class ExpectedLidsObjective:
    """
    Zielfunktion für die erwartete Deckelveränderung (Option B).

    Bewertet ein eigenes Endergebnis mit der negativen erwarteten Veränderung
    des eigenen Deckelstands in dieser Runde; größer ist also besser. Drei
    Ausgänge werden unterschieden:

    - Verlierer: erhält min(v, Pot) in Phase 1, min(v, D_Gewinner) in Phase 2,
      bei Schock-Out des Gewinners alle übrigen Deckel im Spiel
    - Gewinner: gibt in Phase 2 min(v(eigen), D_eigen) ab, bei eigenem
      Schock-Out alle eigenen Deckel
    - unbeteiligt: keine Veränderung, außer bei Schock-Out am Tisch, dann
      gehen alle eigenen Deckel an den Verlierer

    Gegner werden als unabhängig angenommen.

    Args:
        opponents: Je Gegner (Position, Deckelstand, gemeinsame Verteilung
            über Rang und Wurfzahl). Für Nachfolger darf statt der Verteilung
            None stehen; sie wird dann je Wurfbudget aus
            follower_distributions entnommen.
        position: Eigene Position in der Runde.
        n_positions: Anzahl der Spieler in der Runde.
        pot: Deckel im Stapel zu Rundenbeginn.
        own_lids: Eigener Deckelstand zu Rundenbeginn.
        total_lids: Alle Deckel im Spiel, Pot eingeschlossen.
        follower_distributions: Nachfolgerverteilungen je Wurfbudget.
        is_opener: Ob die eigene Wurfzahl das Budget der Nachfolger setzt.
        max_rolls: Wurfbudget der Runde, sofern bereits festgelegt.
        value_fn: Deckelwert eines Rangs.
        shock_out_clears: Ob Schock-Out alle Deckel an den Verlierer überträgt.
    """

    def __init__(
        self,
        opponents: list[tuple[int, int, JointDistribution | None]],
        position: int,
        n_positions: int,
        pot: int,
        own_lids: int,
        total_lids: int,
        follower_distributions: dict[int, JointDistribution],
        is_opener: bool,
        max_rolls: int = 3,
        value_fn: Callable[[tuple[int, ...]], int] = rank_lid_value,
        shock_out_clears: bool = True,
    ):
        self.opponents = opponents
        self.position = position
        self.pot = pot
        self.own_lids = own_lids
        self.total_lids = total_lids
        self.follower_distributions = follower_distributions
        self.is_opener = is_opener
        self.max_rolls = max_rolls
        self.value_fn = value_fn
        self.shock_out_clears = shock_out_clears

        self.keys, self.index = build_key_universe(n_positions, max_rolls=3)
        self.is_shock_out = np.array(
            [shock_out_clears and key[0] == SHOCK_OUT for key in self.keys]
        )
        self._arrays: dict[int, tuple[np.ndarray, ...]] = {}
        self._memo: dict[Outcome, float] = {}

    # ---------------------------------------------------------------- Aufbau

    def _gain(self, opponent_lids: int) -> np.ndarray:
        """Deckel, die man als Verlierer erhält, je Schlüssel des Gewinners."""
        gains = np.empty(len(self.keys))
        for i, (rank, _, _) in enumerate(self.keys):
            value = self.value_fn(rank)
            if self.is_shock_out[i]:
                gains[i] = self.total_lids - self.own_lids
            elif self.pot > 0:
                gains[i] = min(value, self.pot)
            else:
                gains[i] = min(value, opponent_lids)
        return gains

    def _opponent_arrays(self, budget: int) -> tuple[np.ndarray, ...]:
        """
        Wahrscheinlichkeitsvektoren und kumulierte Summen aller Gegner.

        Hängt nur dann vom Budget ab, wenn Nachfolger beteiligt sind; daher
        einmal je Budget aufgebaut und zwischengespeichert.
        """
        if budget in self._arrays:
            return self._arrays[budget]

        n_keys = len(self.keys)
        probabilities = np.zeros((len(self.opponents), n_keys))
        gains = np.zeros((len(self.opponents), n_keys))

        for row, (position, lids, distribution) in enumerate(self.opponents):
            if distribution is None:
                distribution = self.follower_distributions[budget]
            for (rank, rolls), p in distribution.items():
                probabilities[row, self.index[(rank, rolls, position)]] += p
            gains[row] = self._gain(lids)

        zero_column = np.zeros((len(self.opponents), 1))
        cumulative = np.hstack([zero_column, np.cumsum(probabilities, axis=1)])
        cumulative_shock_out = np.hstack(
            [zero_column, np.cumsum(probabilities * self.is_shock_out, axis=1)]
        )

        arrays = (probabilities, gains, cumulative, cumulative_shock_out)
        self._arrays[budget] = arrays
        return arrays

    # ------------------------------------------------------------ Bewertung

    def outcome_probabilities(
        self, rank: tuple[int, ...], rolls_used: int
    ) -> dict[str, float]:
        """
        Zerlegt ein eigenes Endergebnis in die Wahrscheinlichkeiten der Ausgänge.

        Args:
            rank: Eigener Endrang.
            rolls_used: Eigene Wurfzahl.

        Returns:
            Dictionary mit p_lose, p_win, p_lose_shock_out (Verlierer gegen
            einen Schock-Out), p_shock_out_before (ein Gegner hat einen
            Schock-Out vor einem selbst), expected_received (erwartete
            erhaltene Deckel, über alle Verlierer-Ausgänge summiert).
        """
        budget = rolls_used if self.is_opener else self.max_rolls
        probabilities, gains, cumulative, cumulative_shock_out = self._opponent_arrays(
            budget
        )
        x = self.index[(rank, rolls_used, self.position)]

        below = cumulative[:, x]
        p_lose = float(np.prod(below))
        p_win = float(np.prod(1.0 - cumulative[:, x + 1]))
        p_shock_out_before = 1.0 - float(np.prod(1.0 - cumulative_shock_out[:, x]))

        # between[k, t]: P(t < K_k < x) für alle Schlüssel t unterhalb von x
        between = below[:, None] - cumulative[:, 1 : x + 1]

        expected_received = 0.0
        p_lose_shock_out = 0.0
        for j in range(len(self.opponents)):
            others = np.prod(np.delete(between, j, axis=0), axis=0)
            weight = probabilities[j, :x] * others
            expected_received += float(weight @ gains[j, :x])
            p_lose_shock_out += float(weight @ self.is_shock_out[:x])

        return {
            "p_lose": p_lose,
            "p_win": p_win,
            "p_lose_shock_out": p_lose_shock_out,
            "p_shock_out_before": p_shock_out_before,
            "expected_received": expected_received,
        }

    def expected_change(self, rank: tuple[int, ...], rolls_used: int) -> float:
        """
        Erwartete Veränderung des eigenen Deckelstands; kleiner ist besser.

        Args:
            rank: Eigener Endrang.
            rolls_used: Eigene Wurfzahl.

        Returns:
            Erwartete Deckelveränderung in dieser Runde.
        """
        if not self.opponents:
            return 0.0

        parts = self.outcome_probabilities(rank, rolls_used)

        if self.shock_out_clears and rank == SHOCK_OUT:
            give_as_winner = self.own_lids
        elif self.pot > 0:
            give_as_winner = 0
        else:
            give_as_winner = min(self.value_fn(rank), self.own_lids)

        cleared_as_bystander = parts["p_shock_out_before"] - parts["p_lose_shock_out"]

        return (
            parts["expected_received"]
            - parts["p_win"] * give_as_winner
            - cleared_as_bystander * self.own_lids
        )

    def __call__(self, rank: tuple[int, ...], rolls_used: int) -> float:
        """Negative erwartete Deckelveränderung; größer ist besser."""
        key = (rank, rolls_used)
        if key not in self._memo:
            self._memo[key] = -self.expected_change(rank, rolls_used)
        return self._memo[key]
