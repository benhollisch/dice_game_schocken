"""
Überlebenswahrscheinlichkeiten gegen Gegnerverteilungen.

Enthält kumulierte Tabellen für schnelle Tailsummen sowie die
Wahrscheinlichkeit, gegen einen Gegner nicht zu verlieren, mit und ohne
Tie-Break über die Wurfzahl.
"""

from bisect import bisect_right

from schocken.probability.enumeration import opponent_distribution
from schocken.strategies.base import BaseStrategy


def cumulative_table(
    distribution: dict[tuple[int, ...], float],
) -> tuple[list[tuple[int, ...]], list[float]]:
    """
    Wandelt eine Rangverteilung in eine kumulierte Tabelle für Tailsummen um.

    Die Ränge werden aufsteigend sortiert (bessere Ränge zuerst). Die
    Präfixsummen enthalten an Position i die aufsummierte Wahrscheinlichkeit
    aller Ränge vor Position i.

    Args:
        distribution: Dictionary von Rang auf Wahrscheinlichkeit.

    Returns:
        Tuple aus sortierter Rangliste und zugehörigen Präfixsummen.
    """
    ranks = sorted(distribution)

    prefix = [0.0]
    for rank in ranks:
        prefix.append(prefix[-1] + distribution[rank])

    return ranks, prefix


def survival_probability(
    table: tuple[list[tuple[int, ...]], list[float]],
    rank: tuple[int, ...],
) -> float:
    """
    Berechnet die Wahrscheinlichkeit, dass ein Gegner schlechter abschneidet.

    Entspricht P(Rang_Gegner > rank), also der Tailsumme oberhalb des
    übergebenen Rangs. Gleichstand zählt nicht als Erfolg, da der Tie-Break
    über die Wurfzahl separat zu behandeln ist.

    Args:
        table: Kumulierte Tabelle aus cumulative_table().
        rank: Eigener Rang, gegen den verglichen wird.

    Returns:
        Wahrscheinlichkeit zwischen 0 und 1.
    """
    ranks, prefix = table
    index = bisect_right(ranks, rank)
    return prefix[-1] - prefix[index]


def survival_probability_with_ties(
    distribution: dict[tuple[tuple[int, ...], int], float],
    rank: tuple[int, ...],
    rolls_used: int,
    acts_first: bool,
) -> float:
    """
    Berechnet die Wahrscheinlichkeit, gegen einen Gegner nicht zu verlieren.

    Berücksichtigt beide Tie-Break-Stufen: Bei gleichem Rang gewinnt die
    geringere Wurfzahl, bei gleicher Wurfzahl die frühere Position.

    Args:
        distribution: Gemeinsame Verteilung aus joint_distribution().
        rank: Eigener Rang.
        rolls_used: Eigene verbrauchte Wurfzahl.
        acts_first: Ob man vor dem betrachteten Gegner an der Reihe war.

    Returns:
        Wahrscheinlichkeit zwischen 0 und 1.
    """
    total = 0.0

    for (opponent_rank, opponent_rolls), p in distribution.items():
        if opponent_rank > rank:
            total += p
        elif opponent_rank == rank:
            if opponent_rolls > rolls_used:
                total += p
            elif opponent_rolls == rolls_used and acts_first:
                total += p

    return total


def opponent_tables(
    strategy: BaseStrategy,
    max_rolls: int = 3,
    n_dice: int = 3,
) -> dict[int, tuple[list[tuple[int, ...]], list[float]]]:
    """
    Tabelliert die kumulierten Rangverteilungen für alle Wurfzahlen.

    Wird einmal vorberechnet und anschließend für Lookups verwendet, da die
    Verteilungen weder vom Tischzustand noch vom eigenen Würfelbild abhängen.

    Args:
        strategy: Referenzstrategie der Gegner.
        max_rolls: Höchste zu tabellierende Wurfzahl.
        n_dice: Anzahl der Würfel zu Beginn.

    Returns:
        Dictionary von Wurfzahl auf kumulierte Tabelle.
    """
    return {
        m: cumulative_table(opponent_distribution(m, strategy, n_dice))
        for m in range(1, max_rolls + 1)
    }
