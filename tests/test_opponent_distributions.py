"""
Tests für die Gegnerverteilungen und die Zielfunktion der OptimalStrategy.

Drei Gegnergruppen werden geprüft:

- (teil)verdeckte Vorgänger: bedingte Verteilung des verdeckten letzten Wurfs
- ausstehende Nachfolger: unbedingte Verteilung unter einer Referenzstrategie
- offene Vorgänger: Zuordnung und Tie-Break

Jede Verteilung wird zweifach geprüft: gegen analytisch hergeleitete
Referenzwerte und gegen eine Monte-Carlo-Stichprobe aus play_turn().

Ausführen mit:  pytest testing/test_opponent_distributions.py -v
"""

import random
import sys
from collections import Counter
from fractions import Fraction as F

import pytest

from helpers import (
    assert_distribution_equal,
    chi_square_p_value,
    predecessor,
    ranks_only,
)
from schocken.core.classification import classify
from schocken.probability.enumeration import (
    hidden_distribution,
    rank_distribution,
)
from schocken.probability.survival import survival_probability_with_ties
from schocken.engine.game import play_turn
from schocken.core.state import decide_after_roll, initial_state
from schocken.strategies.absolute import (
    GreedyAllIn,
    StaticThresholdStrategy,
)
from schocken.strategies.optimizer.objectives import (
    Objective,
    split_predecessors,
)
from schocken.strategies.optimizer.strategy import OptimalStrategy
from schocken.core.typedefs import RoundContext

TOLERANCE = 1e-12
P_VALUE_THRESHOLD = 1e-3
N_MONTE_CARLO = 30_000


# --------------------------------------------------------------------------
# A. (Teil)verdeckte Vorgänger: analytische Referenzwerte
# --------------------------------------------------------------------------


def test_hidden_h0_matches_single_roll_categories():
    """h = 0: ein verdeckter Wurf mit drei Würfeln, Kategorien aus Tabelle 1."""
    dist = ranks_only(hidden_distribution(held_ones=0, rolls_used=3))

    categories: dict[str, float] = Counter()
    for rank, p in dist.items():
        if rank == (0, 0):
            categories["schock_out"] += p
        else:
            categories[
                {0: "schock", 1: "general", 2: "strasse", 3: "haus"}[rank[0]]
            ] += p

    assert abs(categories["schock_out"] - 1 / 216) < TOLERANCE
    assert abs(categories["schock"] - 15 / 216) < TOLERANCE
    assert abs(categories["general"] - 5 / 216) < TOLERANCE
    assert abs(categories["strasse"] - 24 / 216) < TOLERANCE
    assert abs(categories["haus"] - 171 / 216) < TOLERANCE


def test_hidden_h0_single_ranks():
    """h = 0: Stichproben einzelner Ränge."""
    dist = ranks_only(hidden_distribution(held_ones=0, rolls_used=3))
    assert abs(dist[(0, 3)] - 3 / 216) < TOLERANCE  # Schock 4: drei Permutationen
    assert abs(dist[(1, 0)] - 1 / 216) < TOLERANCE  # General 6
    assert abs(dist[(2, 0)] - 6 / 216) < TOLERANCE  # Straße 6-5-4: sechs Permutationen


def test_hidden_h1_full_rank_distribution():
    """h = 1: Endbild (1, x, y) mit zwei frisch geworfenen Würfeln, auf Rangebene."""
    expected: dict[tuple[int, ...], F] = {(0, 0): F(1, 36)}

    for a in range(2, 7):
        expected[(0, 7 - a)] = F(2, 36)  # Schock mit Beizahl a
        expected[(3, -a, -a, -1)] = F(1, 36)  # Pasch-Hausnummer (a, a, 1)

    expected[(2, 3)] = F(2, 36)  # Straße (3, 2, 1)

    for a in range(3, 7):
        for b in range(2, a):
            if (a, b) != (3, 2):
                expected[(3, -a, -b, -1)] = F(2, 36)  # gemischte Hausnummer

    assert sum(expected.values()) == 1
    assert_distribution_equal(ranks_only(hidden_distribution(1, 3)), expected)


def test_hidden_h2_full_rank_distribution():
    """h = 2: ein verdeckter Würfel, je 1/6 Schock-Out und Schock 6 bis 2."""
    expected = {(0, k): F(1, 6) for k in range(6)}
    assert_distribution_equal(ranks_only(hidden_distribution(2, 3)), expected)


def test_hidden_h3_is_certain_shock_out():
    """h = 3: kein Würfel mehr im Becher, Schock-Out mit Sicherheit."""
    assert_distribution_equal(hidden_distribution(3, 3), {((0, 0), 3): 1})


def test_hidden_carries_rolls_used():
    """Die Wurfzahl des Vorgängers steht unverändert in jedem Eintrag."""
    for rolls in (1, 2, 3):
        assert {r for _, r in hidden_distribution(1, rolls)} == {rolls}


# --------------------------------------------------------------------------
# A. (Teil)verdeckte Vorgänger: Monte-Carlo und Strategieunabhängigkeit
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "strategy",
    [GreedyAllIn(), StaticThresholdStrategy(threshold=(4, 3, 2))],
    ids=["greedy", "threshold_strasse"],
)
def test_hidden_matches_simulation_for_any_strategy(strategy):
    """
    Erzwungen gestoppte Züge, gruppiert nach h, folgen der bedingten Verteilung.

    Mit zwei verschiedenen Strategien geprüft: Die bedingte Verteilung darf
    nicht von der Strategie abhängen.
    """
    random.seed(12345)
    budget = 3
    samples: dict[int, Counter] = {h: Counter() for h in range(4)}

    for _ in range(N_MONTE_CARLO):
        result = play_turn(strategy, budget)
        visible = result["visible_state"]
        if visible is not None and len(visible) == 3:
            continue  # offen, nicht Gegenstand dieses Tests
        held = len(visible) if visible else 0
        samples[held][(result["rank"], result["rolls_used"])] += 1

    tested = 0
    for held, observed in samples.items():
        n = sum(observed.values())
        if n < 500:
            continue
        p = chi_square_p_value(observed, hidden_distribution(held, budget), n)
        assert p > P_VALUE_THRESHOLD, f"h={held}, n={n}, p={p}"
        tested += 1

    assert tested >= 2, "zu wenige Gruppen mit ausreichender Stichprobe"


# --------------------------------------------------------------------------
# B. Ausstehende Nachfolger
# --------------------------------------------------------------------------


def test_follower_budget_one_equals_fully_hidden(follower_tables):
    """Budget 1: ein einziger Wurf, identisch mit einem verdeckten Wurf bei h = 0."""
    assert_distribution_equal(follower_tables[1], hidden_distribution(0, 1))


def test_follower_shock_out_reference_value(follower_tables):
    """Schock-Out nach drei Würfen unter GreedyAllIn, exakter Bruch aus dem Paper."""
    p = ranks_only(follower_tables[3])[(0, 0)]
    assert abs(p - 54271 / 629856) < TOLERANCE


@pytest.mark.parametrize("budget", [1, 2, 3])
def test_follower_marginal_matches_rank_distribution(follower_tables, budget):
    """Randverteilung der gemeinsamen Verteilung entspricht rank_distribution."""
    reference = rank_distribution(initial_state(n_rolls=budget), GreedyAllIn())
    assert_distribution_equal(ranks_only(follower_tables[budget]), reference)


@pytest.mark.parametrize("budget", [1, 2, 3])
def test_follower_matches_simulation(follower_tables, budget):
    """Gemeinsame Häufigkeit von Rang und Wurfzahl aus play_turn."""
    random.seed(budget)
    observed: Counter = Counter()
    for _ in range(N_MONTE_CARLO):
        result = play_turn(GreedyAllIn(), budget)
        observed[(result["rank"], result["rolls_used"])] += 1

    p = chi_square_p_value(observed, follower_tables[budget], N_MONTE_CARLO)
    assert p > P_VALUE_THRESHOLD, f"budget={budget}, p={p}"


# --------------------------------------------------------------------------
# C. Zuordnung der Vorgänger
# --------------------------------------------------------------------------


def test_split_opener_stopped_early_is_open():
    """Startspieler stoppt nach einem Wurf mit Straße: offen, nicht verdeckt."""
    open_, hidden = split_predecessors([predecessor(0, (6, 5, 4), 1)])
    assert open_ == [((2, 0), 1)]
    assert hidden == []


def test_split_partially_hidden_and_hidden():
    """Teilverdeckt mit ein oder zwei Einsen, vollständig verdeckt ohne Einsen."""
    table = [
        predecessor(0, (1, 1), 3),
        predecessor(1, (1,), 3),
        predecessor(2, None, 3),
    ]
    open_, hidden = split_predecessors(table)
    assert open_ == []
    assert hidden == [(2, 3), (1, 3), (0, 3)]


def test_split_three_held_ones_is_open_shock_out():
    """Drei gehaltene Einsen sind ein vollständig sichtbares Bild."""
    open_, hidden = split_predecessors([predecessor(0, (1, 1, 1), 3)])
    assert open_ == [((0, 0), 3)]
    assert hidden == []


# --------------------------------------------------------------------------
# D. Zielfunktion und Strategie
# --------------------------------------------------------------------------


def test_objective_against_partially_hidden_worked_example(follower_tables):
    """
    Beispiel aus ERKENNTNISSE.md, Abschnitt 11.

    Vorgänger zeigt (1, 1) nach drei Würfen. Eigener Schock 4 überlebt mit
    3/6 nach zwei Würfen (Gleichstand über weniger Würfe gewonnen) und mit
    2/6 nach drei Würfen (Gleichstand über frühere Position verloren).
    """
    objective = Objective(
        open_predecessors=[],
        hidden_predecessors=[(2, 3)],
        n_followers=0,
        follower_distributions=follower_tables,
        is_opener=False,
        max_rolls=3,
    )
    schock_4 = classify((4, 1, 1))
    assert abs(objective(schock_4, 2) - 3 / 6) < TOLERANCE
    assert abs(objective(schock_4, 3) - 2 / 6) < TOLERANCE
    assert objective(classify((5, 3, 2)), 1) == 0.0


def test_objective_beating_one_open_predecessor_is_safe(follower_tables):
    """Straße gegen offene Hausnummer: sicher nicht Verlierer, trotz Nachfolger."""
    objective = Objective(
        open_predecessors=[(classify((6, 5, 5)), 3)],
        hidden_predecessors=[],
        n_followers=1,
        follower_distributions=follower_tables,
        is_opener=False,
        max_rolls=3,
    )
    assert objective(classify((4, 3, 2)), 1) == 1.0


def test_objective_tie_with_open_predecessor(follower_tables):
    """Gleichstand mit offenem Vorgänger: weniger Würfe gewinnt, gleich viele verliert."""
    objective = Objective(
        open_predecessors=[(classify((4, 3, 2)), 2)],
        hidden_predecessors=[],
        n_followers=0,
        follower_distributions=follower_tables,
        is_opener=False,
        max_rolls=3,
    )
    assert objective(classify((4, 3, 2)), 1) == 1.0
    assert objective(classify((4, 3, 2)), 2) == 0.0


def test_objective_two_players_equals_survival(follower_tables):
    """Bei zwei Spielern fallen „nicht verlieren“ und „schlagen“ zusammen."""
    objective = Objective([], [], 1, follower_tables, is_opener=True, max_rolls=3)
    rank = classify((6, 5, 4))
    expected = survival_probability_with_ties(follower_tables[1], rank, 1, True)
    assert abs(objective(rank, 1) - expected) < TOLERANCE


def test_objective_more_followers_is_safer(follower_tables):
    """Ab drei Spielern: mehr Nachfolger machen Nicht-Verlieren wahrscheinlicher."""
    rank = classify((6, 5, 3))
    values = [
        Objective([], [], k, follower_tables, is_opener=True, max_rolls=3)(rank, 1)
        for k in (1, 2, 3, 4)
    ]
    assert values == sorted(values)
    assert values[-1] > values[0]


def test_strategy_does_not_stop_against_partially_hidden(follower_tables):
    """Der beobachtete Fehler: (5, 3, 2) gegen einen Vorgänger mit (1, 1)."""
    context = RoundContext(
        n_active=2,
        max_rolls=3,
        public_table_state=[predecessor(0, (1, 1), 3)],
    )
    strategy = OptimalStrategy(follower_distributions=follower_tables)
    decision = decide_after_roll(initial_state(n_rolls=3), (5, 3, 2), strategy, context)
    assert decision["action"] == "continue"


def test_strategy_stops_when_safe(follower_tables):
    """Straße gegen offene Hausnummer: Stoppen ist sicher und wird gewählt."""
    context = RoundContext(
        n_active=3,
        max_rolls=3,
        public_table_state=[predecessor(0, (6, 5, 5), 3)],
    )
    strategy = OptimalStrategy(follower_distributions=follower_tables)
    decision = decide_after_roll(initial_state(n_rolls=3), (4, 3, 2), strategy, context)
    assert decision["action"] == "stop"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
