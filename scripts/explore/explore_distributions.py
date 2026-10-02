from schocken.core.classification import classify
from schocken.core.state import initial_state
from schocken.probability.enumeration import joint_distribution, opponent_distribution
from schocken.probability.survival import (
    cumulative_table,
    survival_probability,
    survival_probability_with_ties,
)
from schocken.strategies.absolute import StaticThresholdStrategy

STRATEGY = StaticThresholdStrategy(threshold=classify((6, 5, 5)))
# STRATEGY = GreedyAllIn()


def show_roll_counts(m: int = 3) -> None:
    """Gibt aus, wie sich die Wahrscheinlichkeit auf Wurfzahlen verteilt."""
    print(f"\nVerteilung der Wurfzahlen (m={m})")
    print("-" * 68)

    joint = joint_distribution(initial_state(n_rolls=m), STRATEGY)
    by_rolls: dict[int, float] = {}
    for (_, rolls), p in joint.items():
        by_rolls[rolls] = by_rolls.get(rolls, 0.0) + p

    for rolls in sorted(by_rolls):
        print(f"  {rolls} Würfe: {by_rolls[rolls]:.6f}")


def show_tie_break_effect(m: int = 3, own_rolls: int = 1) -> None:
    """Zeigt die Ränge, an denen der Tie-Break am stärksten wirkt."""
    print(
        f"\nGrößter Tie-Break-Effekt (m={m}, eigene Wurfzahl {own_rolls}, früher dran)"
    )
    print("-" * 68)

    joint = joint_distribution(initial_state(n_rolls=m), STRATEGY)
    table = cumulative_table(opponent_distribution(m, STRATEGY))

    deltas = []
    for rank in {r for r, _ in joint}:
        without = survival_probability(table, rank)
        with_ties = survival_probability_with_ties(joint, rank, own_rolls, True)
        deltas.append((with_ties - without, rank))

    for delta, rank in sorted(deltas, reverse=True)[:8]:
        print(f"  {str(rank):<22} +{delta:.6f}")
