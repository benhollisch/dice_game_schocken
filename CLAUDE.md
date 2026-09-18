# Schocken-Simulation

Simulationsstudie zum Würfelspiel Schocken. Ziel ist die Analyse verschiedener
Strategien und die Herleitung dominanter bzw. erwartungswertoptimaler Spielweisen.
Ein begleitendes Paper ist in Arbeit.

## Arbeitsweise

Der Entwickler möchte selbst denken. Lösungen werden **nicht** vorweggenommen, sondern
erst auf direkte Anfrage präsentiert und dann erklärt. Bei Designentscheidungen:
Optionen mit Vor- und Nachteilen darstellen, Rückfragen stellen, die Entscheidung dem
Entwickler überlassen.

Code wird vorgeschlagen, nicht direkt geschrieben — außer es wird ausdrücklich darum
gebeten.

## Spielregeln (implementierte Variante)

Drei Würfel, bis zu drei Würfe pro Zug. Der Startspieler legt mit seiner Wurfzahl die
Obergrenze für alle Nachfolger fest (`round_max_rolls`).

**Rangfolge** (aufsteigend, kleiner ist besser):
- Schock-Out `(1,1,1)` → Rang `(0,0)`
- Schock `(a,1,1)` → Rang `(0, 7-a)`
- General `(a,a,a)` → Rang `(1, 6-a)`
- Straße `(a, a-1, a-2)` → Rang `(2, 6-a)`
- Hausnummer → Rang `(3, -a, -b, -c)`

**Tie-Break:** erst weniger Würfe, dann frühere Position.

**Sechsen-Konversion:** Im ersten und zweiten Wurf dürfen zwei Sechsen zu einer Eins
bzw. drei Sechsen zu zwei Einsen gedreht werden, sofern noch ein Wurf folgt. Wer
konvertiert, muss weiterwürfeln (`must_continue`).

**Deckel:** Der Rundengewinner bestimmt über sein Bild den Deckelwert, der Verlierer
erhält die Deckel. Bei leerem Pot wandern sie aus dem Stapel des Gewinners. Schock-Out
überträgt alle Deckel im Spiel an den Verlierer.

**Halbzeiten:** Wer alle Deckel hat, verliert die Halbzeit und steht im Finale. Nach der
zweiten Halbzeit spielen die beiden Halbzeitverlierer das Finale aus.

## Modulstruktur

```
src/schocken/
├── types.py          # TypedDicts: GameState, Decision, TurnResult, PublicPlayerState
├── utils.py          # normalize()
├── dice.py           # roll_dice()
├── classification.py # is_shock, is_general, is_straight, is_shock_out, classify, lid_value
├── state.py          # next_states(), decide_after_roll()
├── distribution.py   # Rangverteilungen, Gegnertabellen, Überlebenswahrscheinlichkeiten
├── game.py           # Player, Game, play_turn(), compare_results()
├── simulation.py     # simulate_games(), print_round_summary()
├── analysis.py       # Konfidenzintervalle, HHI, Rosenbluth, Gini, Chi-Quadrat, print_summary()
└── strategies/
    ├── base.py       # BaseStrategy (ABC), danger_score, total_danger, worst_public_rank
    ├── absolute.py   # GreedyAllIn, StaticThresholdStrategy
    └── relative.py   # PublicThreshold, AdaptiveGreedy, HybridThreshold, DangerAware
testing/
└── test_distribution.py
main.py
```

## Designentscheidungen

- **`TypedDict` statt `dataclass`** — dict-Syntax bleibt, Typ-Hints für statische Analyse.
  `GameState(...)`-Konstruktorsyntax wird verwendet, wenn alle Felder explizit gesetzt
  werden; `{**state, "key": value}` beim partiellen Überschreiben.
- **`ABC` statt `Protocol`** für Strategien — expliziter Fehler bei fehlender
  `choose()`-Implementierung.
- **`# type: ignore` gezielt** einsetzen, wo Mypy den Kontrollfluss nicht ableiten kann.
  Keine `assert`-Statements, die nur für Mypy existieren.
- **Ränge statt Würfelbilder** in allen Verteilungsrechnungen — `classify()` ist injektiv,
  es geht keine Information verloren.
- **Rohdaten nicht beim Speichern runden**, nur bei der Ausgabe.
- **Typ-Hints durchgängig**, aber `tuple[int, ...]` statt `tuple[int, int, int]` — eine
  Sensitivitätsanalyse über die Würfelanzahl ist geplant.

## Zentrale Befunde

Siehe `docs/ERKENNTNISSE.md` für die ausführliche Fassung.

1. **`classify()` ist injektiv** — der Rang ist eine gleichwertige Umkodierung des
   Würfelbilds, keine Vergröberung.
2. **Tupel-Vergleich ist sicher** — gleiche erste Komponente bedeutet gleiche Kategorie
   und damit gleiche Länge.
3. **Herauslegen von Einsen ist nicht universell dominant** — Gegenbeispiel existiert,
   zeigt aber primär Dominanz des Stoppens.
4. **Ohne Konversion kollabiert die Rekursion auf eine Binomialverteilung** mit
   `q_m = 1 - (5/6)^m`. Referenzwert: `P(X_{3,3}=3) = (91/216)^3 ≈ 0.074781`.
5. **Mit Konversion** (Enumeration unter GreedyAllIn): `≈ 0.086164`.
6. **Monotonieverletzung unter GreedyAllIn** — fünf Verletzungen am unteren Rangende beim
   Übergang m=1 → m=2. Kein Enumerationsfehler, sondern Eigenschaft der Strategie.
   GreedyAllIn ist als Gegnermodell **nicht konservativ**. Der Monotonie-Check eignet
   sich als Regressionstest für die optimale Politik.
7. **First-Mover-Kopplung** — die eigene Wurfzahl verbessert die eigene Rangverteilung,
   hebt aber die Obergrenze für alle Nachfolger. Straße `(6,5,4)`: survival fällt von
   0.8750 (m=1) auf 0.5553 (m=3). Empirisch verliert der Startspieler seltener
   (≈0.4793 vs ≈0.5207 bei n=10.000).

## Methodische Festlegungen

**Zielfunktion (Option A — Rundenverlust minimieren):**

    u(ρ, m) = 1[ρ < θ] · (P_m(Rang > ρ))^k

mit θ aus `worst_public_rank()`, `P_m` der Gegnerrangverteilung bei m Würfen, k der
Anzahl Nachfolger.

**Bellman-Struktur** (Zufall und Entscheidung wechseln sich ab):

    W(s) = Σ_r P(r | d(s)) · Q(s, r)                    # vor dem Wurf
    Q(s, r) = max_a { u(final) falls stop, W(s') falls continue }   # nach dem Wurf

Anker bei `rolls_left = 1`, wo keine Entscheidung mehr existiert.

**θ ist Parameter, nicht Zustandsdimension** — die Induktion wird einmal pro θ gerechnet,
statt den Zustandsraum zu vervielfachen.

**Gegnerverteilungen werden tabelliert** — `P_m` hängt weder vom Tischzustand noch vom
eigenen Bild ab. Drei Enumerationen genügen für eine ganze Simulationskampagne.

**Rückwärtsinduktion statt Referenzpolitik** — eine unterstellte Politik wäre zirkulär
und beantwortete nur die Frage nach der besten ersten Abweichung.

## Offene Punkte

- [ ] **Rückwärtsinduktion** in `strategies/optimal.py` implementieren
- [ ] Zielfunktion Option B (erwartete Deckelanzahl) und C (Halbzeitverlust)
- [ ] **Dominanz des Herauslegens** empirisch prüfen, gegeben die Stop-Entscheidung
- [ ] **Fixpunkt-Iteration**: optimale Politik gegen sich selbst tabellieren — Konvergenz offen
- [ ] First-Mover-Bias quantifizieren (Startposition als Kovariate)
- [ ] Sensitivitätsanalyse über Spieler- und Würfelanzahl
- [ ] Präfix-Heuristiken als Strategiefamilie (reale Spieler schauen auf die höchste
      Augenzahl, nicht auf den vollen Rang)
- [ ] `parse_threshold()` in `base.py` — Threshold wahlweise als Würfelbild oder Rang
- [ ] TODO in `distribution.py`: `decide_after_roll` wird ohne `public_table_state`
      aufgerufen; für reaktive Strategien ist die Enumeration daher nicht korrekt

## Konventionen

- Docstrings auf Deutsch, Code und Bezeichner auf Englisch
- Google-Style Docstrings mit Args/Returns/Raises
- Mypy läuft über das Projekt, Ruff als Linter
- Gespräche auf Deutsch, Duzen
