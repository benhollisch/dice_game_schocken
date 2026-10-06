"""
Einstiegspunkt für die Schocken-Simulation.

Konfiguration der Spieler und Strategien sowie Start der Simulation.
"""

from schocken.engine.game import Player
from schocken.engine.simulation import simulate_games
from schocken.strategies.absolute import StaticThresholdStrategy, GreedyAllIn
from schocken.strategies.optimizer.strategy import OptimalStrategy
from schocken.analysis.statistics import print_summary

players = [
    # Player("Greedy All-In  ", GreedyAllIn()),
    # Player("Greedy All-In B", GreedyAllIn()),
    # Player("Greedy All-In C", GreedyAllIn()),
    Player("Loss Optimizer ", OptimalStrategy(objective="not_lose")),
    Player("Lid Optimizer  ", OptimalStrategy(objective="expected_lids")),
    Player("Lid Optimizer 2", OptimalStrategy(objective="expected_lids")),
]

results = simulate_games(players=players, n_games=10_000)
# print(results)
print_summary(results)
# print_summary(results, reference="Loss Optimizer ")
