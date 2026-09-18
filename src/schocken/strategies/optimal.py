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
from schocken.types import Decision, GameState, PublicPlayerState
from schocken.utils import normalize


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
        acts_first: Ob der Spieler vor den ausstehenden Gegnern an der Reihe war.
        is_opener: Ob die eigene Wurfzahl das Budget der Nachfolger setzt.
        max_rolls: Wurfbudget der Runde, sofern bereits festgelegt.
    """

    def __init__(
        self,
        theta: tuple[int, ...] | None,
        n_followers: int,
        opponent_distributions: dict[int, dict[tuple[tuple[int, ...], int], float]],
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
        if self.theta is not None and rank >= self.theta:
            return 0.0

        if self.n_followers == 0:
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

    Die Zielfunktion wird beim Aufruf aus dem öffentlichen Tischzustand
    aufgebaut, da theta und die Anzahl der Nachfolger pro Zug variieren.

    Args:
        opponent_distributions: Tabellierte Gegnerverteilungen je Wurfbudget.
        n_players: Gesamtzahl der Spieler in der Runde.
        max_rolls: Wurfbudget der Runde.
        is_opener: Ob dieser Spieler die Runde eröffnet.
    """

    def __init__(
        self,
        opponent_distributions: dict[int, dict[tuple[tuple[int, ...], int], float]],
        n_players: int,
        max_rolls: int = 3,
        is_opener: bool = False,
    ):
        self.opponent_distributions = opponent_distributions
        self.n_players = n_players
        self.max_rolls = max_rolls
        self.is_opener = is_opener

    def choose(
        self,
        options: list[Decision],
        state: GameState,
        roll: tuple[int, ...],
        public_table_state: list[PublicPlayerState] | None = None,
    ) -> Decision:
        objective = self._build_objective(public_table_state)
        cache: dict = {}

        best = None
        best_value = -1.0

        for option in options:
            if option["action"] == "stop":
                value = objective(option["rank"], option["state"]["rolls_used"])
            else:
                value = value_before_roll(option["state"], objective, cache)

            if value > best_value:
                best_value = value
                best = option

        return best

    def _build_objective(
        self, public_table_state: list[PublicPlayerState] | None
    ) -> Objective:
        """
        Baut die Zielfunktion aus dem aktuellen Tischzustand.

        Args:
            public_table_state: Öffentlich sichtbare Zustände der Vorgänger.

        Returns:
            Zielfunktion für die Bewertung von Endergebnissen.
        """
        n_before = len(public_table_state) if public_table_state else 0
        n_followers = self.n_players - n_before - 1

        return Objective(
            theta=worst_public_rank(public_table_state),
            n_followers=n_followers,
            opponent_distributions=self.opponent_distributions,
            acts_first=True,
            is_opener=self.is_opener,
            max_rolls=self.max_rolls,
        )
