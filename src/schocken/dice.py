from random import randint
from schocken.utils import normalize


def roll_dice(dices_used: int = 3) -> tuple[int, ...]:
    dices = [randint(1, 6) for _ in range(dices_used)]
    return normalize(dices)
