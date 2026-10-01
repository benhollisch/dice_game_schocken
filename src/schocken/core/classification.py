"""
Klassifikation von Würfelbildern im Schocken-Spiel.

Enthält Funktionen zur Erkennung und Klassifikation von Würfelkombinationen
sowie die Berechnung des Deckelwerts eines Würfelbildes.
"""

from schocken.utils import normalize


def is_shock_out(dice: tuple[int, ...]) -> bool:
    """Prüft ob das Würfelbild ein Schock-Out ist (drei Einsen)."""
    return dice == (1, 1, 1)


def is_shock(dice: tuple[int, ...]) -> bool:
    """Prüft ob das Würfelbild ein Schock ist (mind. zwei Einsen)."""
    _, b, c = dice
    return b == c == 1


def is_general(dice: tuple[int, ...]) -> bool:
    """Prüft ob das Würfelbild ein General ist (drei gleiche, keine Einsen)."""
    a, b, c = dice
    return a == b == c and a != 1


def is_straight(dice: tuple[int, ...]) -> bool:
    """Prüft ob das Würfelbild eine Straße ist (drei aufeinanderfolgende Werte)."""
    a, b, c = dice
    return a == b + 1 == c + 2


def classify(dice: tuple[int, ...]) -> tuple[int, ...]:
    """
    Klassifiziert ein Würfelbild und gibt einen vergleichbaren Rang zurück.

    Der Rang ist so aufgebaut, dass niedrigere Werte besser sind:
      (0, x) -> Schock
      (1, x) -> General
      (2, x) -> Straße
      (3, x) -> Normalwurf

    Args:
        dice: Normalisiertes Würfelbild als Tuple.

    Returns:
        Tuple das den Rang repräsentiert.

    Raises:
        ValueError: Wenn nicht genau 3 Würfel übergeben werden.
    """
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
        return (3, -a, -b, -c)


def lid_value(roll: tuple[int, ...]) -> int:
    """
    Berechnet den Deckelwert eines Würfelbildes.
    Schock-Out wird separat über is_shock_out() behandelt.

    Returns:
        Anzahl der zu verteilenden Deckel als int.
    """
    a, b, c = normalize(roll)

    if is_shock(roll):
        return a
    if is_general(roll):
        return 3
    if is_straight(roll):
        return 2
    return 1
