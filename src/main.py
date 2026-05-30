"""
Einstiegspunkt für die Schocken-Simulation.

Konfiguration der Spieler und Strategien sowie Start der Simulation.
"""

from schocken.game import Player
from schocken.simulation import simulate_games
from schocken.strategies.absolute import StaticThresholdStrategy

players = [
    Player("C1", StaticThresholdStrategy(threshold=(2, 3))),
    Player("C2", StaticThresholdStrategy(threshold=(2, 3))),
]

results = simulate_games(players=players, n_games=1000000)
print(results)
