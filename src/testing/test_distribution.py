"""Prüfskript für joint_distribution und survival_probability_with_ties."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schocken.distribution import (  # noqa: E402
    cumulative_table,
    joint_distribution,
    opponent_distribution,
    survival_probability,
    survival_probability_with_ties,
)
from schocken.strategies.absolute import (
    GreedyAllIn,
    StaticThresholdStrategy,
)  # noqa: E402
from schocken.types import GameState  # noqa: E402
from schocken.classification import classify

STRATEGY = StaticThresholdStrategy(threshold=classify((6, 5, 5)))
# STRATEGY = GreedyAllIn()

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


def start_state(n_rolls: int, n_dice: int = 3) -> GameState:
    """Erzeugt den Ausgangszustand eines Spielers vor dem ersten Wurf."""
    return GameState(
        held_ones=0,
        rolls_left=n_rolls,
        rolls_used=0,
        visible_state=None,
        must_continue=False,
        dice_to_roll=n_dice,
    )


def check_consistency() -> None:
    """Prüft, ob die Randverteilung mit rank_distribution übereinstimmt."""
    print("Konsistenz mit rank_distribution")
    print("-" * 68)

    for m in (1, 2, 3):
        joint = joint_distribution(start_state(m), STRATEGY)

        marginal: dict[tuple[int, ...], float] = {}
        for (rank, _), p in joint.items():
            marginal[rank] = marginal.get(rank, 0.0) + p

        reference = opponent_distribution(m, STRATEGY)
        matches = all(
            abs(marginal.get(r, 0.0) - p) < 1e-12 for r, p in reference.items()
        )
        print(
            f"m={m}  Einträge: {len(joint):3d}  Summe: {sum(joint.values()):.10f}  "
            f"Randverteilung stimmt: {matches}"
        )


def show_roll_counts(m: int = 3) -> None:
    """Gibt aus, wie sich die Wahrscheinlichkeit auf Wurfzahlen verteilt."""
    print(f"\nVerteilung der Wurfzahlen (m={m})")
    print("-" * 68)

    joint = joint_distribution(start_state(m), STRATEGY)
    by_rolls: dict[int, float] = {}
    for (_, rolls), p in joint.items():
        by_rolls[rolls] = by_rolls.get(rolls, 0.0) + p

    for rolls in sorted(by_rolls):
        print(f"  {rolls} Würfe: {by_rolls[rolls]:.6f}")


def compare_survival(m: int = 3) -> None:
    """Stellt beide Überlebensfunktionen für ausgewählte Ränge gegenüber."""
    print(f"\nVergleich der Überlebensfunktionen (m={m})")
    print("-" * 68)

    joint = joint_distribution(start_state(m), STRATEGY)
    table = cumulative_table(opponent_distribution(m, STRATEGY))

    header = (
        f"{'Rang':<22}{'ohne Ties':>11}{'r=1 first':>11}"
        f"{'r=3 first':>11}{'r=3 last':>11}"
    )
    print(header)

    for rank, label in PROBES:
        without = survival_probability(table, rank)
        r1_first = survival_probability_with_ties(joint, rank, 1, True)
        r3_first = survival_probability_with_ties(joint, rank, 3, True)
        r3_last = survival_probability_with_ties(joint, rank, 3, False)
        print(
            f"{label:<22}{without:>11.4f}{r1_first:>11.4f}"
            f"{r3_first:>11.4f}{r3_last:>11.4f}"
        )


def check_invariants(m: int = 3) -> None:
    """
    Prüft zwei Invarianten der neuen Überlebensfunktion.

    Die Berücksichtigung von Gleichständen darf den Wert nie senken, und eine
    frühere Position darf nie schaden.
    """
    print("\nInvarianten")
    print("-" * 68)

    joint = joint_distribution(start_state(m), STRATEGY)
    table = cumulative_table(opponent_distribution(m, STRATEGY))

    violations = 0
    for rank in {r for r, _ in joint}:
        without = survival_probability(table, rank)
        for rolls in (1, 2, 3):
            first = survival_probability_with_ties(joint, rank, rolls, True)
            last = survival_probability_with_ties(joint, rank, rolls, False)

            if last < without - 1e-12:
                violations += 1
                print(f"  ties < ohne Ties bei {rank}, r={rolls}: {last} < {without}")
            if first < last - 1e-12:
                violations += 1
                print(f"  first < last bei {rank}, r={rolls}: {first} < {last}")

    print(f"Verletzungen: {violations}")


def show_tie_break_effect(m: int = 3, own_rolls: int = 1) -> None:
    """Zeigt die Ränge, an denen der Tie-Break am stärksten wirkt."""
    print(
        f"\nGrößter Tie-Break-Effekt (m={m}, eigene Wurfzahl {own_rolls}, früher dran)"
    )
    print("-" * 68)

    joint = joint_distribution(start_state(m), STRATEGY)
    table = cumulative_table(opponent_distribution(m, STRATEGY))

    deltas = []
    for rank in {r for r, _ in joint}:
        without = survival_probability(table, rank)
        with_ties = survival_probability_with_ties(joint, rank, own_rolls, True)
        deltas.append((with_ties - without, rank))

    for delta, rank in sorted(deltas, reverse=True)[:8]:
        print(f"  {str(rank):<22} +{delta:.6f}")


if __name__ == "__main__":
    check_consistency()
    show_roll_counts()
    compare_survival()
    check_invariants()
    show_tie_break_effect()
