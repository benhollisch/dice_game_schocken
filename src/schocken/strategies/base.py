"""
Abstrakte Basisklasse für Schocken-Strategien.

Enthält die abstrakte Basisklasse BaseStrategy sowie Hilfsfunktionen
zur Bewertung des öffentlichen Tischzustands.
"""

from abc import ABC, abstractmethod
from schocken.types import GameState, Decision, PublicPlayerState
from schocken.classification import classify


class BaseStrategy(ABC):
    """Abstrakte Basisklasse für alle Schocken-Strategien."""

    @abstractmethod
    def choose(
        self,
        options: list[Decision],
        state: GameState,
        roll: tuple[int, ...],
        public_table_state: list[PublicPlayerState] | None = None,
    ) -> Decision:
        """
        Wählt eine Entscheidung aus den verfügbaren Optionen.

        Args:
            options: Liste möglicher Entscheidungen.
            state: Aktueller Spielzustand.
            roll: Aktueller Wurf als normalisiertes Tuple.
            public_table_state: Öffentlich sichtbare Zustände der anderen Spieler.

        Returns:
            Die gewählte Entscheidung.
        """
        ...


def worst_public_rank(
    public_table_state: list[PublicPlayerState] | None,
) -> tuple[int, ...] | None:
    """
    Bestimmt den schlechtesten öffentlich sichtbaren Rang am Tisch.

    Args:
        public_table_state: Öffentlich sichtbare Zustände der anderen Spieler.

    Returns:
        Schlechtester Rang als Tuple, oder None wenn kein Rang sichtbar ist.
    """
    if not public_table_state:
        return None

    public_ranks = [
        classify(p["visible_state"])
        for p in public_table_state
        if p["visible_state"] is not None and len(p["visible_state"]) == 3
    ]

    if not public_ranks:
        return None

    return max(public_ranks)


def danger_score(visible_state: tuple[int, ...] | None) -> float:
    """
    Berechnet einen Gefahrenwert für einen sichtbaren Zustand.

    Args:
        visible_state: Öffentlich sichtbarer Zustand eines Spielers.

    Returns:
        Gefahrenwert zwischen 0 und 1.
    """
    if visible_state is None:
        return 0.5
    if len(visible_state) == 1:
        return 0.8
    if len(visible_state) == 2:
        return 0.95
    return 0.2


def total_danger(public_table_state: list[PublicPlayerState]) -> float:
    """
    Berechnet den Gesamtgefahrenwert basierend auf allen sichtbaren Zuständen.

    Args:
        public_table_state: Öffentlich sichtbare Zustände der anderen Spieler.

    Returns:
        Gesamtgefahrenwert zwischen 0 und 1.
    """
    safe_probability = 1.0
    for p in public_table_state:
        d = danger_score(p["visible_state"])
        safe_probability *= 1 - d

    return 1 - safe_probability
