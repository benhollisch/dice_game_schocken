# Erkenntnisse — Schocken-Simulation

Sammlung der analytischen und methodischen Befunde aus der Modellentwicklung.
Stand: 18.09.2026

---

## 1. Rangkodierung ist informationserhaltend

`classify()` bildet Würfelbilder injektiv auf Ränge ab: Aus `(0, 7-a)` lässt sich die
Beizahl zurücklesen, aus `(1, 6-a)` und `(2, 6-a)` der Wert, und `(3, -a, -b, -c)`
enthält ohnehin alle drei Würfel.

**Konsequenz:** Der Rang ist keine gröbere Darstellung des Würfelbilds, sondern eine
gleichwertige Umkodierung — zusätzlich bereits in der Ordnung, die zum Vergleichen
gebraucht wird. Alle Verteilungsrechnungen können direkt auf Rängen arbeiten;
`lid_value` lässt sich als Funktion des Rangs schreiben.

## 2. Tupel-Vergleich ist sicher

Zwei Ränge mit derselben ersten Komponente liegen immer in derselben Kategorie und
haben damit dieselbe Länge. Der lexikographische Vergleich unterschiedlich langer Tupel
ist deshalb unkritisch — der Fall "gleiches erstes Element, unterschiedliche Länge"
tritt nicht auf.

**Konsequenz:** `(3, -a, -b, -c)` als flaches Tupel statt `(3, (-a, -b, -c))` ist
zulässig und macht den Rückgabetyp von `classify()` einheitlich `tuple[int, ...]`.

## 3. Herauslegen von Einsen ist nicht universell dominant

Gegenbeispiel: Ein Gegner hat `(6,5,5)` offen stehen — eine Hausnummer. Man selbst
würfelt `(3,2,1)`, eine Straße, und schlägt ihn damit sicher. Das Herauslegen der Eins
und Weiterwürfeln würde die sichere Position aufgeben.

**Einordnung:** Das Beispiel zeigt primär, dass **Stoppen** dominant ist, nicht dass
Nicht-Herauslegen dominant ist. Trennt man die Entscheidungen — erst "stoppen oder
weiter", dann "wie viele Einsen herauslegen" —, entfallen die suboptimalen
Continue-Fälle. Die Dominanz des Herauslegens im verbleibenden Fall ist noch offen und
empirisch zu prüfen.

## 4. Analytische Verteilung der Einsenanzahl (ohne Sonderregeln)

Ohne Sechsen-Konversion entkoppelt die Dynamik "alle Einsen herauslegen, Rest
nachwürfeln" die Würfel vollständig: Jeder Würfel durchläuft unabhängig denselben
Prozess.

Für einen einzelnen Würfel gilt

    P(Eins nach m Würfen) = 1 - (5/6)^m =: q_m

und damit

    X_{n,m} ~ B(n, q_m)

Die allgemeine Rekursion kollabiert also auf eine Binomialverteilung. Beweis per
Induktion über m: Für m=0 ist q_0 = 0, was der Indikator-Anfangsbedingung entspricht;
im Schritt ergibt die Faltung zweier Binomialterme wieder eine Binomialverteilung mit
q_{m-1} + (1 - q_{m-1}) * p = 1 - (1-p)^m = q_m.

**Referenzwert:** P(X_{3,3} = 3) = (91/216)^3 ≈ 0.074781

## 5. Sechsen-Konversion bricht die Unabhängigkeit

Die Konversion koppelt die Würfel: Ob eine Eins geschenkt wird, hängt davon ab, was die
*anderen* Würfel zeigen. Eine geschlossene Form existiert dann nicht mehr.

Innerhalb eines einzelnen Wurfs bleibt die Rechnung jedoch analytisch:

    Δ = A + κ(B),   κ(0)=κ(1)=0, κ(2)=1, κ(3)=2

mit (A, B) gemeinsam multinomial über Einsen, Sechsen und Rest. Daraus ergibt sich
P(Δ = j) als Summe über alle (a, b) mit a + κ(b) = j. Eingesetzt in die Rekursion ist
die Konversion damit analytisch erfasst — der Zustand (s, d) bleibt Markov, weil Sechsen
nicht über Würfe hinweg übertragen werden.

**Grenze:** Eine Verteilung über Einsenanzahlen lässt sich nicht in eine Rangverteilung
übersetzen. Bei zwei Einsen entscheidet die Beizahl, ohne Einsen entscheidet sich General
gegen Straße gegen Hausnummer. Für die Zielfunktion wird die volle
Würfelbildverteilung benötigt.

**Enumerationswert mit Konversion:** P(drei Einsen) ≈ 0.086164 unter GreedyAllIn, gegenüber
0.074781 ohne Konversion.

## 6. Monotonieverletzung unter GreedyAllIn

Der Monotonie-Check über `survival_probability(tables[m], rank)` zeigt fünf Verletzungen,
alle am unteren Ende der Rangskala und alle beim Übergang m=1 → m=2:

| Rang | m=1 | m=2 | m=3 |
|---|---|---|---|
| (3, -4, -4, -2) | 0.152778 | 0.154835 | 0.130697 |
| (3, -4, -3, -3) | 0.125000 | 0.129630 | 0.110425 |
| (3, -4, -2, -2) | 0.083333 | 0.086420 | 0.073617 |
| (3, -3, -3, -2) | 0.041667 | 0.043210 | 0.036808 |
| (3, -3, -2, -2) | 0.013889 | 0.018004 | 0.016537 |

**Ursache:** Die Rangordnung behandelt Einsen gegensätzlich — im Schock das Wertvollste,
in der Hausnummer das Schlechteste. GreedyAllIn legt jede Eins heraus; wird der Schock
nicht erreicht, bleibt sie im Endbild und zieht den Rang nach unten. Mit nur einem Wurf
kann dieser Fall nicht auftreten. Bei m=2 entsteht dadurch eine neue Klasse schlechter
Ausgänge wie `(3,2,1)` oder `(2,2,1)`. Bei m=3 überwiegt der Schock-Effekt wieder.

**Einordnung:** Kein Enumerationsfehler, sondern eine Eigenschaft der Referenzstrategie.
Monotonie in m ist eine Eigenschaft **optimaler** Politiken: Wer stoppen darf, kann einen
zusätzlichen Wurf ignorieren. GreedyAllIn stoppt nie (außer bei Schock-Out) und muss den
schädlichen Zusatzwurf nehmen.

**Konsequenz 1:** Unter der optimalen Politik muss der Check verletzungsfrei durchlaufen.
Er eignet sich als Regressionstest für `strategies/optimal.py`.

**Konsequenz 2:** GreedyAllIn ist als Gegnermodell **nicht konservativ**. Es unterschätzt
die Gefahr am unteren Rangende — also genau dort, wo ein Spieler mit mittelmäßigem Bild
die Stop-Entscheidung trifft. Die Referenzverteilung sollte durch die optimale Politik
ersetzt werden, sobald diese vorliegt.

## 7. First-Mover-Kopplung

Die eigene Wurfzahl wirkt in zwei entgegengesetzte Richtungen: Sie verbessert die eigene
Rangverteilung, hebt aber zugleich `round_max_rolls` und damit die Obergrenze für alle
Nachfolger.

Quantifiziert am Beispiel einer Straße `(6,5,4)`:

| m | survival_probability |
|---|---|
| 1 | 0.8750 |
| 2 | 0.7238 |
| 3 | 0.5553 |

Die Wahrscheinlichkeit, dass ein Gegner schlechter abschneidet, fällt von 87,5 % auf
55,5 %. Das erklärt, warum frühes Stoppen mit einem mittelmäßigen Bild rational sein kann.

**Zielfunktion:**

    u(ρ, m) = 1[ρ < θ] · (P_m(Rang > ρ))^k

mit θ aus `worst_public_rank()`, P_m der Rangverteilung eines Gegners mit m Würfen und
k der Anzahl der Nachfolger.

**Einschränkung:** Die Kopplung gilt nur für den Startspieler. Wer nach ihm dran ist, hat
die Obergrenze bereits vorgegeben — seine Wurfzahl wirkt nur noch über den Tie-Break.

**Empirischer Beleg:** Bei zwei identischen `StaticThresholdStrategy`-Spielern verliert
der Startspieler seltener (≈0.4793 vs ≈0.5207 bei n=10.000), Konfidenzintervalle
überlappen nicht.

## 8. Unabhängigkeitsannahme für Nachfolger

Das Produkt über die noch offenen Gegner setzt Unabhängigkeit ihrer Ergebnisse voraus.
Die Würfel sind unabhängig, die Entscheidungen nicht ganz — alle sehen denselben Tisch.

Unter GreedyAllIn tritt das Problem nicht auf, da die Strategie den `public_table_state`
ignoriert; dort ist die Unabhängigkeit exakt. Für reaktive Referenzstrategien ist sie
eine Näherung.

## 9. Methodische Festlegungen

**Rückwärtsinduktion statt Referenzpolitik.** Eine unterstellte Politik zur Bewertung
wäre zirkulär und beantwortete nur die Frage nach der besten ersten Abweichung. Die
Rückwärtsinduktion ankert bei `rolls_left = 1`, wo keine Entscheidung mehr existiert.

**Bellman-Struktur.** Zufall und Entscheidung wechseln sich ab:

    W(s) = Σ_r P(r | d(s)) · Q(s, r)                    (vor dem Wurf)
    Q(s, r) = max_a { u(final) falls stop,
                      W(s') falls continue }             (nach dem Wurf)

**θ als Parameter, nicht als Zustandsdimension.** Der Gegnerstand geht über einen
Schwellenrang ein, statt den Zustandsraum aufzublähen. Die Induktion wird einmal pro θ
gerechnet.

**Tabellierung der Gegnerverteilungen.** P_m hängt weder vom Tischzustand noch vom
eigenen Bild ab. Drei Enumerationen (m = 1, 2, 3) genügen für die gesamte Simulation;
kumulierte Tabellen machen auch die Tailsummen zu Lookups.
