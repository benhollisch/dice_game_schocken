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
    dice_to_roll: int


class PublicPlayerState(TypedDict):
    """Öffentlich sichtbarer Zustand eines Spielers am Tisch."""

    player: str
    turn_order: int
    visible_state: tuple[int, ...] | None
    rolls_used: int


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


class RoundContext(TypedDict):
    """
    Zustand der laufenden Runde aus Sicht des Spielers am Zug.

    Im Unterschied zu GameState beschreibt dieser Typ nicht den eigenen
    Wurfverlauf, sondern die Tischsituation: wer bereits gespielt hat, wie
    viele Spieler insgesamt aktiv sind und welches Wurfbudget gilt.

    pot ist der Deckelstand im Stapel zu Rundenbeginn. lids enthält die
    Deckelstände aller aktiven Spieler zu Rundenbeginn in Sitzreihenfolge
    dieser Runde; Index i gehört zum Spieler mit turn_order i.
    """

    n_active: int
    max_rolls: int | None
    public_table_state: list[PublicPlayerState]
    pot: int
    lids: list[int]
