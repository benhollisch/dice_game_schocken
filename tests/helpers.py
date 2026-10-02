"""Gemeinsame Hilfsfunktionen für die Tests."""

from collections import Counter

from scipy import stats

from schocken.core.typedefs import PublicPlayerState


def ranks_only(distribution: dict) -> dict[tuple[int, ...], float]:
    """Summiert eine gemeinsame Verteilung über die Wurfzahl hinweg."""
    marginal: dict[tuple[int, ...], float] = {}
    for (rank, _), p in distribution.items():
        marginal[rank] = marginal.get(rank, 0.0) + p
    return marginal


def assert_distribution_equal(
    actual: dict, expected: dict, tolerance: float = 1e-12
) -> None:
    """Prüft zwei Verteilungen eintragsweise, in beide Richtungen."""
    for key in set(actual) | set(expected):
        assert abs(actual.get(key, 0.0) - float(expected.get(key, 0))) < tolerance, key


def chi_square_p_value(observed: Counter, expected: dict, n: int) -> float:
    """
    Chi-Quadrat-Anpassungstest einer Stichprobe gegen eine Verteilung.

    Zellen mit erwarteter Häufigkeit unter 5 werden zu einer Restzelle
    zusammengefasst, damit die Chi-Quadrat-Näherung gültig bleibt.
    """
    obs, exp = [], []
    rest_obs, rest_exp = 0, 0.0

    for key, p in expected.items():
        if p * n >= 5:
            obs.append(observed.get(key, 0))
            exp.append(p * n)
        else:
            rest_obs += observed.get(key, 0)
            rest_exp += p * n

    unexpected = sum(v for k, v in observed.items() if k not in expected)
    assert unexpected == 0, "Stichprobe enthält Ausgänge außerhalb der Verteilung"

    if rest_exp > 0:
        obs.append(rest_obs)
        exp.append(rest_exp)

    return stats.chisquare(obs, f_exp=exp).pvalue


def predecessor(seat: int, visible, rolls: int) -> PublicPlayerState:
    """Öffentlicher Tischeintrag eines Vorgängers."""
    return PublicPlayerState(
        player=f"P{seat}", turn_order=seat, visible_state=visible, rolls_used=rolls
    )
