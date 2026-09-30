# Erkenntnisse — Schocken-Simulation

Sammlung der analytischen und methodischen Befunde aus der Modellentwicklung.
Stand: 30.09.2026

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

Die Wahrscheinlichkeit, dass ein *einzelner* Gegner schlechter abschneidet, fällt von
87,5 % auf 55,5 %. Das erklärt, warum frühes Stoppen mit einem mittelmäßigen Bild
rational sein kann.

Wie diese Einzelwahrscheinlichkeiten zur Zielfunktion zusammengesetzt werden, steht in
Abschnitt 10. Eine frühere Fassung dieses Abschnitts enthielt an dieser Stelle eine
fehlerhafte Zielfunktion.

**Einschränkung:** Die Kopplung gilt nur für den Startspieler. Wer nach ihm dran ist, hat
die Obergrenze bereits vorgegeben — seine Wurfzahl wirkt nur noch über den Tie-Break.

**Empirischer Beleg:** Bei zwei identischen `StaticThresholdStrategy`-Spielern verliert
der Startspieler seltener (≈0.4793 vs ≈0.5207 bei n=10.000), Konfidenzintervalle
überlappen nicht.

## 8. Unabhängigkeitsannahme für Nachfolger

Das Produkt in der Zielfunktion (Abschnitt 10) setzt Unabhängigkeit der Gegnerergebnisse
voraus. Die Würfel sind unabhängig, die Entscheidungen nicht ganz — alle sehen denselben
Tisch.

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

**Tischzustand als Parameter, nicht als Zustandsdimension.** Die öffentliche Information
— Ränge offener Vorgänger, gehaltene Einsen verdeckter Vorgänger, Anzahl der Nachfolger,
Wurfbudget — ist innerhalb eines Zuges konstant. Sie geht als Parameter in die
Zielfunktion ein, statt den Zustandsraum der Induktion aufzublähen.

**Tabellierung der Gegnerverteilungen.** P_m hängt weder vom Tischzustand noch vom
eigenen Bild ab. Drei Enumerationen (m = 1, 2, 3) genügen für die gesamte Simulation;
kumulierte Tabellen machen auch die Tailsummen zu Lookups.

## 10. Zielfunktion: nicht Verlierer sein

Ziel der Option A ist, die Runde **nicht zu verlieren**. Dafür reicht es, dass
**mindestens ein** Gegner schlechter abschneidet. Man verliert nur, wenn **jeder**
Gegner besser ist:

    P(nicht Verlierer | ρ, m) = 1 − Π_j (1 − S_j(ρ, m))

mit S_j(ρ, m) = Wahrscheinlichkeit, dass Gegner j schlechter abschneidet als man selbst
mit Rang ρ nach m Würfen — einschließlich beider Tie-Break-Stufen (weniger Würfe, dann
frühere Position).

**Korrektur einer früheren Fassung.** Zunächst war die Zielfunktion als

    u(ρ, m) = 1[ρ < θ] · S(ρ)^k

formuliert. Das ist die Wahrscheinlichkeit, **alle** Gegner zu schlagen, also die Runde
zu gewinnen — nicht, sie nicht zu verlieren. Bei zwei Spielern fallen beide Formeln
zusammen, ab drei Spielern unterscheiden sie sich stark. Beispiel: Man hat eine Straße,
ein offener Vorgänger eine Hausnummer, ein Nachfolger folgt noch. Man ist sicher nicht
Verlierer; die alte Formel liefert trotzdem nur S(ρ). Eine Politik auf Basis der alten
Formel spielt wie jemand, der gewinnen will, und nimmt Risiken, die sich für bloßes
Nicht-Verlieren nicht lohnen.

Dieselbe fehlerhafte Formel steht im Paper-Entwurf als Gleichung (3) und ist dort zu
korrigieren.

**Die drei Gegnergruppen:**

| Gruppe | S_j | Wurfzahl des Gegners | acts_first |
|---|---|---|---|
| offene Vorgänger | 0 oder 1 (Rang bekannt) | bekannt | False |
| verdeckte Vorgänger | bedingte Verteilung (Abschnitt 11) | volles Budget | False |
| Nachfolger | Budgetverteilung P_m | aus der Verteilung | True |

`acts_first` ist aus Sicht des entscheidenden Spielers definiert: War er vor dem
betrachteten Gegner an der Reihe? Gegenüber Vorgängern also nie.

**Konsequenzen:**
- Schlägt man einen offenen Vorgänger, ist der Wert sofort 1. Der schlechteste offene
  Rang θ ist damit eine **hinreichende Bedingung für Sicherheit**, kein Faktor.
- Gleichstand mit einem offenen Vorgänger ist kein sicherer Verlust: Bei weniger Würfen
  gewinnt man ihn.
- Bei k identischen, unabhängigen Nachfolgern wird ihr Beitrag zu (1 − S_m(ρ, m))^k.
- Beim Startspieler ist m zugleich das Budget der Nachfolger (First-Mover-Kopplung,
  Abschnitt 7).

## 11. Verdeckte Vorgänger sind Gegner mit bedingter Verteilung

Wer sein Wurfbudget ausschöpft, veröffentlicht nur die herausgelegten Einsen; der letzte
Wurf bleibt verdeckt. Das entspricht der Spielregel. `worst_public_rank()` berücksichtigt
aber nur Bilder mit drei sichtbaren Würfeln — verdeckte Vorgänger fielen dadurch
vollständig aus der Zielfunktion heraus.

**Beobachteter Fehler:** Zwei Spieler, C4 (GreedyAllIn) eröffnet, braucht drei Würfe und
zeigt `(1, 1)`. OptimalStrategy (C5) sieht θ = None und null Nachfolger, bewertet jede
Option mit 1.0 und stoppt mit `(5,3,2)` — ein sicherer Verlust, da C4 garantiert einen
Schock oder Schock-Out hat.

**Richtige Modellierung:** Ein verdeckter Vorgänger mit h gehaltenen Einsen hat genau
einen verdeckten Wurf mit 3 − h Würfeln getan. Seine Rangverteilung ist damit exakt:

    P(Rang_j = r) = Σ_{w : classify(sort(1^h, w)) = r} P(w | 3 − h Würfel)

direkt aus `roll_distribution` und `classify`. Seine Wurfzahl ist das volle Budget.

Im Beispiel: je 1/6 Schock-Out und Schock 6 bis Schock 2. Ein eigener Schock 4 nach zwei
Würfen überlebt gegen C4 mit Wahrscheinlichkeit 3/6 (Schock 3 und 2 schlechter,
Schock 4 durch weniger Würfe gewonnen); nach drei Würfen nur mit 2/6, weil C4 den
Gleichstand über die frühere Position gewinnt.

**Nicht der Erwartungswert zählt.** „Im Mittel Schock 3,5“ ist keine geeignete
Zielgröße — entscheidend ist die Wahrscheinlichkeit, schlechter zu sein, und die hängt an
der ganzen Verteilung.
