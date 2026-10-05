"""
Statistische Auswertung von Schocken-Simulationsergebnissen.

Enthält Funktionen zur Berechnung von Konfidenzintervallen,
Disparitätsmaßen und Signifikanztests.

Die Batch-Means-Verfahren arbeiten auf der Folge der Spielverlierer und
setzen keine Unabhängigkeit der Spiele voraus. Sie sind damit unabhängig
davon gültig, wie der Versuchsaufbau die Spiele aneinanderreiht.
"""

import math
from collections.abc import Sequence
from itertools import combinations
from typing import TypedDict

import numpy as np
from scipy import stats

N_BATCHES = 30
MIN_GAMES_PER_BATCH = 30


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


# --------------------------------------------------------------------------
# Batch Means: Intervalle ohne Unabhängigkeitsannahme
# --------------------------------------------------------------------------


class ShareEstimate(TypedDict):
    """Verliereranteil eines Spielers mit Batch-Means-Unsicherheit."""

    share: float
    se: float | None
    ci_95: tuple[float, float] | None


class PairwiseDifference(TypedDict):
    """Differenz der Verliereranteile zweier Spieler."""

    first: str
    second: str
    difference: float
    se: float | None
    ci_95: tuple[float, float] | None
    p_value: float | None
    p_value_holm: float | None
    significant: bool | None


def batch_means_se(
    values: Sequence[float] | np.ndarray, n_batches: int = N_BATCHES
) -> float | None:
    """
    Schätzt den Standardfehler eines Mittelwerts aus einer abhängigen Folge.

    Die Folge wird in n_batches gleich lange, aufeinanderfolgende Blöcke
    geteilt. Die Streuung der Blockmittel ergibt den Standardfehler, ohne
    eine Annahme über die Korrelation zwischen den Werten. Überzählige Werte
    am Ende, die keinen vollen Block füllen, gehen nicht in die Schätzung ein.

    Args:
        values: Folge von Werten in zeitlicher Reihenfolge, je Spiel einer.
        n_batches: Anzahl der Blöcke.

    Returns:
        Standardfehler des Mittelwerts, oder None, wenn ein Block weniger
        als MIN_GAMES_PER_BATCH Werte enthielte.
    """
    data = np.asarray(values, dtype=float)
    batch_size = len(data) // n_batches
    if batch_size < MIN_GAMES_PER_BATCH:
        return None

    batch_means = data[: n_batches * batch_size].reshape(n_batches, batch_size).mean(1)
    return float(batch_means.std(ddof=1) / math.sqrt(n_batches))


def _t_quantile(n_batches: int = N_BATCHES, level: float = 0.95) -> float:
    """Quantil der t-Verteilung für ein zweiseitiges Intervall aus Blockmitteln."""
    return float(stats.t.ppf(0.5 + level / 2, df=n_batches - 1))


def loss_indicator(losers: Sequence[str], player: str) -> np.ndarray:
    """Folge mit 1 für jedes Spiel, das der Spieler verloren hat, sonst 0."""
    return np.fromiter((loser == player for loser in losers), dtype=float)


def share_estimate(
    losers: Sequence[str], player: str, n_batches: int = N_BATCHES
) -> ShareEstimate:
    """
    Schätzt den Verliereranteil eines Spielers mit Batch-Means-Intervall.

    Args:
        losers: Verlierer je Spiel, in Spielreihenfolge.
        player: Name des Spielers.
        n_batches: Anzahl der Blöcke.

    Returns:
        Anteil, Standardfehler und 95%-Intervall. Standardfehler und
        Intervall sind None, wenn zu wenige Spiele vorliegen.
    """
    indicator = loss_indicator(losers, player)
    share = float(indicator.mean())
    se = batch_means_se(indicator, n_batches)
    if se is None:
        return ShareEstimate(share=share, se=None, ci_95=None)

    margin = _t_quantile(n_batches) * se
    return ShareEstimate(share=share, se=se, ci_95=(share - margin, share + margin))


def holm_correction(p_values: Sequence[float]) -> list[float]:
    """
    Korrigiert p-Werte nach Holm für mehrfaches Testen.

    Die p-Werte werden aufsteigend sortiert; der i-te kleinste (ab 0 gezählt)
    wird mit (m - i) multipliziert. Anschließend wird die Folge monoton
    gemacht und auf 1 begrenzt. Die Reihenfolge der Rückgabe entspricht der
    Eingabe.

    Args:
        p_values: Unkorrigierte p-Werte.

    Returns:
        Korrigierte p-Werte in der Reihenfolge der Eingabe.
    """
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running_max = 0.0
    for rank, index in enumerate(order):
        running_max = max(running_max, (m - rank) * p_values[index])
        adjusted[index] = min(1.0, running_max)
    return adjusted


def pairwise_differences(
    losers: Sequence[str],
    players: Sequence[str],
    reference: str | None = None,
    n_batches: int = N_BATCHES,
    alpha: float = 0.05,
) -> list[PairwiseDifference]:
    """
    Vergleicht die Verliereranteile von Spielerpaaren.

    Pro Spiel wird d_t = 1[erster verliert] - 1[zweiter verliert] gebildet.
    Der Standardfehler des Mittelwerts von d_t per Batch Means enthält damit
    sowohl die negative Kovarianz (nie verlieren beide) als auch eine
    eventuelle Abhängigkeit zwischen den Spielen.

    Ohne Referenz werden alle Paare verglichen, mit Referenz nur die Referenz
    gegen jeden anderen Spieler. Die p-Werte werden über alle durchgeführten
    Vergleiche nach Holm korrigiert.

    Args:
        losers: Verlierer je Spiel, in Spielreihenfolge.
        players: Namen aller Spieler.
        reference: Optionaler Spieler, gegen den alle anderen verglichen werden.
        n_batches: Anzahl der Blöcke.
        alpha: Signifikanzniveau nach Holm-Korrektur.

    Returns:
        Ein Eintrag je Paar. difference ist Anteil(first) - Anteil(second);
        negativ heißt also, first verliert seltener.

    Raises:
        ValueError: Wenn die Referenz nicht unter den Spielern ist.
    """
    if reference is not None:
        if reference not in players:
            raise ValueError(f"Referenz {reference!r} ist kein Spieler.")
        pairs = [(reference, other) for other in players if other != reference]
    else:
        pairs = list(combinations(players, 2))

    quantile = _t_quantile(n_batches)
    results: list[PairwiseDifference] = []
    for first, second in pairs:
        d = loss_indicator(losers, first) - loss_indicator(losers, second)
        difference = float(d.mean())
        se = batch_means_se(d, n_batches)

        if se is None:
            ci, p_value = None, None
        elif se == 0.0:
            ci = (difference, difference)
            p_value = 1.0 if difference == 0.0 else 0.0
        else:
            ci = (difference - quantile * se, difference + quantile * se)
            t_stat = difference / se
            p_value = float(2 * stats.t.sf(abs(t_stat), df=n_batches - 1))

        results.append(
            PairwiseDifference(
                first=first,
                second=second,
                difference=difference,
                se=se,
                ci_95=ci,
                p_value=p_value,
                p_value_holm=None,
                significant=None,
            )
        )

    tested = [r for r in results if r["p_value"] is not None]
    adjusted = holm_correction([r["p_value"] for r in tested])  # type: ignore[misc]
    for entry, p_holm in zip(tested, adjusted):
        entry["p_value_holm"] = p_holm
        entry["significant"] = p_holm < alpha

    return results


def analyze(results: dict, reference: str | None = None) -> dict:
    """
    Berechnet statistische Kennzahlen für Simulationsergebnisse.

    Die naiven Intervalle unterstellen unabhängige Spiele, die Batch-Means-
    Intervalle nicht. Beide werden vorerst parallel ausgegeben.

    Args:
        results: Rückgabe von simulate_games().
        reference: Optionaler Spieler für die Paarvergleiche; ohne Referenz
            werden alle Paare verglichen.

    Returns:
        Dictionary mit Konfidenzintervallen, HHI, Chi-Quadrat-Test und
        Paarvergleichen.
    """
    n = results["n_games"]
    loser_shares = results["loser_shares"]
    losers = results["losers"]
    players = results["players"]

    return {
        "batch_means": {player: share_estimate(losers, player) for player in players},
        "pairwise_differences": pairwise_differences(losers, players, reference),
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


def print_summary(results: dict, reference: str | None = None) -> None:
    """
    Gibt eine formatierte Tabelle der Simulationsergebnisse aus.

    Naive Konfidenzintervalle werden nur bei n_games >= 30 ausgegeben,
    Batch-Means-Intervalle und Paarvergleiche erst ab N_BATCHES *
    MIN_GAMES_PER_BATCH Spielen.

    Args:
        results: Rückgabe von simulate_games().
        reference: Optionaler Spieler für die Paarvergleiche; ohne Referenz
            werden alle Paare verglichen.
    """
    analysis = analyze(results, reference)
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
    print("Confidence Intervals (95%, Batch Means)")
    for player in sorted(analysis["batch_means"]):
        ci = analysis["batch_means"][player]["ci_95"]
        text = "-" if ci is None else f"{ci[0]:.4f}    -    {ci[1]:.4f}"
        row(player, text, indent=1)

    print()
    title = "Pairwise Differences (first - second, Holm-corrected)"
    if reference is not None:
        title += f", reference: {reference.strip()}"
    print(title)
    pairs = analysis["pairwise_differences"]
    labels = [f"{e['first'].strip()} - {e['second'].strip()}" for e in pairs]
    label_width = max((len(label) for label in labels), default=0) + 2
    for label, entry in zip(labels, pairs):
        if entry["ci_95"] is None:
            print(
                f"  {label:<{label_width}}{entry['difference']:+.4f}   (zu wenige Spiele)"
            )
            continue
        lower, upper = entry["ci_95"]
        marker = "*" if entry["significant"] else " "
        print(
            f"  {label:<{label_width}}{entry['difference']:+.4f}"
            f"  [{lower:+.4f}, {upper:+.4f}]  p={entry['p_value_holm']:.4f} {marker}"
        )

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
