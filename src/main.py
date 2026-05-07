from collections.abc import Sequence
from random import randint


def roll_dice(dices_used=3) -> tuple:
    dices = [randint(1, 6) for _ in range(dices_used)]
    return normalize(dices)


def normalize(dice: Sequence) -> tuple:
    return tuple(sorted(dice, reverse=True))


def is_shock(dice) -> bool:
    _, b, c = dice
    return b == c == 1


def is_general(dice) -> bool:
    a, b, c = dice
    return a == b == c and a != 1


def is_straight(dice) -> bool:
    a, b, c = dice
    return a == b + 1 == c + 2


def classify(dice) -> tuple:
    if len(dice) != 3:
        raise ValueError(f"Expected 3 dice, got {dice}")
    a, b, c = dice
    if is_shock(dice):
        if a == 1:
            return (0, 0)
        else:
            return (0, 7 - a)
    elif is_general(dice):
        return (1, 6 - a)
    elif is_straight(dice):
        return (2, 6 - a)
    else:
        return (3, (-a, -b, -c))


def next_states(state: dict, roll: tuple) -> list:
    rolls_used = state["rolls_used"] + 1
    rolls_left = state["rolls_left"] - 1

    ones = roll.count(1)
    sixes = roll.count(6)

    possible_conversions = [0]
    if sixes >= 2:
        possible_conversions.append(1)
    if sixes == 3:
        possible_conversions.append(2)

    new_states = []
    for k in possible_conversions:
        if k > 0 and rolls_left < 1:  # optional: '<2' if strikter rule applies
            continue

        total_ones = ones + k

        max_keep = total_ones if rolls_left > 0 else 0

        for keep in range(0, max_keep + 1):
            new_states.append(
                {
                    "held_ones": state["held_ones"] + keep,
                    "rolls_left": rolls_left,
                    "rolls_used": rolls_used,
                    "must_continue": rolls_left > 1
                    and (state["must_continue"] or (k > 0)),
                    "dice_to_roll": state["dice_to_roll"] - keep,
                }
            )

    return new_states


def decide_after_roll(state, roll, strategy):
    options = []

    if state["rolls_left"] == 1:
        final = normalize((1,) * state["held_ones"] + roll)
        return {
            "action": "stop",
            "final": final,
            "rank": classify(final),
            "state": {
                **state,
                "rolls_used": state["rolls_used"] + 1,
                "rolls_left": state["rolls_left"] - 1,
            },
        }

    # Stop-Option
    if not state["must_continue"]:
        final = normalize((1,) * state["held_ones"] + roll)
        options.append(
            {
                "action": "stop",
                "final": final,
                "rank": classify(final),
                "state": {
                    **state,
                    "rolls_used": state["rolls_used"] + 1,
                    "rolls_left": state["rolls_left"] - 1,
                },
            }
        )

    # Continue-Optionen
    for next_state in next_states(state, roll):
        options.append({"action": "continue", "state": next_state})

    return strategy.choose(options, state, roll)


class GreedyAllIn:
    def choose(self, options, state, roll):
        # Stop-Option prüfen
        stop_option = next((o for o in options if o["action"] == "stop"), None)

        if stop_option is not None and stop_option["rank"] == (0, 0):
            return stop_option

        # sonst weiter: max Einsen
        continues = [o for o in options if o["action"] == "continue"]
        return max(continues, key=lambda o: o["state"]["held_ones"])


class ThresholdStrategy:
    def __init__(self, threshold):
        self.threshold = threshold

    def choose(self, options, state, roll):
        for o in options:
            if o["action"] == "stop" and o["rank"] <= self.threshold:
                return o

        # sonst weiter wie greedy
        continues = [o for o in options if o["action"] == "continue"]
        if not continues:
            return [o for o in options if o["action"] == "stop"][0]
        return max(continues, key=lambda o: o["state"]["held_ones"])


def play_turn(strategy):
    state = {
        "held_ones": 0,
        "rolls_left": 3,
        "rolls_used": 0,
        "must_continue": False,
        "dice_to_roll": 3,
    }

    history = []

    while state["rolls_left"] > 0:
        roll = roll_dice(state["dice_to_roll"])

        decision = decide_after_roll(state, roll, strategy)

        history.append(
            {
                "state_before": state.copy(),
                "roll": roll,
                "decision": decision["action"],
                "state_after": decision.get("state"),
                "final": decision.get("final"),
                "rank": decision.get("rank"),
            }
        )

        state = decision["state"]
        if decision["action"] == "stop":
            return {
                "final": decision["final"],
                "rank": decision["rank"],
                "rolls_used": state["rolls_used"],
                "history": history,
            }


def compare_results(a, b):
    if a["rank"] < b["rank"]:
        return a

    if b["rank"] < a["rank"]:
        return b

    # Tie-Break: weniger Würfe
    if a["rolls_used"] < b["rolls_used"]:
        return a

    if b["rolls_used"] < a["rolls_used"]:
        return b

    # Tie-Break: frühere Position
    if a["turn_order"] < b["turn_order"]:
        return a

    if b["turn_order"] < a["turn_order"]:
        return b

    raise RuntimeError("Impossible tie")


class Player:
    def __init__(self, name, strategy):
        self.name = name
        self.strategy = strategy


class Game:
    def __init__(self, players: list):
        self.players = players
        self.starting_player = 0

    def play_round(self) -> list:
        ordered_players = (
            self.players[self.starting_player :] + self.players[: self.starting_player]
        )

        results = []

        for i, player in enumerate(ordered_players):
            result = play_turn(player.strategy)

            result["player"] = player.name
            result["player_index"] = self.players.index(player)
            result["turn_order"] = i

            results.append(result)

        return results

    def determine_loser(self, results: list):
        loser = results[0]

        for result in results[1:]:
            winner = compare_results(result, loser)

            if winner is loser:
                loser = result

        return loser

    def determine_winner(self, results: list):
        winner = results[0]

        for result in results[1:]:
            winner = compare_results(result, winner)

        return winner


players = [
    Player("A", GreedyAllIn()),
    Player("B", ThresholdStrategy((1, 4))),
    Player("C", ThresholdStrategy((2, 2))),
]

game = Game(players)

results = game.play_round()

for r in results:
    print(r["player"], r["final"], r["rank"], r["rolls_used"], r["turn_order"])

loser = game.determine_loser(results)
winner = game.determine_winner(results)
print(f"verlierer ist: {loser["player"]} \ngewinner ist: {winner["player"]}")
