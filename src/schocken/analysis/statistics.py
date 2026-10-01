"""
Statistische Auswertung von Schocken-Simulationsergebnissen.

Enthält Funktionen zur Berechnung von Konfidenzintervallen,
Disparitätsmaßen und Signifikanztests.
"""

import math
from scipy import stats


def confidence_interval(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """
    Berechnet ein Konfidenzintervall für einen Anteilswert.

    Args:
        p: Beobachteter Anteilswert.
        n: Anzahl der Beobachtungen.
        z: z-Wert für das Konfidenzintervall (default: 1.96 für 95%).

    Returns:
        Tuple mit unterem und oberem Konfidenzintervall.
    """
    margin = z * math.sqrt(p * (1 - p) / n)
    return (round(p - margin, 6), round(p + margin, 6))


def herfindahl_index(loser_shares: dict[str, float]) -> float:
    """
    Berechnet den Herfindahl-Hirschman-Index (HHI) der Verliererlast.

    Ein hoher HHI deutet auf eine konzentrierte Verliererlast hin,
    d.h. eine Strategie verliert systematisch häufiger.
    Bei gleichmäßiger Verteilung ist HHI = 1/n_players.

    Args:
        loser_shares: Dictionary mit Spielername und Verliereranteil.

    Returns:
        HHI zwischen 0 und 1.
    """
    return round(sum(p**2 for p in loser_shares.values()), 6)


def rosenbluth_index(loser_shares: dict[str, float]) -> float:
    """
    Berechnet den Rosenbluth-Index der Verliererlast.

    Args:
        loser_shares: Dictionary mit Spielername und Verliereranteil.

    Returns:
        Rosenbluth-Index zwischen 0 und 1.
    """
    sorted_shares = sorted(loser_shares.values(), reverse=True)
    denominator = 2 * sum((i + 1) * p for i, p in enumerate(sorted_shares)) - 1
    return round(1 / denominator, 6)


def gini_coefficient(loser_shares: dict[str, float]) -> float:
    """
    Berechnet den Gini-Koeffizienten aus dem Rosenbluth-Index.

    Verwendet die Beziehung K_R = 1 / (n * (1 - D_G)).

    Args:
        loser_shares: Dictionary mit Spielername und Verliereranteil.

    Returns:
        Gini-Koeffizient zwischen 0 und 1.
    """
    n = len(loser_shares)
    k_r = rosenbluth_index(loser_shares)
    return round(1 - 1 / (n * k_r), 6)


def chi_square_test(loser_shares: dict[str, float], n_games: int) -> dict:
    """
    Führt einen Chi-Quadrat-Anpassungstest auf Gleichheit der Verliereranteile durch.

    Nullhypothese: Alle Spieler verlieren gleich häufig (p = 1/n_players).
    Alternative: Mindestens ein Spieler weicht signifikant ab.

    Args:
        loser_shares: Dictionary mit Spielername und Verliereranteil.
        n_games: Anzahl der simulierten Spiele.

    Returns:
        Dictionary mit Teststatistik, p-Wert und Ergebnis der Nullhypothese.
    """
    n_players = len(loser_shares)
    expected_count = n_games / n_players
    observed_counts = [share * n_games for share in loser_shares.values()]

    chi2, p_value = stats.chisquare(observed_counts, f_exp=[expected_count] * n_players)

    return {
        "chi2": round(chi2, 4),
        "p_value": round(p_value, 6),
        "reject_null": p_value < 0.05,
    }


def analyze(results: dict) -> dict:
    """
    Berechnet statistische Kennzahlen für Simulationsergebnisse.

    Args:
        results: Rückgabe von simulate_games().

    Returns:
        Dictionary mit Konfidenzintervallen, HHI und Chi-Quadrat-Test.
    """
    n = results["n_games"]
    loser_shares = results["loser_shares"]

    return {
        "confidence_intervals_95": {
            player: confidence_interval(share, n)
            for player, share in loser_shares.items()
        },
        "herfindahl_index": herfindahl_index(loser_shares),
        "rosenbluth_index": rosenbluth_index(loser_shares),
        "gini_coefficient": gini_coefficient(loser_shares),
        "hhi_baseline": round(1 / len(loser_shares), 6),
        "chi_square_test": chi_square_test(loser_shares, n),
    }


def print_summary(results: dict) -> None:
    """
    Gibt eine formatierte Tabelle der Simulationsergebnisse aus.

    Konfidenzintervalle werden nur bei n_games >= 30 ausgegeben.

    Args:
        results: Rückgabe von simulate_games().
    """
    analysis = analyze(results)
    n = results["n_games"]
    col_width = 32

    def row(label: str, value: str, indent: int = 0) -> None:
        prefix = "  " * indent
        print(f"{prefix}{label:<{col_width - 2 * indent}}{value}")

    print(f"\n{'Measure':<{col_width}}{'Value'}")
    print("-" * 60)

    row("Games Simulated", f"{n:,}")
    row("Avg Rounds per Game", f"{results['avg_rounds']:.2f}")

    print()
    print("Loser Shares")
    for player, share in results["loser_shares"].items():
        row(player, f"{share:.4f}", indent=1)

    if n >= 30:
        print()
        print("Confidence Intervals (95%)")
        for player, (lower, upper) in analysis["confidence_intervals_95"].items():
            row(player, f"{lower:.4f}    -    {upper:.4f}", indent=1)

    print()
    print("Concentration Measures")
    row("Baseline (1/n)", f"{analysis['hhi_baseline']:.6f}", indent=1)
    row("Herfindahl Index", f"{analysis['herfindahl_index']:.6f}", indent=1)
    row("Rosenbluth Index", f"{analysis['rosenbluth_index']:.6f}", indent=1)
    row("Gini Coefficient", f"{analysis['gini_coefficient']:.6f}", indent=1)

    print()
    print("Chi-Square Test")
    chi = analysis["chi_square_test"]
    row("chi2", f"{chi['chi2']:.4f}", indent=1)
    row("p-value", f"{chi['p_value']:.4f}", indent=1)
    row("Reject H0", str(chi["reject_null"]), indent=1)
