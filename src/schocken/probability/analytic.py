"""
Analytische Verteilungen der Einsenanzahl.

Geschlossene Berechnungen auf Basis der Multinomialverteilung, die als
Kontrollrechnung zur Validierung der Enumeration dienen.
"""

from collections import defaultdict
from math import comb, factorial


def increment_distribution(n_dice: int) -> dict[int, float]:
    """
    Berechnet die Verteilung des Einsen-Zuwachses in einem einzelnen Wurf.

    Berücksichtigt die Konversion von Sechsen: zwei Sechsen ergeben eine
    zusätzliche Eins, drei Sechsen ergeben zwei. Basiert auf der gemeinsamen
    Multinomialverteilung von Einsen und Sechsen.

    Args:
        n_dice: Anzahl der geworfenen Würfel.

    Returns:
        Dictionary von Zuwachs auf Wahrscheinlichkeit.
    """
    conversion = {0: 0, 1: 0, 2: 1, 3: 2}
    distribution: dict[int, float] = defaultdict(float)

    for ones in range(n_dice + 1):
        for sixes in range(n_dice - ones + 1):
            rest = n_dice - ones - sixes
            weight = (
                factorial(n_dice)
                / (factorial(ones) * factorial(sixes) * factorial(rest))
                * (1 / 6) ** ones
                * (1 / 6) ** sixes
                * (4 / 6) ** rest
            )
            distribution[ones + conversion.get(sixes, 0)] += weight

    return dict(distribution)


def ones_distribution(
    n_dice: int, n_rolls: int, with_conversion: bool = True
) -> dict[int, float]:
    """
    Berechnet die Verteilung der Einsenanzahl nach n_rolls Würfen.

    Analytische Kontrollrechnung zur Validierung der Enumeration. Unterstellt,
    dass in jedem Wurf alle Einsen herausgelegt und die verbleibenden Würfel
    erneut geworfen werden.

    Args:
        n_dice: Anzahl der Würfel zu Beginn.
        n_rolls: Anzahl der Würfe.
        with_conversion: Ob die Sechsen-Konversion berücksichtigt wird.

    Returns:
        Dictionary von Einsenanzahl auf Wahrscheinlichkeit.
    """
    distribution: dict[int, float] = {0: 1.0}

    for _ in range(n_rolls):
        updated: dict[int, float] = defaultdict(float)

        for held, p_held in distribution.items():
            remaining = n_dice - held

            if remaining == 0:
                updated[held] += p_held
                continue

            if with_conversion:
                increments = increment_distribution(remaining)
            else:
                increments = {
                    k: comb(remaining, k) * (1 / 6) ** k * (5 / 6) ** (remaining - k)
                    for k in range(remaining + 1)
                }

            for increment, p_increment in increments.items():
                updated[min(held + increment, n_dice)] += p_held * p_increment

        distribution = dict(updated)

    return distribution
