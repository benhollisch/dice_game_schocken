"""
Erwartungswertoptimale Politik durch Rückwärtsinduktion.

Berechnet die Wertfunktion eines Zuges über die Bellman-Rekursion und leitet
daraus eine Strategie ab, die aus einer gegebenen Optionsmenge die beste wählt.
Die Induktion ankert bei rolls_left = 1, wo keine Entscheidung mehr existiert
und der Wert allein durch die Zielfunktion bestimmt ist.

Zielfunktion ist die Wahrscheinlichkeit, die Runde nicht zu verlieren. Man
verliert nur, wenn jeder Gegner besser abschneidet:

    P(nicht Verlierer) = 1 - Π_j (1 - S_j)

mit S_j der Wahrscheinlichkeit, dass Gegner j schlechter abschneidet. Die
Gegner zerfallen in drei Gruppen:

- offene Vorgänger: alle Würfel sichtbar, Rang bekannt, S_j ist 0 oder 1
- (teil)verdeckte Vorgänger: nur herausgelegte Einsen sichtbar, der letzte
  Wurf ist verdeckt; S_j aus der exakten bedingten Verteilung
- ausstehende Nachfolger: noch nicht gewürfelt; S_j aus der Verteilung einer
  unterstellten Referenzstrategie beim geltenden Wurfbudget
"""

from schocken.classification import classify
from schocken.distribution import (
    hidden_distribution,
    roll_distribution,
    survival_probability_with_ties,
)
from schocken.state import next_states
from schocken.strategies.base import BaseStrategy
from schocken.typedefs import Decision, GameState, PublicPlayerState, RoundContext
from schocken.utils import normalize

Outcome = tuple[tuple[int, ...], int]
JointDistribution = dict[Outcome, float]


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


def value_before_roll(
    state: GameState,
    objective: Objective,
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
        state["must_continue"],
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
    objective: Objective,
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

    if state["rolls_left"] == 1 or not state["must_continue"]:
        final = normalize((1,) * state["held_ones"] + roll)
        candidates.append(objective(classify(final), state["rolls_used"] + 1))

    if state["rolls_left"] > 1:
        for successor in next_states(state, roll):
            candidates.append(value_before_roll(successor, objective, cache))

    return max(candidates)


class OptimalStrategy(BaseStrategy):
    """
    Strategie, die jede Option über die Bellman-Wertfunktion bewertet.

    Die Zielfunktion wird pro Zug aus dem Rundenkontext aufgebaut.

    Args:
        follower_distributions: Tabellierte Nachfolgerverteilungen je Wurfbudget.
        max_rolls: Wurfbudget, falls der Kontext noch keines festlegt.
        fallback_players: Spielerzahl, falls kein Kontext übergeben wird
            (z.B. bei der Enumeration in distribution.py). Im Spiel ohne Wirkung.
    """

    def __init__(
        self,
        follower_distributions: dict[int, JointDistribution],
        max_rolls: int = 3,
        fallback_players: int = 2,
    ):
        self.follower_distributions = follower_distributions
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
        best_value = -1.0

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

    def build_objective(self, context: RoundContext | None) -> Objective:
        """
        Baut die Zielfunktion aus dem aktuellen Rundenkontext.

        Args:
            context: Rundenkontext aus Sicht des Spielers am Zug.

        Returns:
            Zielfunktion für die Bewertung von Endergebnissen.
        """
        table = context["public_table_state"] if context else []
        n_active = context["n_active"] if context else self.fallback_players
        round_budget = context["max_rolls"] if context else None

        open_predecessors, hidden_predecessors = split_predecessors(table)

        return Objective(
            open_predecessors=open_predecessors,
            hidden_predecessors=hidden_predecessors,
            n_followers=n_active - len(table) - 1,
            follower_distributions=self.follower_distributions,
            is_opener=not table,
            max_rolls=round_budget if round_budget is not None else self.max_rolls,
        )
