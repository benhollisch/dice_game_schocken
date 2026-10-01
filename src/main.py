"""
Einstiegspunkt für die Schocken-Simulation.

Konfiguration der Spieler und Strategien sowie Start der Simulation.
"""

from schocken.game import Player
from schocken.simulation import simulate_games
from schocken.distribution import joint_distribution
from schocken.strategies.absolute import StaticThresholdStrategy, GreedyAllIn
from schocken.strategies.optimal import OptimalStrategy
from schocken.typedefs import GameState
from analysis import print_summary

reference = GreedyAllIn()
tables = {
    m: joint_distribution(
        GameState(
            held_ones=0,
            rolls_left=m,
            rolls_used=0,
            visible_state=None,
            dice_to_roll=3,
        ),
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
