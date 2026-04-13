# KleinerPfadfinder

Ein offline-fähiger Berufsorientierungs-Fragebogen für Schüler:innen mit
Realschulabschluss. Schlägt am Ende **10 Ausbildungsberufe** mit
Begründung vor — inklusive Nischen, die in der üblichen Berufsberatung
untergehen.

## Benutzen

`index.html` im Browser öffnen. Fertig. Die Datei enthält HTML, CSS, JS
und die Berufsdaten inline — keine Installation, keine Internetverbindung
nötig.

Per USB-Stick verteilbar. Läuft im Flugmodus.

## Leitprinzipien

- **Eine Datei:** `index.html` ist das komplette Produkt.
- **Kein Backend, keine Tracker, keine Cookies.**
- **Geschlechtsneutral:** Alle Berufe werden gleichwertig präsentiert.
- **10 Vorschläge als Spektrum,** niemals ein einzelnes „Top-Ergebnis".
- **Nur Ausbildungen** (dual + schulisch), keine Studiengänge.

## Repository-Struktur

```
index.html              # Das Produkt (Daten inline eingebettet)
build/
  berufe_roh.json       # Rohe Berufsliste (Quelldaten)
  tag.js                # Tagging via Anthropic API (Tags, Kategorien, Umgebung)
  seltenheit.js         # Klassifiziert regionale Verfügbarkeit (haeufig/regional/selten)
  fix_review.js         # Manuelle Korrekturen für needs_review-Einträge
  embed.js              # Embedet berufe.json + berufe_roh.json in index.html
  berufe.json           # Getaggte Berufsliste (gitignored, Build-Artefakt)
docs/
  didaktik.md           # Warum der Fragebogen so aufgebaut ist
```

## Tagging neu laufen lassen

Nur nötig, wenn sich `berufe_roh.json` ändert:

```bash
cp .env.example .env       # einmalig
# ANTHROPIC_API_KEY in .env eintragen
npm install                # einmalig

node build/tag.js          # Tags, Kategorien, Umgebung (~4 Min, ~3-5 €)
node build/fix_review.js   # nur falls bekannte needs_review-IDs enthalten sind
node build/seltenheit.js   # Seltenheits-Klassifikation (~2 Min, <1 €)
node build/embed.js        # baut alles in index.html ein
```

Danach `index.html` per USB-Stick verteilen — keine Internet-Verbindung mehr nötig.
