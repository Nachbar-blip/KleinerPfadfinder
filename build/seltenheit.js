'use strict';
/**
 * seltenheit.js — Klassifiziert jeden Beruf als haeufig | regional | selten.
 *
 * Definition:
 *   haeufig   = in jeder Kreisstadt / jedem mittelgrossen Ort ausbildbar
 *   regional  = nur in groesseren Staedten oder Ballungsraeumen
 *   selten    = nur an wenigen Standorten deutschlandweit (unter ~20 Betriebe)
 *
 * Sendet alle Berufe in grossen Batches (30 pro Request), um API-Kosten zu sparen.
 */

const fs = require('fs');
const path = require('path');
const Anthropic = require('@anthropic-ai/sdk');

const MODEL = 'claude-sonnet-4-5-20250929';
const BATCH_SIZE = 30;
const INPUT_FILE = path.join(__dirname, 'berufe.json');
const ROH_FILE = path.join(__dirname, 'berufe_roh.json');

function ladeEnv() {
  const envPath = path.join(__dirname, '..', '.env');
  const content = fs.readFileSync(envPath, 'utf8');
  for (const line of content.split(/\r?\n/)) {
    const m = line.match(/^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$/);
    if (m) process.env[m[1]] = m[2].trim();
  }
}

const SYSTEM_PROMPT = `Du klassifizierst deutsche Ausbildungsberufe nach ihrer regionalen Verfuegbarkeit.

Kategorien:
  "haeufig"  = in jeder Kreisstadt oder jedem mittelgrossen Ort ausbildbar (z.B. Kaufmann im Einzelhandel, Tischler, Elektroniker)
  "regional" = nur in groesseren Staedten, Ballungsraeumen oder spezialisierten Industrieregionen (z.B. Chemielaborant, Mediengestalter, Fluggeraetemechaniker)
  "selten"   = nur an wenigen Standorten deutschlandweit, unter etwa 20 Ausbildungsbetriebe gesamt (z.B. Orgelbauer, Geigenbauer, Glasmacher, Bergbautechnolge)

Du bekommst eine Liste von Berufen mit id und name. Gib fuer jeden die Kategorie zurueck.

Antworte AUSSCHLIESSLICH mit einem gueltigen JSON-Array. Kein Markdown, keine Prosa. Format:
[{"id":"<id>","seltenheit":"haeufig|regional|selten"}, ...]`;

async function klassifiziereBatch(client, batch) {
  const input = batch.map(b => ({ id: b.id, name: b.name, beschreibung: b.beschreibung?.slice(0, 150) }));
  const response = await client.messages.create({
    model: MODEL,
    max_tokens: 4096,
    system: [{ type: 'text', text: SYSTEM_PROMPT, cache_control: { type: 'ephemeral' } }],
    messages: [{ role: 'user', content: `Berufe:\n${JSON.stringify(input, null, 2)}` }]
  });
  const text = response.content.map(c => c.text || '').join('').trim();
  const cleaned = text.replace(/^```json\s*/i, '').replace(/\s*```$/i, '').trim();
  return JSON.parse(cleaned);
}

async function main() {
  ladeEnv();
  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

  const berufe = JSON.parse(fs.readFileSync(INPUT_FILE, 'utf8'));
  const roh = JSON.parse(fs.readFileSync(ROH_FILE, 'utf8'));
  const rohMap = new Map(roh.map(r => [r.id, r]));

  const alleMitBeschreibung = berufe.map(b => ({
    id: b.id,
    name: b.name,
    beschreibung: rohMap.get(b.id)?.beschreibung || ''
  }));

  const seltenheitMap = new Map();
  const totalBatches = Math.ceil(alleMitBeschreibung.length / BATCH_SIZE);

  for (let i = 0; i < alleMitBeschreibung.length; i += BATCH_SIZE) {
    const batch = alleMitBeschreibung.slice(i, i + BATCH_SIZE);
    const batchNr = Math.floor(i / BATCH_SIZE) + 1;
    console.log(`Batch ${batchNr}/${totalBatches} (${batch.length} Berufe)...`);
    try {
      const result = await klassifiziereBatch(client, batch);
      for (const r of result) {
        if (r.id && ['haeufig', 'regional', 'selten'].includes(r.seltenheit)) {
          seltenheitMap.set(r.id, r.seltenheit);
        }
      }
      console.log(`  ${result.length} klassifiziert`);
    } catch (e) {
      console.error(`  Fehler: ${e.message}`);
    }
    if (i + BATCH_SIZE < alleMitBeschreibung.length) {
      await new Promise(r => setTimeout(r, 2000));
    }
  }

  let aktualisiert = 0;
  for (const b of berufe) {
    if (seltenheitMap.has(b.id)) {
      b.seltenheit = seltenheitMap.get(b.id);
      aktualisiert++;
    }
  }

  fs.writeFileSync(INPUT_FILE, JSON.stringify(berufe, null, 2), 'utf8');

  const verteilung = { haeufig: 0, regional: 0, selten: 0, fehlt: 0 };
  for (const b of berufe) verteilung[b.seltenheit || 'fehlt']++;

  console.log('\n=== FERTIG ===');
  console.log(`Aktualisiert: ${aktualisiert}/${berufe.length}`);
  console.log(`Verteilung:`, verteilung);
}

main().catch(e => { console.error('FATAL:', e); process.exit(1); });
