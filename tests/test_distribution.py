"""
Tests für joint_distribution und survival_probability_with_ties.

Geprüft werden die Konsistenz der gemeinsamen Verteilung mit der reinen
Rangverteilung sowie Invarianten der Überlebensfunktion mit Tie-Break.
Alle Verteilungen stammen aus der Schwellenstrategie in conftest.py.

Ausführen mit:  pytest tests/test_distribution.py -v
"""

import sys

import pytest

from helpers import assert_distribution_equal, ranks_only
from schocken.probability.survival import (
    survival_probability,
    survival_probability_with_ties,
)

TOLERANCE = 1e-12

PROBES = [
    ((0, 0), "Schock-Out (1,1,1)"),
    ((0, 1), "Schock (6,1,1)"),
    ((0, 4), "Schock (3,1,1)"),
    ((1, 0), "General (6,6,6)"),
    ((2, 0), "Straße (6,5,4)"),
    ((2, 3), "Straße (3,2,1)"),
    ((3, -6, -5, -3), "Hausnummer (6,5,3)"),
    ((3, -4, -4, -2), "Hausnummer (4,4,2)"),
]


# --------------------------------------------------------------------------
# A. Konsistenz der gemeinsamen Verteilung
# --------------------------------------------------------------------------


@pytest.mark.parametrize("budget", [1, 2, 3])
def test_joint_sums_to_one(threshold_joint_tables, budget):
    """Die gemeinsame Verteilung ist normiert."""
    assert abs(sum(threshold_joint_tables[budget].values()) - 1.0) < TOLERANCE


@pytest.mark.parametrize("budget", [1, 2, 3])
def test_joint_rolls_within_budget(threshold_joint_tables, budget):
    """Keine Wurfzahl liegt außerhalb von 1 bis zum Budget."""
    assert {r for _, r in threshold_joint_tables[budget]} <= set(range(1, budget + 1))


@pytest.mark.parametrize("budget", [1, 2, 3])
def test_joint_marginal_matches_opponent_distribution(
    threshold_joint_tables, threshold_rank_tables, budget
):
    """Die Randverteilung über die Wurfzahl entspricht opponent_distribution."""
    assert_distribution_equal(
        ranks_only(threshold_joint_tables[budget]),
        threshold_rank_tables[budget],
        TOLERANCE,
    )


# --------------------------------------------------------------------------
# B. Überlebensfunktion: Sonderfälle
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "rank", [rank for rank, _ in PROBES], ids=[label for _, label in PROBES]
)
def test_ties_vanish_at_full_budget_acting_last(
    threshold_joint_tables, threshold_cumulative_tables, rank
):
    """
    Volles Budget und spätere Position: Jeder Gleichstand geht verloren.

    Kein Gegner kann mehr Würfe verbrauchen als das Budget, und bei gleicher
    Wurfzahl entscheidet die Position gegen den eigenen Spieler. Die Funktion
    mit Ties muss dann mit der ohne Ties übereinstimmen.
    """
    budget = 3
    without = survival_probability(threshold_cumulative_tables[budget], rank)
    with_ties = survival_probability_with_ties(
        threshold_joint_tables[budget], rank, budget, False
    )
    assert abs(with_ties - without) < TOLERANCE


@pytest.mark.parametrize(
    "rank", [rank for rank, _ in PROBES], ids=[label for _, label in PROBES]
)
@pytest.mark.parametrize("rolls", [1, 2, 3])
@pytest.mark.parametrize("acts_first", [True, False])
def test_survival_is_probability(threshold_joint_tables, rank, rolls, acts_first):
    """Alle Werte liegen im Einheitsintervall."""
    value = survival_probability_with_ties(
        threshold_joint_tables[3], rank, rolls, acts_first
    )
    assert -TOLERANCE <= value <= 1.0 + TOLERANCE


# --------------------------------------------------------------------------
# C. Überlebensfunktion: Invarianten über alle erreichbaren Ränge
# --------------------------------------------------------------------------


@pytest.mark.parametrize("budget", [1, 2, 3])
@pytest.mark.parametrize("rolls", [1, 2, 3])
def test_ties_never_lower_survival(
    threshold_joint_tables, threshold_cumulative_tables, budget, rolls
):
    """Die Berücksichtigung von Gleichständen senkt den Wert nie."""
    joint = threshold_joint_tables[budget]
    for rank in {r for r, _ in joint}:
        without = survival_probability(threshold_cumulative_tables[budget], rank)
        last = survival_probability_with_ties(joint, rank, rolls, False)
        assert last >= without - TOLERANCE, rank


@pytest.mark.parametrize("budget", [1, 2, 3])
@pytest.mark.parametrize("rolls", [1, 2, 3])
def test_acting_first_never_hurts(threshold_joint_tables, budget, rolls):
    """Eine frühere Position schadet nie."""
    joint = threshold_joint_tables[budget]
    for rank in {r for r, _ in joint}:
        first = survival_probability_with_ties(joint, rank, rolls, True)
        last = survival_probability_with_ties(joint, rank, rolls, False)
        assert first >= last - TOLERANCE, rank


@pytest.mark.parametrize("budget", [1, 2, 3])
@pytest.mark.parametrize("acts_first", [True, False])
def test_fewer_rolls_never_hurt(threshold_joint_tables, budget, acts_first):
    """Weniger eigene Würfe schaden bei gleichem Rang nie."""
    joint = threshold_joint_tables[budget]
    for rank in {r for r, _ in joint}:
        values = [
            survival_probability_with_ties(joint, rank, rolls, acts_first)
            for rolls in (1, 2, 3)
        ]
        assert all(a >= b - TOLERANCE for a, b in zip(values, values[1:])), rank


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
