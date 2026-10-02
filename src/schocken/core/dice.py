from random import randint
from collections.abc import Sequence


def normalize(dice: Sequence[int]) -> tuple[int, ...]:
    """Sortiert die Würfel in absteigender Reihenfolge."""
    return tuple(sorted(dice, reverse=True))


def roll_dice(dices_used: int = 3) -> tuple[int, ...]:
    """Simuliert einen Wurf von `dices_used` Würfeln."""
    dices = [randint(1, 6) for _ in range(dices_used)]
    return normalize(dices)
