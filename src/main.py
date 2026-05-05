from random import randint
from collections.abc import Sequence
from pprint import pprint


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


# all_rolls = [
#     (a, b, c) for a in range(6, 0, -1) for b in range(a, 0, -1) for c in range(b, 0, -1)
# ]
# sorted_rolls = sorted(all_rolls, key=classify)


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

    decision = decide_after_roll(state, roll, GreedyAllIn())

    history.append((state.copy(), roll, decision))

    if decision["action"] == "stop":
        state = decision["state"]
        break
    else:
        state = decision["state"]

final = normalize((1,) * state["held_ones"] + roll)

for step in history:
    pprint(step)
