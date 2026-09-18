"""Prüfskript für die Gegnerverteilungen in distribution.py."""

from schocken.distribution import (
    opponent_distribution,
    opponent_tables,
    survival_probability,
)
from schocken.strategies.absolute import GreedyAllIn

strategy = GreedyAllIn()
tables = opponent_tables(strategy)

print("Verteilungen pro Wurfzahl")
print("-" * 60)
for m in (1, 2, 3):
    dist = opponent_distribution(m, strategy)
    print(f"m={m}  Ränge: {len(dist):3d}  Summe: {sum(dist.values()):.10f}")

print("\nBeste und schlechteste Ränge (m=3)")
print("-" * 60)
dist = opponent_distribution(3, strategy)
for rank in sorted(dist):
    print(f"  {str(rank):<22} {dist[rank]:.6f}")
# print("  ...")
# for rank in sorted(dist)[-3:]:
# print(f"  {str(rank):<22} {dist[rank]:.6f}")

print("\nsurvival_probability für ausgewählte Ränge")
print("-" * 60)
probes = [
    ((0, 0), "Schock-Out (1,1,1)"),
    ((0, 1), "Schock (6,1,1)"),
    ((0, 4), "Schock (3,1,1)"),
    ((1, 0), "General (6,6,6)"),
    ((2, 0), "Straße (6,5,4)"),
    ((3, -6, -5, -3), "Hausnummer (6,5,3)"),
    ((3, -3, -2, -2), "Hausnummer (3,2,2)"),
]

header = f"{'Rang':<22}{'m=1':>10}{'m=2':>10}{'m=3':>10}"
print(header)
for rank, label in probes:
    values = "".join(
        f"{survival_probability(tables[m], rank):>10.4f}" for m in (1, 2, 3)
    )
    print(f"{label:<22}{values}")

print("\nMonotonie-Check: P sollte mit m fallen")
print("-" * 60)
violations = 0
for rank in sorted(dist):
    values = [survival_probability(tables[m], rank) for m in (1, 2, 3)]
    if not (values[0] >= values[1] >= values[2] - 1e-12):
        violations += 1
        print(f"  Verletzung bei {rank}: {values}")
print(f"Verletzungen: {violations}")
