"""
Tests für die Batch-Means-Auswertung in analysis/statistics.py.

Die Kernprüfung ist die Überdeckung: Bei vielen künstlichen Verliererfolgen
mit bekanntem wahren Anteil muss das 95%-Intervall den wahren Wert in etwa
95 % der Fälle enthalten. Das wird für unabhängige und für stark abhängige
Folgen geprüft; bei abhängigen versagt das naive Intervall, Batch Means nicht.
"""

import math

import numpy as np
import pytest

from schocken.analysis.statistics import (
    MIN_GAMES_PER_BATCH,
    N_BATCHES,
    batch_means_se,
    confidence_interval,
    holm_correction,
    pairwise_differences,
    print_summary,
    share_estimate,
)
from schocken.engine.game import Player
from schocken.engine.simulation import simulate_games
from schocken.strategies.absolute import GreedyAllIn, StaticThresholdStrategy

ENOUGH_GAMES = N_BATCHES * MIN_GAMES_PER_BATCH


def iid_losers(shares: dict[str, float], n: int, seed: int) -> list[str]:
    """Unabhängige Verliererfolge mit vorgegebenen Anteilen."""
    rng = np.random.default_rng(seed)
    names = list(shares)
    return list(rng.choice(names, size=n, p=list(shares.values())))


def sticky_chains(p: float, stay: float, n: int, reps: int, seed: int) -> np.ndarray:
    """
    Binäre Markov-Ketten mit stationärem Anteil p und starker Autokorrelation.

    Mit Wahrscheinlichkeit stay wird der Vorwert übernommen, sonst neu aus
    Bernoulli(p) gezogen. Die Autokorrelation zum Abstand k ist stay**k.
    """
    rng = np.random.default_rng(seed)
    chains = np.empty((reps, n))
    chains[:, 0] = rng.random(reps) < p
    for t in range(1, n):
        keep = rng.random(reps) < stay
        fresh = rng.random(reps) < p
        chains[:, t] = np.where(keep, chains[:, t - 1], fresh)
    return chains


# --------------------------------------------------------------------------
# batch_means_se
# --------------------------------------------------------------------------


def test_batch_means_needs_enough_games():
    assert batch_means_se(np.zeros(ENOUGH_GAMES - 1)) is None
    assert batch_means_se(np.zeros(ENOUGH_GAMES)) == 0.0


def test_batch_means_matches_naive_for_independent_games():
    """Ohne Abhängigkeit liegen Batch Means und naive Formel nah beieinander."""
    losers = iid_losers({"A": 0.2, "B": 0.8}, n=60_000, seed=1)
    estimate = share_estimate(losers, "A")
    naive = math.sqrt(estimate["share"] * (1 - estimate["share"]) / len(losers))
    assert estimate["se"] is not None
    assert 0.75 < estimate["se"] / naive < 1.25


# --------------------------------------------------------------------------
# Überdeckung der Intervalle
# --------------------------------------------------------------------------


def coverage(chains: np.ndarray, p: float) -> tuple[float, float]:
    """Anteil der Intervalle, die den wahren Wert enthalten: (Batch Means, naiv)."""
    hits_bm = hits_naive = 0
    for chain in chains:
        losers = ["A" if x else "B" for x in chain]
        estimate = share_estimate(losers, "A")
        lower, upper = estimate["ci_95"]  # type: ignore[misc]
        hits_bm += lower <= p <= upper
        naive_lower, naive_upper = confidence_interval(estimate["share"], len(chain))
        hits_naive += naive_lower <= p <= naive_upper
    return hits_bm / len(chains), hits_naive / len(chains)


def test_coverage_independent_games():
    chains = sticky_chains(p=0.2, stay=0.0, n=3_000, reps=400, seed=2)
    bm, naive = coverage(chains, p=0.2)
    assert 0.91 <= bm <= 0.99
    assert 0.91 <= naive <= 0.99


def test_coverage_dependent_games():
    """
    Stark abhängige Spiele: Das naive Intervall ist viel zu schmal und trifft
    den wahren Wert deutlich seltener; Batch Means hält die 95 % ungefähr.
    """
    chains = sticky_chains(p=0.2, stay=0.8, n=6_000, reps=300, seed=3)
    bm, naive = coverage(chains, p=0.2)
    assert bm >= 0.89
    assert naive <= 0.75


# --------------------------------------------------------------------------
# Holm-Korrektur
# --------------------------------------------------------------------------


def test_holm_known_values():
    """
    Sortiert: 0.005·4 = 0.02, 0.01·3 = 0.03, 0.03·2 = 0.06, 0.04·1 = 0.04 → 0.06
    (Monotonie). Rückgabe in Eingabereihenfolge.
    """
    adjusted = holm_correction([0.01, 0.04, 0.03, 0.005])
    assert adjusted == pytest.approx([0.03, 0.06, 0.06, 0.02])


def test_holm_caps_at_one_and_handles_empty():
    assert holm_correction([0.5, 0.6]) == pytest.approx([1.0, 1.0])
    assert holm_correction([]) == []


# --------------------------------------------------------------------------
# Paarvergleiche
# --------------------------------------------------------------------------

SHARES = {"A": 0.15, "B": 0.25, "C": 0.25, "D": 0.35}


@pytest.fixture(scope="module")
def iid_sample() -> list[str]:
    return iid_losers(SHARES, n=40_000, seed=4)


def test_all_pairs_or_reference(iid_sample):
    players = list(SHARES)
    assert len(pairwise_differences(iid_sample, players)) == 6
    with_reference = pairwise_differences(iid_sample, players, reference="A")
    assert [(r["first"], r["second"]) for r in with_reference] == [
        ("A", "B"),
        ("A", "C"),
        ("A", "D"),
    ]


def test_unknown_reference_raises(iid_sample):
    with pytest.raises(ValueError):
        pairwise_differences(iid_sample, list(SHARES), reference="X")


def test_difference_equals_difference_of_shares(iid_sample):
    for entry in pairwise_differences(iid_sample, list(SHARES)):
        expected = (
            share_estimate(iid_sample, entry["first"])["share"]
            - share_estimate(iid_sample, entry["second"])["share"]
        )
        assert entry["difference"] == pytest.approx(expected)


def test_difference_se_includes_negative_covariance(iid_sample):
    """
    Bei unabhängigen Spielen gilt pro Spiel Var(d) = pA + pB - (pA - pB)^2.
    Die Summe der Einzelvarianzen allein wäre zu klein.
    """
    n = len(iid_sample)
    (entry,) = [
        e
        for e in pairwise_differences(iid_sample, list(SHARES))
        if e["second"] == "D" and e["first"] == "A"
    ]
    pa, pd = SHARES["A"], SHARES["D"]
    with_cov = math.sqrt((pa + pd - (pa - pd) ** 2) / n)
    without_cov = math.sqrt((pa * (1 - pa) + pd * (1 - pd)) / n)
    assert entry["se"] is not None
    assert abs(entry["se"] - with_cov) < abs(entry["se"] - without_cov)
    assert 0.75 < entry["se"] / with_cov < 1.25


def test_significance(iid_sample):
    results = {
        (e["first"], e["second"]): e
        for e in pairwise_differences(iid_sample, list(SHARES))
    }
    assert results[("A", "D")]["significant"] is True
    assert results[("B", "C")]["significant"] is False


def test_too_few_games_gives_no_interval():
    losers = iid_losers(SHARES, n=ENOUGH_GAMES - 1, seed=5)
    for entry in pairwise_differences(losers, list(SHARES)):
        assert entry["ci_95"] is None
        assert entry["p_value_holm"] is None
        assert entry["significant"] is None


def test_player_without_losses_is_included():
    losers = ["A"] * ENOUGH_GAMES
    assert share_estimate(losers, "B")["share"] == 0.0
    (entry,) = pairwise_differences(losers, ["A", "B"])
    assert entry["difference"] == 1.0
    assert entry["significant"] is True


# --------------------------------------------------------------------------
# Zusammenspiel mit simulate_games
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def simulation_results() -> dict:
    players = [
        Player("Greedy", GreedyAllIn()),
        Player("Threshold", StaticThresholdStrategy(threshold=(4, 3, 2))),
        Player("Threshold 2", StaticThresholdStrategy(threshold=(4, 3, 2))),
    ]
    return simulate_games(players, n_games=ENOUGH_GAMES)


def test_simulation_returns_loser_sequence(simulation_results):
    losers = simulation_results["losers"]
    assert len(losers) == simulation_results["n_games"]
    assert simulation_results["players"] == ["Greedy", "Threshold", "Threshold 2"]
    for name, share in simulation_results["loser_shares"].items():
        assert losers.count(name) / len(losers) == pytest.approx(share)


def test_print_summary_runs(simulation_results, capsys):
    print_summary(simulation_results, reference="Greedy")
    output = capsys.readouterr().out
    assert "Batch Means" in output
    assert "Greedy - Threshold" in output
