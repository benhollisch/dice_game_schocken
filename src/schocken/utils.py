from collections.abc import Sequence


def normalize(dice: Sequence[int]) -> tuple[int, ...]:
    return tuple(sorted(dice, reverse=True))
