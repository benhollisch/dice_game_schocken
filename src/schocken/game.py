"""
Spiellogik für das Schocken-Spiel.

Enthält die Klassen Player und Game sowie die Funktionen play_turn und compare_results.
"""

from schocken.dice import roll_dice
from schocken.classification import lid_value, is_shock_out
from schocken.state import decide_after_roll
from schocken.types import GameState, PublicPlayerState, TurnResult
from schocken.strategies.base import BaseStrategy


def play_turn(
    strategy: BaseStrategy,
    max_rolls: int = 3,
    public_table_state: list[PublicPlayerState] | None = None,
) -> TurnResult:
    """
    Simuliert den Zug eines Spielers.

    Args:
        strategy: Strategie des Spielers.
        max_rolls: Maximale Anzahl an Würfen.
        public_table_state: Öffentlich sichtbare Zustände der anderen Spieler.

    Returns:
        Ergebnis des Zuges als TurnResult.
    """
    state = GameState(
        held_ones=0,
        rolls_left=max_rolls,
        rolls_used=0,
        visible_state=None,
        must_continue=False,
        dice_to_roll=3,
    )

    history = []

    while state["rolls_left"] > 0:
        roll = roll_dice(state["dice_to_roll"])
        decision = decide_after_roll(state, roll, strategy, public_table_state)

        history.append(
            {
                "state_before": state.copy(),
                "roll_number": state["rolls_used"] + 1,
                "roll": roll,
                "decision": decision["action"],
                "state_after": decision.get("state"),
                "final": decision.get("final"),
                "rank": decision.get("rank"),
                "visible_state": decision["state"]["visible_state"],
            }
        )

        state = decision["state"]
        if decision["action"] == "stop":
            return {
                "final": decision["final"],  # type: ignore
                "rank": decision["rank"],  # type: ignore
                "rolls_used": decision["state"]["rolls_used"],
                "visible_state": decision["state"]["visible_state"],
                "history": history,
            }

    raise RuntimeError("Unreachable: turn ended without stop decision.")


def compare_results(a: dict, b: dict) -> dict:
    """
    Vergleicht zwei Rundenergebnisse und gibt das bessere zurück.

    Tie-Breaks: weniger Würfe, dann frühere Position.

    Args:
        a: Erstes Rundenergebnis.
        b: Zweites Rundenergebnis.

    Returns:
        Das bessere Rundenergebnis.

    Raises:
        RuntimeError: Bei unauflösbarem Gleichstand.
    """
    if a["rank"] < b["rank"]:
        return a
    if b["rank"] < a["rank"]:
        return b
    if a["rolls_used"] < b["rolls_used"]:
        return a
    if b["rolls_used"] < a["rolls_used"]:
        return b
    if a["turn_order"] < b["turn_order"]:
        return a
    if b["turn_order"] < a["turn_order"]:
        return b
    raise RuntimeError("Impossible tie")


class Player:
    """Repräsentiert einen Spieler mit Name, Strategie und Deckelstand."""

    def __init__(self, name: str, strategy: BaseStrategy):
        self.name = name
        self.strategy = strategy
        self.lids: int = 0


class Game:
    """
    Repräsentiert ein Schocken-Spiel mit mehreren Spielern.

    Args:
        players: Liste der Spieler.
        starting_lids: Anzahl der Deckel im Starttopf.
    """

    def __init__(self, players: list[Player], starting_lids: int = 13):
        self.players = players
        self.starting_player = 0
        self.pot = starting_lids

    def active_players(self) -> list[Player]:
        """Gibt die aktiven Spieler zurück."""
        if self.pot > 0:
            return self.players
        return [player for player in self.players if player.lids > 0]

    def play_round(self) -> dict:
        """Simuliert eine Runde und gibt das Ergebnis zurück."""
        players = self.active_players()
        starter = self.players[self.starting_player]

        start_index = players.index(starter)
        ordered_players = players[start_index:] + players[:start_index]

        round_max_rolls = None
        results = []
        public_table_state: list[PublicPlayerState] = []

        for i, player in enumerate(ordered_players):
            if round_max_rolls is None:
                result = play_turn(
                    player.strategy, 3, public_table_state=public_table_state
                )
                round_max_rolls = result["rolls_used"]
            else:
                result = play_turn(
                    player.strategy,
                    round_max_rolls,
                    public_table_state=public_table_state,
                )

            public_table_state.append(
                PublicPlayerState(
                    player=player.name,
                    turn_order=i,
                    visible_state=result["visible_state"],
                    is_closed=result["rolls_used"] == round_max_rolls,
                )
            )

            result["player"] = player.name
            result["player_index"] = self.players.index(player)
            result["turn_order"] = i

            results.append(result)

        winner = self.determine_winner(results)
        loser = self.determine_loser(results)
        self.resolve_round(winner, loser)
        self.starting_player = loser["player_index"]

        return {
            "results": results,
            "winner": winner,
            "loser": loser,
            "public_table_state": public_table_state,
        }

    def determine_winner(self, results: list[dict]) -> dict:
        """Bestimmt den Gewinner einer Runde."""
        winner = results[0]
        for result in results[1:]:
            winner = compare_results(result, winner)
        return winner

    def determine_loser(self, results: list[dict]) -> dict:
        """Bestimmt den Verlierer einer Runde."""
        loser = results[0]
        for result in results[1:]:
            winner = compare_results(result, loser)
            if winner is loser:
                loser = result
        return loser

    def resolve_round(self, winner_result: dict, loser_result: dict) -> None:
        """
        Verteilt Deckel nach einer Runde.

        Bei Schock-Out werden alle Deckel an den Verlierer übertragen.

        Args:
            winner_result: Ergebnis des Gewinners.
            loser_result: Ergebnis des Verlierers.
        """
        winner = self.players[winner_result["player_index"]]
        loser = self.players[loser_result["player_index"]]

        if is_shock_out(winner_result["final"]):
            total = self.pot
            for player in self.players:
                total += player.lids
                player.lids = 0
            self.pot = 0
            loser.lids += total
            return

        value = lid_value(winner_result["final"])

        if self.pot > 0:
            transfer = min(self.pot, value)
            self.pot -= transfer
            loser.lids += transfer
            return

        transfer = min(winner.lids, value)
        winner.lids -= transfer
        loser.lids += transfer

    def is_game_over(self) -> bool:
        """Prüft ob das Spiel beendet ist."""
        if self.pot > 0:
            return False
        active = [p for p in self.players if p.lids > 0]
        return len(active) <= 1
