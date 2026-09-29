"""
Erwartungswertoptimale Politik durch Rückwärtsinduktion.

Berechnet die Wertfunktion eines Zuges über die Bellman-Rekursion und leitet
daraus eine Strategie ab, die aus einer gegebenen Optionsmenge die beste wählt.
Die Induktion ankert bei rolls_left = 1, wo keine Entscheidung mehr existiert
und der Wert allein durch die Zielfunktion bestimmt ist.
"""

from schocken.classification import classify
from schocken.distribution import roll_distribution, survival_probability_with_ties
from schocken.state import next_states
from schocken.strategies.base import BaseStrategy, worst_public_rank
from schocken.types import Decision, GameState, RoundContext
from schocken.utils import normalize

JointDistribution = dict[tuple[tuple[int, ...], int], float]


class Objective:
    """
    Zielfunktion für die Rundenverlust-Minimierung (Option A).

    Bewertet ein Endergebnis aus Rang und verbrauchter Wurfzahl. Ein Rang ab
    dem Schwellenrang theta verliert sicher gegen einen bereits
    abgeschlossenen Gegner; andernfalls ist der Wert die Wahrscheinlichkeit,
    dass alle noch ausstehenden Gegner schlechter abschneiden.

    Args:
        theta: Schlechtester öffentlich sichtbarer Rang am Tisch, oder None.
        n_followers: Anzahl der Spieler, die nach diesem Zug noch folgen.
        opponent_distributions: Gemeinsame Verteilungen über Rang und Wurfzahl,
            je Wurfbudget des Gegners.
        acts_first: Ob der Spieler vor den ausstehenden Gegnern an der Reihe ist.
        is_opener: Ob die eigene Wurfzahl das Budget der Nachfolger setzt.
        max_rolls: Wurfbudget der Runde, sofern bereits festgelegt.
    """

    def __init__(
        self,
        theta: tuple[int, ...] | None,
        n_followers: int,
        opponent_distributions: dict[int, JointDistribution],
        acts_first: bool = True,
        is_opener: bool = False,
        max_rolls: int = 3,
    ):
        self.theta = theta
        self.n_followers = n_followers
        self.opponent_distributions = opponent_distributions
        self.acts_first = acts_first
        self.is_opener = is_opener
        self.max_rolls = max_rolls

    def __call__(self, rank: tuple[int, ...], rolls_used: int) -> float:
        """
        Bewertet ein Endergebnis.

        Args:
            rank: Erreichter Endrang.
            rolls_used: Verbrauchte Wurfzahl.

        Returns:
            Wahrscheinlichkeit, die Runde nicht zu verlieren.
        """
        # TODO: decide_after_roll wird ohne RoundContext aufgerufen. Für reaktive
        # Strategien entspricht die Verteilung daher nicht dem tatsächlichen
        # Spielverhalten. OptimalStrategy fällt dabei auf fallback_players zurück.
        if self.theta is not None and rank >= self.theta:
            return 0.0

        if self.n_followers <= 0:
            return 1.0

        budget = rolls_used if self.is_opener else self.max_rolls
        distribution = self.opponent_distributions[budget]

        survival = survival_probability_with_ties(
            distribution, rank, rolls_used, self.acts_first
        )
        return survival**self.n_followers


def value_before_roll(
    state: GameState,
    objective: Objective,
    cache: dict | None = None,
) -> float:
    """
    Berechnet den Wert eines Zustands unmittelbar vor dem Wurf.

    Entspricht W(s) in der Bellman-Formulierung: der Erwartungswert über alle
    möglichen Würfe des jeweils besten erreichbaren Werts danach.

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
    Berechnet den Wert eines Zustands nach beobachtetem Wurf.

    Entspricht Q(s, r) in der Bellman-Formulierung: das Maximum über die
    zulässigen Aktionen. Stoppen ist ausgeschlossen, solange must_continue
    gesetzt ist; Weiterwürfeln entfällt beim letzten Wurf.

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

    Die Zielfunktion wird pro Zug aus dem Rundenkontext aufgebaut, da theta,
    die Anzahl der Nachfolger, die Startspielerrolle und das Wurfbudget von
    Zug zu Zug variieren.

    Args:
        opponent_distributions: Tabellierte Gegnerverteilungen je Wurfbudget.
        max_rolls: Wurfbudget, falls der Kontext noch keines festlegt.
        fallback_players: Spielerzahl, falls kein Kontext übergeben wird
            (z.B. bei der Enumeration in distribution.py). Im Spiel ohne Wirkung.
    """

    def __init__(
        self,
        opponent_distributions: dict[int, JointDistribution],
        max_rolls: int = 3,
        fallback_players: int = 2,
    ):
        self.opponent_distributions = opponent_distributions
        self.max_rolls = max_rolls
        self.fallback_players = fallback_players

    def choose(
        self,
        options: list[Decision],
        state: GameState,
        roll: tuple[int, ...],
        context: RoundContext | None = None,
    ) -> Decision:
        objective = self._build_objective(context)
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

    def _build_objective(self, context: RoundContext | None) -> Objective:
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
        n_before = len(table)

        return Objective(
            theta=worst_public_rank(table),
            n_followers=n_active - n_before - 1,
            opponent_distributions=self.opponent_distributions,
            acts_first=True,
            is_opener=(n_before == 0),
            max_rolls=round_budget if round_budget is not None else self.max_rolls,
        )
