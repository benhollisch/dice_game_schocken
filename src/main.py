from collections.abc import Sequence
from random import randint
from collections import Counter
from tqdm import tqdm


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
        # Conversion only feasible if player may continue
        if k > 0 and rolls_left < 1:  # optional: '<2' if strikter rule applies
            continue

        total_ones = ones + k

        max_keep = total_ones if rolls_left > 0 else 0

        for keep in range(0, max_keep + 1):
            held_ones = state["held_ones"] + keep

            if held_ones > 0:
                visible_state = (1,) * held_ones
            else:
                visible_state = None

            new_states.append(
                {
                    "held_ones": held_ones,
                    "rolls_left": rolls_left,
                    "rolls_used": rolls_used,
                    "visible_state": visible_state,
                    "must_continue": (
                        rolls_left > 1 and (state["must_continue"] or (k > 0))
                    ),
                    "dice_to_roll": state["dice_to_roll"] - keep,
                }
            )

    return new_states


def decide_after_roll(state, roll, strategy, public_table_state=None):
    options = []

    final = normalize((1,) * state["held_ones"] + roll)

    if state["rolls_left"] == 1:
        return {
            "action": "stop",
            "final": final,
            "rank": classify(final),
            "state": {
                **state,
                "rolls_used": state["rolls_used"] + 1,
                "rolls_left": state["rolls_left"] - 1,
                "visible_state": state["visible_state"],
            },
        }

    # Stop-Option
    if not state["must_continue"]:

        options.append(
            {
                "action": "stop",
                "final": final,
                "rank": classify(final),
                "state": {
                    **state,
                    "rolls_used": state["rolls_used"] + 1,
                    "rolls_left": state["rolls_left"] - 1,
                    "visible_state": final,
                },
            }
        )

    # Continue-Optionen
    for next_state in next_states(state, roll):
        options.append({"action": "continue", "state": next_state})

    return strategy.choose(options, state, roll, public_table_state)


def danger_score(visible_state):
    if visible_state is None:
        return 0.5

    if len(visible_state) == 1:
        return 0.8

    if len(visible_state) == 2:
        return 0.95

    return 0.2


def total_danger(public_table_state):
    safe_probability = 1.0
    for p in public_table_state:
        d = danger_score(p["visible_state"])
        safe_probability *= 1 - d

    return 1 - safe_probability


# absolute strategies
class GreedyAllIn:
    def choose(self, options, state, roll, public_table_state=None):
        # Stop-Option prüfen
        stop_option = next((o for o in options if o["action"] == "stop"), None)

        if stop_option is not None and stop_option["rank"] == (0, 0):
            return stop_option

        # sonst weiter: max Einsen
        continues = [o for o in options if o["action"] == "continue"]
        return max(continues, key=lambda o: o["state"]["held_ones"])


class StaticThresholdStrategy:
    def __init__(self, threshold):
        self.threshold = threshold

    def choose(self, options, state, roll):
        # Stop-Option prüfen
        stop_option = next((o for o in options if o["action"] == "stop"), None)

        if stop_option is not None and stop_option["rank"] <= self.threshold:
            return stop_option

        # sonst weiter wie greedy
        continues = [o for o in options if o["action"] == "continue"]
        if not continues:
            return stop_option

        return max(continues, key=lambda o: o["state"]["held_ones"])


# relative strategies
class PublicThresholdStrategy:
    def choose(self, options, state, roll, public_table_state=None):
        stop_option = next((o for o in options if o["action"] == "stop"), None)
        worst_public = worst_public_rank(public_table_state)
        if stop_option is not None:
            if worst_public is not None and stop_option["rank"] < worst_public:
                return stop_option

        # sonst weiter wie greedy
        continues = [o for o in options if o["action"] == "continue"]
        if not continues:
            return stop_option

        return max(continues, key=lambda o: o["state"]["held_ones"])


class AdaptiveGreedyStrategy:
    def choose(self, options, state, roll, public_table_state=None):
        # Stop-Option prüfen
        stop_option = next((o for o in options if o["action"] == "stop"), None)
        worst_public = worst_public_rank(public_table_state)

        # no public information availabe -> play aggressive
        if worst_public is None:
            if stop_option is not None and stop_option["rank"] == (0, 0):
                return stop_option

            continues = [o for o in options if o["action"] == "continue"]
            if not continues:
                return stop_option

            return max(continues, key=lambda o: o["state"]["held_ones"])

        # public information available -> only avoid sure defeat
        if stop_option is not None and stop_option["rank"] < worst_public:
            return stop_option

        continues = [o for o in options if o["action"] == "continue"]
        if not continues:
            return stop_option

        return max(continues, key=lambda o: o["state"]["held_ones"])


class HybridThresholdStrategy:
    def __init__(self, threshold):
        self.threshold = threshold

    def choose(self, options, state, roll, public_table_state=None):
        # Stop-Option prüfen
        stop_option = next((o for o in options if o["action"] == "stop"), None)
        worst_public = worst_public_rank(public_table_state)
        if worst_public is None:
            if stop_option is not None and stop_option["rank"] <= self.threshold:
                return stop_option

        # Öffentliche Zielmarke vorhanden:
        # -> nur nicht verlieren
        else:
            if stop_option is not None and stop_option["rank"] < worst_public:
                return stop_option

        # sonst weiter wie greedy
        continues = [o for o in options if o["action"] == "continue"]
        if not continues:
            return stop_option

        return max(continues, key=lambda o: o["state"]["held_ones"])


class DangerAwareStrategy:

    def __init__(self, threshold, risk_aversion=0.5):
        self.threshold = threshold
        self.risk_aversion = risk_aversion

    def choose(self, options, state, roll, public_table_state):
        stop_option = next((o for o in options if o["action"] == "stop"), None)
        continues = [o for o in options if o["action"] == "continue"]

        if stop_option is None:
            return max(continues, key=lambda o: o["state"]["held_ones"])

        my_rank = stop_option["rank"]

        # Basis-Threshold
        if my_rank > self.threshold:
            return max(continues, key=lambda o: o["state"]["held_ones"])

        # Gefahrenniveau abschätzen
        # Hohe Gefahr -> aggressiver bleiben
        if total_danger(public_table_state) > self.risk_aversion:
            return max(continues, key=lambda o: o["state"]["held_ones"])

        # sonst stoppen
        return stop_option


def play_turn(strategy, max_rolls=3, public_table_state=None):
    state = {
        "held_ones": 0,
        "rolls_left": max_rolls,
        "rolls_used": 0,
        "visible_state": None,
        "must_continue": False,
        "dice_to_roll": 3,
    }

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
                "final": decision["final"],
                "rank": decision["rank"],
                "rolls_used": decision["state"]["rolls_used"],
                "visible_state": decision["state"]["visible_state"],
                "history": history,
            }


def worst_public_rank(public_table_state):
    public_ranks = [
        classify(p["visible_state"])
        for p in public_table_state
        if p["visible_state"] is not None and len(p["visible_state"]) == 3
    ]

    if not public_ranks:
        return None

    return max(public_ranks)


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


def lid_value(roll):
    a, b, c = normalize(roll)

    if roll == (1, 1, 1):
        return "shock_out"

    if is_shock(roll):
        return a

    if is_general(roll):
        return 3

    if is_straight(roll):
        return 2

    return 1


class Player:
    def __init__(self, name, strategy):
        self.name = name
        self.strategy = strategy
        self.lids = 0


class Game:
    def __init__(self, players: list):
        self.players = players
        self.starting_player = 0
        self.pot = 13

    def active_players(self):
        # Topf noch nicht leer -> alle spielen
        if self.pot > 0:
            return self.players

        return [player for player in self.players if player.lids > 0]

    def play_round(self) -> dict:
        players = self.active_players()
        starter = self.players[self.starting_player]

        start_index = players.index(starter)
        ordered_players = players[start_index:] + players[:start_index]

        round_max_rolls = None
        results = []
        public_table_state = []

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
                {
                    "player": player.name,
                    "turn_order": i,
                    "visible_state": result["visible_state"],
                    "is_closed": result["rolls_used"] == round_max_rolls,
                }
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

    def resolve_round(self, winner_result, loser_result):
        winner = self.players[winner_result["player_index"]]
        loser = self.players[loser_result["player_index"]]

        value = lid_value(winner_result["final"])

        # Schock Out
        if value == "shock_out":
            total = self.pot

            for player in self.players:
                total += player.lids
                player.lids = 0

            self.pot = 0
            loser.lids += total

            return

        # Pot zuerst
        if self.pot > 0:
            transfer = min(self.pot, value)

            self.pot -= transfer
            loser.lids += transfer

            return

        # Spieler zu Spieler
        transfer = min(winner.lids, value)

        winner.lids -= transfer
        loser.lids += transfer

    def is_game_over(self):
        if self.pot > 0:
            return False

        active = [p for p in self.players if p.lids > 0]

        return len(active) <= 1


def print_round_summary(game, round_result):
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
        "\nWinner:",
        round_result["winner"]["player"],
        round_result["winner"]["final"],
    )

    print(
        "Loser:",
        round_result["loser"]["player"],
        round_result["loser"]["final"],
    )
    print("Round max rolls:", max(r["rolls_used"] for r in round_result["results"]))
    print("\nPot:", game.pot)

    for player in game.active_players():
        print(f"{player.name}: {player.lids} lids")
    print("---------------------------------------")


def simulate_games(players, n_games=10):
    loser_counts = Counter()
    rounds_per_game = []

    for _ in tqdm(range(n_games)):
        # for _ in range(n_games):
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
        # "loser_counts": {key: loser_counts[key] for key in sorted(loser_counts)},
        "loser_shares": {
            key: round(loser_counts[key] / n_games, 4) for key in sorted(loser_counts)
        },
        "avg_rounds": sum(rounds_per_game) / len(rounds_per_game),
    }


players = [
    # Player("A", GreedyAllIn()),
    # Player("B", PublicThresholdStrategy()),
    Player("C1", StaticThresholdStrategy(threshold=(2, 3))),
    Player("C2", StaticThresholdStrategy(threshold=(2, 3))),
    # Player("D", AdaptiveGreedyStrategy()),
]

results = simulate_games(players=players, n_games=1000000)
print(results)
