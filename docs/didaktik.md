# Didaktik

Warum der Fragebogen so aufgebaut ist — und was er bewusst _nicht_ tut.

## Zielgruppe

Schüler:innen mit Realschulabschluss, ca. 14–17 Jahre alt, die vor der Frage
„Was nach der Schule?" stehen. Viele kennen nur die zehn üblichen Berufe aus
dem Bekanntenkreis. Das Tool soll das Spektrum öffnen — nicht engführen.

## Kernprinzipien

### 1. Spektrum statt „Top-Treffer"

Klassische Berufstests liefern oft _DEN_ einen Beruf. Das ist pädagogisch
fragwürdig: 15-Jährige sollen nicht das Gefühl bekommen, ein Algorithmus habe
ihre Zukunft entschieden. Deshalb zeigen wir bis zu **10 Vorschläge als
gleichberechtigtes Spektrum**. Die Reihenfolge folgt dem Score, aber die
Karten sind visuell gleichwertig — kein Podium.

### 2. Geschlechtsneutralität

Alle Berufe werden gleichwertig präsentiert, ohne Filter nach „typisch
männlich/weiblich". Das Matching kennt keine Geschlechts-Variable. Der
Fragebogen fragt sie nicht ab.

### 3. Konkrete Tätigkeiten statt abstrakter Interessen

Statt „Magst du Mathe?" fragen wir: „Stell dir vor, du sollst Wasserrohre
verlegen und verbinden — wie fühlt sich das an?" Tätigkeitsbeschreibungen
sind für Jugendliche greifbarer als Interessens-Labels. Sie zwingen zur
inneren Vorstellung, nicht zur Selbstetikettierung.

### 4. Nur Ausbildungsberufe

Studiengänge bleiben außen vor. Das Tool richtet sich an Realschüler:innen
und soll keine Hierarchie „Studium > Ausbildung" reproduzieren. Wer Abi
machen will, weiß das ohnehin schon.

### 5. Offline, kein Tracking, kein Cookie

Eine HTML-Datei. Kein Backend. Kein Analytics. Kein Cookie. Antworten
verlassen den Browser nicht. Das ist datenschutzkonform _by design_ und
ermöglicht den Einsatz in Schulen ohne IT-Genehmigung.

## Aufbau des Fragebogens

Vier Blöcke, ca. 5–8 Minuten:

1. **Umgebungs-Regler** (4 Fragen): drinnen/draußen, allein/Team,
   Routine/Wechsel, anpacken/konzentriert. Liefern ein grobes Profil.
2. **Tätigkeits-Auswahl** (6 Themengruppen): konkrete Aufgaben ankreuzen,
   die einen ansprechen würden. Liefert die Tag-Treffer.
3. **Motivations-Auswahl**: was wäre im Beruf am wichtigsten?
   Sicherheit, anderen helfen, eigene Hände, Geld, Kreativität …
4. **Ergebnis**: gerankte Vorschläge mit Begründung.

## Matching-Logik

Score pro Beruf =
`0.6 × Tag-Score + 0.25 × Umgebungs-Score + 0.15 × Motivations-Score`

- **Tag-Score:** Anteil der Beruf-Tags, die der/die Nutzer:in angekreuzt hat.
- **Umgebungs-Score:** Mittlere Abweichung der Regler-Werte vom Beruf-Profil.
- **Motivations-Score:** Überlapp zwischen gewählten Motivationen und
  Beruf-Kategorien.

**Schwelle:** Berufe mit weniger als 2 passenden Tags _und_ Score < 0,25
fallen raus. Lieber 5 ehrliche Vorschläge als 10 hingebogene.

**Diversifizierung:** Maximal 2 Vorschläge pro Hauptkategorie. Wenn ein
neuer Vorschlag mehr als 60 % Tag-Überlapp mit einem schon gewählten hat,
fällt er raus. Das verhindert „4× Tiefbau im Ergebnis".

## Seltenheit

Jeder Beruf ist als `haeufig | regional | selten` klassifiziert. Seltene
Berufe (Orgelbauer, Geigenbauer, Glasmacher …) erscheinen ganz normal im
Ergebnis, werden aber als `selten` markiert — mit Hinweis, dass die
Ausbildungsplatz-Suche hier ungewöhnlich ist und besser über den Großen
Pfadfinder oder die Arbeitsagentur erfolgt.

## Was das Tool _nicht_ tut

- **Keine Region/Postleitzahlen-Suche.** Das ist Aufgabe des Großen
  Pfadfinders mit Backend.
- **Keine Notenabfrage, kein Eignungstest.** Wir messen Interesse, nicht
  Fähigkeit.
- **Keine Empfehlung „du _musst_ X werden".** Wir liefern ein Spektrum
  zum Weiter-Recherchieren.
- **Keine Werbung, kein Sponsoring, keine Verlinkung zu Stellenbörsen.**
  Einziger Außen-Link: BERUFENET der Bundesagentur (öffentliche Daten).
