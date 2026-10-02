"""
Einstiegspunkt für die Schocken-Simulation.

Konfiguration der Spieler und Strategien sowie Start der Simulation.
"""

from schocken.engine.game import Player
from schocken.engine.simulation import simulate_games
from schocken.probability.enumeration import joint_distribution
from schocken.strategies.absolute import StaticThresholdStrategy, GreedyAllIn
from schocken.strategies.optimizer.strategy import OptimalStrategy
from schocken.core.typedefs import GameState
from schocken.core.state import initial_state
from schocken.analysis.statistics import print_summary

reference = GreedyAllIn()
tables = {
    m: joint_distribution(
        initial_state(n_rolls=m),
        reference,
    )
    for m in (1, 2, 3)
}

players = [
    Player("Threshold 665 ", StaticThresholdStrategy(threshold=(6, 6, 5))),
    Player("Threshold S2  ", StaticThresholdStrategy(threshold=(1, 1, 2))),
    Player("Threshold S4  ", StaticThresholdStrategy(threshold=(1, 1, 4))),
    Player("Greedy All-In ", GreedyAllIn()),
    Player(
        "Loss Optimizer",
        OptimalStrategy(follower_distributions=tables, objective="not_lose"),
    ),
    Player(
        "Lid Optimizer ",
        OptimalStrategy(follower_distributions=tables, objective="expected_lids"),
    ),
]

results = simulate_games(players=players, n_games=100)
print(results)
print_summary(results)
