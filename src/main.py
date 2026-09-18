"""
Einstiegspunkt für die Schocken-Simulation.

Konfiguration der Spieler und Strategien sowie Start der Simulation.
"""

from schocken.game import Player
from schocken.simulation import simulate_games
from schocken.strategies.absolute import StaticThresholdStrategy
from analysis import print_summary

players = [
    Player("C1", StaticThresholdStrategy(threshold=(0, -6, -6, -5))),
    Player("C2", StaticThresholdStrategy(threshold=(2, 3))),
    Player("C3", StaticThresholdStrategy(threshold=(2, 3))),
]

results = simulate_games(players=players, n_games=100)
print(results)
print_summary(results)
