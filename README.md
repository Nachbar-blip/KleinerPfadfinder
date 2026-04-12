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
index.html              # Das Produkt
build/
  tag.js                # Einmaliges Tagging-Skript (Node + Anthropic API)
  berufe_roh.json       # Rohe Berufsliste
  berufe.json           # Getaggte Berufsliste (Output von tag.js)
docs/
  didaktik.md           # Warum der Fragebogen so aufgebaut ist
```

## Tagging neu laufen lassen

Nur nötig, wenn sich die Berufsliste ändert:

```bash
cp .env.example .env
# ANTHROPIC_API_KEY in .env eintragen
npm install @anthropic-ai/sdk
node build/tag.js
```

Kosten: ~3–5 € pro kompletter Lauf.
