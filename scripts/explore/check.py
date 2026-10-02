from schocken.probability.enumeration import (
    roll_distribution,
    rank_distribution,
)
from schocken.probability.analytic import ones_distribution
from schocken.core.classification import classify
import schocken.core.state as state_module
from schocken.strategies.absolute import GreedyAllIn

d = roll_distribution(3)
print(len(d), sum(d.values()))


state = state_module.initial_state(n_rolls=1, n_dice=3)

dist = rank_distribution(state, GreedyAllIn())
print(sum(dist.values()))

expected = {}
for roll, p in roll_distribution(3).items():
    expected[classify(roll)] = expected.get(classify(roll), 0) + p

print(dist == expected)


state = state_module.initial_state(n_rolls=3, n_dice=3)

dist = rank_distribution(state, GreedyAllIn())
print(dist)
print(sum(dist.values()))
print(dist.get((0, 0)))


original_next_states = state_module.next_states


def next_states_without_conversion(state, roll):
    """next_states ohne Sechsen-Konversion: filtert alle Zustände mit k > 0."""
    ones = roll.count(1)
    max_held = state["held_ones"] + ones
    return [s for s in original_next_states(state, roll) if s["held_ones"] <= max_held]


state_module.next_states = next_states_without_conversion

start = state_module.initial_state(n_rolls=3, n_dice=3)

dist = rank_distribution(start, GreedyAllIn())

print("Summe:      ", sum(dist.values()))
print("P(1,1,1):   ", dist.get((0, 0)))
print("Erwartet:   ", (91 / 216) ** 3)

state_module.next_states = original_next_states

print("Verteilung der Einsen-Zuwächse in einem Wurf mit 3 Würfeln")
print("ohne Konversion:", ones_distribution(3, 3, with_conversion=False)[3])
print("Erwartet:       ", (91 / 216) ** 3)
print("mit Konversion: ", ones_distribution(3, 3)[3])
print("Erwartet:       ", 54271 / 629856)
