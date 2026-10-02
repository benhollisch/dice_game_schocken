"""Gemeinsame Fixtures für die Tests."""

import pytest

from schocken.core.classification import classify
from schocken.core.state import initial_state
from schocken.probability.enumeration import (
    joint_distribution,
    opponent_distribution,
)
from schocken.probability.survival import cumulative_table
from schocken.strategies.absolute import GreedyAllIn, StaticThresholdStrategy

BUDGETS = (1, 2, 3)


@pytest.fixture(scope="session")
def follower_tables() -> dict[int, dict]:
    """Nachfolgerverteilungen unter GreedyAllIn, je Wurfbudget."""
    return {
        m: joint_distribution(initial_state(n_rolls=m), GreedyAllIn()) for m in BUDGETS
    }


@pytest.fixture(scope="session")
def threshold_strategy() -> StaticThresholdStrategy:
    """Schwellenstrategie, die ab Hausnummer (6, 5, 5) stoppt."""
    return StaticThresholdStrategy(threshold=classify((6, 5, 5)))


@pytest.fixture(scope="session")
def threshold_joint_tables(threshold_strategy) -> dict[int, dict]:
    """Gemeinsame Verteilungen von Rang und Wurfzahl unter der Schwellenstrategie."""
    return {
        m: joint_distribution(initial_state(n_rolls=m), threshold_strategy)
        for m in BUDGETS
    }


@pytest.fixture(scope="session")
def threshold_rank_tables(threshold_strategy) -> dict[int, dict]:
    """Rangverteilungen ohne Wurfzahl unter der Schwellenstrategie."""
    return {m: opponent_distribution(m, threshold_strategy) for m in BUDGETS}


@pytest.fixture(scope="session")
def threshold_cumulative_tables(
    threshold_rank_tables,
) -> dict[int, tuple[list[tuple[int, ...]], list[float]]]:
    """Kumulierte Rangverteilungen unter der Schwellenstrategie."""
    return {m: cumulative_table(dist) for m, dist in threshold_rank_tables.items()}
