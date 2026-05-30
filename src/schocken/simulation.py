"""
Simulation und Auswertung von Schocken-Spielen.

Enthält Funktionen zur Simulation mehrerer Spiele und zur Ausgabe von Rundendetails.
"""

from collections import Counter
from tqdm import tqdm

from schocken.game import Game, Player


def print_round_summary(game: Game, round_result: dict) -> None:
    """
    Gibt eine Zusammenfassung einer Runde auf der Konsole aus.

    Args:
        game: Aktuelles Spielobjekt.
        round_result: Ergebnis der Runde.
    """
    print("\nRound Summary")

    for r in round_result["results"]:
        print(
            r["player"],
            r["final"],
            r["rank"],
            f"({r['rolls_used']} rolls)",
            r["visible_state"],
        )
        for step in r["history"]:
            print(
                f"  Roll {step['roll_number']}: "
                f"{step['roll']} "
                f"-> visible: {step['visible_state']}"
            )

    print(
        "\nWinner:", round_result["winner"]["player"], round_result["winner"]["final"]
    )
    print("Loser:", round_result["loser"]["player"], round_result["loser"]["final"])
    print("Round max rolls:", max(r["rolls_used"] for r in round_result["results"]))
    print("\nPot:", game.pot)

    for player in game.active_players():
        print(f"{player.name}: {player.lids} lids")
    print("---------------------------------------")


def simulate_games(players: list[Player], n_games: int = 10) -> dict:
    """
    Simuliert mehrere Spiele und gibt Auswertungsstatistiken zurück.

    Args:
        players: Liste der Spieler mit ihren Strategien.
        n_games: Anzahl der zu simulierenden Spiele.

    Returns:
        Dictionary mit Verliereranteilen und durchschnittlicher Rundenanzahl.
    """
    loser_counts: Counter = Counter()
    rounds_per_game = []

    for _ in tqdm(range(n_games)):
        fresh_players = [Player(p.name, p.strategy) for p in players]
        game = Game(fresh_players)
        rounds = 0

        while not game.is_game_over():
            if n_games <= 5:
                round_result = game.play_round()
                print_round_summary(game, round_result)
            else:
                game.play_round()
            rounds += 1

        loser = next(player for player in game.players if player.lids > 0)
        loser_counts[loser.name] += 1
        rounds_per_game.append(rounds)

    return {
        "n_games": n_games,
        "loser_shares": {
            key: round(loser_counts[key] / n_games, 4) for key in sorted(loser_counts)
        },
        "avg_rounds": sum(rounds_per_game) / len(rounds_per_game),
    }
