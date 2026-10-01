# Erkenntnisse — Schocken-Simulation

Sammlung der analytischen und methodischen Befunde aus der Modellentwicklung.
Stand: 01.10.2026

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

## 12. Nicht-Verlieren am vollen Tisch: das Fünf-Spieler-Beispiel

### Ausgangslage

Fünf Spieler, man selbst sitzt auf Position 5. Alle vier Vorgänger haben ihr Budget von
drei Würfen ausgeschöpft und zeigen je `(1, 1)` — sie sind teilverdeckt mit h = 2. Ihr
verdeckter Würfel d ist gleichverteilt und von ihrer Strategie unabhängig (Abschnitt 11).
Jeder Vorgänger hat damit entweder einen Schock-Out (d = 1) oder einen Schock mit
Beizahl d.

Die Wahrscheinlichkeit, dass mindestens ein Vorgänger einen Schock-Out verdeckt hält, ist

    1 − (5/6)^4 = 671/1296 ≈ 51,8 %

### Die Entscheidung nach dem zweiten Wurf

Man selbst hat nach dem zweiten Wurf einen Schock mit Beizahl a und einen Wurf übrig.

**Stoppen.** Man hat zwei Würfe gebraucht, die Vorgänger drei. Gegen einen Vorgänger
besteht man, wenn seine Beizahl schlechter ist oder gleich — den Gleichstand gewinnt man
über die geringere Wurfzahl. Damit ist S_j = (a − 1)/6 und

    P(Verlierer | Stopp) = ((7 − a) / 6)^4

**Weiterwürfeln** mit dem einen freien Würfel, Ergebnis e. Man braucht dann ebenfalls drei
Würfe und verliert jeden Gleichstand, weil die Vorgänger früher an der Reihe waren:

| e | eigenes Endbild | Vorgänger schlechter, wenn | P(Verlierer \| e) |
|---|---|---|---|
| 1 | Schock-Out | d ≠ 1 | (1/6)^4 = 1/1296 |
| 6 | Schock 6 | d ∈ {2, …, 5} | (2/6)^4 = 1/81 |
| 5 | Schock 5 | d ∈ {2, 3, 4} | (3/6)^4 = 1/16 |
| 4 | Schock 4 | d ∈ {2, 3} | (4/6)^4 = 16/81 |
| 3 | Schock 3 | d = 2 | (5/6)^4 = 625/1296 |
| 2 | Schock 2 | nie | 1 |

Gemittelt über e: P(Verlierer | Weiterwürfeln) = 2275/7776 ≈ 29,3 %.

**Vergleich:**

| Bild nach Wurf 2 | P(Verlierer) bei Stopp | bei Weiterwürfeln | Entscheidung |
|---|---|---|---|
| `(1,1,6)` | 1/1296 ≈ 0,1 % | 29,3 % | stoppen |
| `(1,1,5)` | 1/81 ≈ 1,2 % | 29,3 % | stoppen |
| `(1,1,4)` | 1/16 ≈ 6,3 % | 29,3 % | stoppen |
| `(1,1,3)` | 16/81 ≈ 19,8 % | 29,3 % | stoppen |
| `(1,1,2)` | 625/1296 ≈ 48,2 % | 29,3 % | weiterwürfeln |

Die Stoppschwelle liegt bei Schock 3, also tiefer, als die Intuition „mindestens Schock 4“
nahelegt.

### Der Wert des Tie-Breaks

Derselbe Schock 5 hat nach zwei Würfen ein Verliererrisiko von 1/81 ≈ 1,2 %, nach drei
Würfen von 1/16 ≈ 6,3 % — das Fünffache. Ein Wurf weniger ist hier so viel wert wie eine
ganze Beizahlstufe: Schock 5 nach zwei Würfen ist exakt so sicher wie Schock 6 nach drei.

Allgemein verschiebt der gewonnene Gleichstand die Überlebenswahrscheinlichkeit gegen
jeden Vorgänger um 1/6. Bei vier Vorgängern potenziert sich das.

### Warum das Option-A-Logik ist

„Man muss nur nicht der Schlechteste sein, den Tisch räumt jemand anders ab“ ist genau die
korrigierte Zielfunktion aus Abschnitt 10. Gewinnen ist hier wertlos: Mit 51,8 % räumt
ohnehin ein Vorgänger ab, und die eigene Bildhöhe spielt nur gegen die Vorgänger eine
Rolle, nicht für einen eigenen Sieg.

Die korrigierte `OptimalStrategy` muss diese Stopptabelle reproduzieren. Das Beispiel
eignet sich als Regressionstest.

### Kein Unterschied bei eigenem Schock-Out

Würfelt man selbst einen Schock-Out, verliert man nur, wenn alle vier Vorgänger ebenfalls
einen verdeckten Schock-Out haben (1/1296) — dann gewinnen sie jeden Gleichstand über die
Position. Hat mindestens ein Vorgänger einen gewöhnlichen Schock, ist er der Verlierer.
Dieser Fall steckt bereits in der Zeile e = 1 und ändert die Entscheidung nicht.

## 13. Option B: erwartete Deckelveränderung

### Zielgröße

Option B minimiert die erwartete Veränderung des eigenen Deckelstands in der Runde.
Deckel werden linear gezählt.

### Drei Ausgänge, nicht zwei

Aus Sicht eines Spielers endet eine Runde auf eine von drei Arten: Er ist Verlierer,
Gewinner oder unbeteiligt. Was mit seinen Deckeln geschieht, hängt zusätzlich davon ab, ob
am Tisch ein Schock-Out fällt und ob der Pot noch Deckel enthält:

| Ausgang | Pot > 0 (Phase 1) | Pot leer (Phase 2) | Schock-Out am Tisch |
|---|---|---|---|
| Verlierer | + min(v(Gewinner), Pot) | + min(v(Gewinner), D_Gewinner) | + alle übrigen Deckel im Spiel |
| Gewinner | 0 | − min(v(eigen), D_eigen) | − D_eigen |
| unbeteiligt | 0 | 0 | − D_eigen |

Daraus:

    E[Δ] = Σ_{Verlierer-Ausgänge} P · erhalten
         − P(Gewinner, kein Schock-Out) · min(v(ρ), D_eigen)   [nur Phase 2]
         − P(nicht Verlierer, Schock-Out am Tisch) · D_eigen

Eine erste Fassung dieser Formel kannte nur Verlierer und Gewinner. Der dritte Term fehlte:
Fällt ein Schock-Out und man ist nicht Verlierer, gehen die eigenen Deckel ebenfalls an den
Verlierer — man ist raus, auch ohne selbst gewonnen zu haben.

### Schock-Out reduziert Option B auf Option A

Fällt am Tisch ein Schock-Out, ist es für einen Spieler gleichgültig, ob er Gewinner oder
unbeteiligt ist: In beiden Fällen verliert er alle Deckel und ist raus. Es zählt nur die
Unterscheidung Verlierer oder nicht. In diesem Zweig ist Option B dieselbe Zielfunktion
wie Option A, nur mit höherem Einsatz.

Die Unterscheidung nach Bildhöhe — der Gewinnerterm mit min(v(ρ), D) — wirkt nur in Runden
ohne Schock-Out. Im Fünf-Spieler-Beispiel aus Abschnitt 12 ist Nicht-Verlieren in Option B
deshalb noch wichtiger als in Option A: Mit 51,8 % räumt ein Vorgänger ab, und wer nicht
Verlierer ist, ist danach raus.

### Phase 1: Option A mit gewichteten Verlusten

Solange der Pot Deckel enthält, bringt Gewinnen direkt nichts — die Deckel kommen aus dem
Pot. Das eigene Bild zählt nur, um nicht Verlierer zu sein. Option B unterscheidet sich von
Option A dann nur darin, wie teuer ein Verlust ist: Gegen eine Hausnummer kostet er einen
Deckel, gegen einen Schock 6 bis zu sechs.

### Phase 2: Die Bildhöhe bekommt einen Wert

Ist der Pot leer, gibt der Gewinner eigene Deckel ab. Ein sicheres Bild wird dadurch nicht
wertlos, ein höheres aber wertvoller. Die Deckelgrenze kehrt diesen Anreiz je nach eigenem
Stand um:

| Eigene Deckel | Gewinnen mit Straße | Gewinnen mit Schock 6 | Anreiz, auf Höhe zu spielen |
|---|---|---|---|
| 1 | −1 | −1 | keiner |
| 3 | −2 | −3 | gering |
| 8 | −2 | −6 | deutlich |

Wer viele Deckel hat, profitiert davon, ein sicheres Bild zu verbessern. Wer wenige hat,
sichert nur ab. Die Abhängigkeit vom eigenen Deckelstand fällt aus der Zielfunktion heraus,
ohne dass sie hineinkonstruiert werden muss.

Gewinner- und Verliererterm ziehen in Phase 2 oft gegeneinander: Weiterwürfeln mit einer
Straße erhöht die Chance auf ein hohes Bild, aber auch das Risiko, auf eine Hausnummer
abzurutschen und Verlierer zu werden.

### Rechnung unter Unabhängigkeit

Jedem Ergebnis wird ein Vergleichsschlüssel (Rang, Wurfzahl, Position) zugeordnet; kleiner
ist besser. Unter allen Spielern ist diese Ordnung strikt, weil Positionen verschieden
sind. Für das eigene Ergebnis mit Schlüssel x und Gegner k mit Schlüssel K_k gilt:

    P(Verlierer)                       = Π_k P(K_k < x)
    P(Gewinner)                        = Π_k P(K_k > x)
    P(Verlierer, Gewinner = j mit o)   = P_j(o) · 1[o < x] · Π_{k≠j} P(o < K_k < x)
    P(Schock-Out-Gewinner vor mir)     = 1 − Π_k (1 − P(K_k < x, Rang_k = Schock-Out))

Die letzte Zeile nutzt, dass Schock-Outs die kleinsten Schlüssel überhaupt sind: Hat
irgendein Gegner einen Schock-Out vor einem selbst, ist der beste Gegner ein Schock-Out.

Mit einer globalen Nummerierung aller Schlüssel und kumulierten Wahrscheinlichkeiten je
Gegner lassen sich alle Terme vektorisiert berechnen.

### Benötigte Information

`RoundContext` braucht zusätzlich den Pot und die Deckelstände aller aktiven Spieler in
Sitzreihenfolge — auch die der Nachfolger, die im `public_table_state` noch nicht stehen.
Beides ist am Tisch öffentlich.

### Regressionstests

- Die Wahrscheinlichkeit P(Verlierer) aus der Option-B-Rechnung muss exakt 1 minus dem Wert
  der Option-A-Zielfunktion entsprechen.
- Ist jeder Deckelwert 1, der Pot ausreichend groß und Schock-Out ohne Sonderregel, ist
  E[Δ] = P(Verlierer); Option B muss dann dieselben Entscheidungen treffen wie Option A.

## 14. Lineare Deckel gegen die eigentliche Zielgröße

Die eigentliche Auszahlung ist binär: Wer das Finale verliert, zahlt eine Runde. Deckel
sind ein Zwischenstand auf dem Weg dorthin. Lineares Zählen ist rational, wenn Deckel die
Zielgröße sind. Ob sie es sind, ist offen.

Zwei Stellen, an denen die lineare Zählung die eigentliche Zielgröße verfehlt:

- **Bei null.** Wer in Phase 2 auf null kommt, scheidet aus der Halbzeit aus und riskiert
  nichts mehr. Linear ist der Schritt von 1 auf 0 so viel wert wie der von 9 auf 8. Mit
  wenigen Deckeln verschiebt sich das Ziel dadurch von „nicht verlieren“ ein Stück zu
  „gewinnen“, ohne dass ein hohes Bild nötig wäre — die Bildhöhe ist wegen der
  Deckelgrenze ohnehin wertlos.
- **Beim Halbzeitverlust.** Der Schritt auf alle Deckel entscheidet die Halbzeit.

Anders zu spielen, wenn man nah an einer dieser Grenzen steht, ist nicht emotional, sondern
die Optimierung der richtigen Zielgröße statt eines Ersatzmaßes. Aus dem Turnierpoker ist
der Unterschied zwischen Chip-Erwartungswert und Turniergewinnwahrscheinlichkeit bekannt.

Eine angenommene Funktionsform, etwa quadratisch in den Deckeln, wäre willkürlich. Für
Option C lässt sich der Wert eines Deckelstands berechnen: als Wahrscheinlichkeit, die
Halbzeit von diesem Stand aus zu verlieren. Die Nichtlinearität ist dann ein Ergebnis,
keine Annahme.
