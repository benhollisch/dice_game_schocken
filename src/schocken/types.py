"""
Typdefinitionen für das Schocken-Spiel.

Enthält TypedDicts für strukturierte Datentypen die modulübergreifend
verwendet werden.
"""

from typing import TypedDict, Literal


class GameState(TypedDict):
    """Repräsentiert den vollständigen Zustand eines Spielerzuges."""

    held_ones: int
    rolls_left: int
    rolls_used: int
    visible_state: tuple[int, ...] | None
    must_continue: bool
    dice_to_roll: int


class PublicPlayerState(TypedDict):
    """Öffentlich sichtbarer Zustand eines Spielers am Tisch."""

    player: str
    turn_order: int
    visible_state: tuple[int, ...] | None
    is_closed: bool


class Decision(TypedDict):
    """Rückgabe von decide_after_roll() und strategy.choose().

    Bei action='continue' sind final und rank nicht gesetzt.
    Bei action='stop' sind final und rank immer vorhanden.
    """

    action: Literal["stop", "continue"]
    final: tuple[int, ...] | None
    rank: tuple[int, ...] | None
    state: GameState


class TurnResult(TypedDict):
    """Rückgabe von play_turn()."""

    final: tuple[int, ...]
    rank: tuple[int, ...]
    rolls_used: int
    visible_state: tuple[int, ...] | None
    history: list[dict]
