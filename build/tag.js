#!/usr/bin/env node
/**
 * tag.js — Tagging-Skript fuer KleinerPfadfinder
 *
 * Liest build/berufe_roh.json, ruft Claude Sonnet 4.6 fuer jeden Beruf auf,
 * und schreibt getaggte Berufe nach build/berufe.json.
 *
 * Verwendet Prompt-Caching fuer das Tag-Vokabular (grosser, wiederverwendbarer
 * Systemprompt), Batching von 10 parallelen Requests und inkrementelles
 * Speichern nach jedem Batch.
 *
 * Aufruf: node build/tag.js
 * Voraussetzungen: .env mit ANTHROPIC_API_KEY, npm install @anthropic-ai/sdk
 */

'use strict';

const fs = require('fs');
const path = require('path');
const Anthropic = require('@anthropic-ai/sdk');

// ---------- Konfiguration ----------

const MODEL = 'claude-sonnet-4-5-20250929';
const BATCH_SIZE = 10;
const MAX_TOKENS = 1024;
const INPUT_FILE = path.join(__dirname, 'berufe_roh.json');
const OUTPUT_FILE = path.join(__dirname, 'berufe.json');

// ---------- Tag-Vokabular (VERBINDLICH, spiegelt KLEINER_PFADFINDER_PROMPT.md §5) ----------

const TAG_VOKABULAR = {
  version: '1.0.0',
  kategorien: {
    handwerk_material: {
      label: 'Handwerk & Material',
      tags: ['holz_bearbeiten', 'metall_bearbeiten', 'stoff_verarbeiten',
             'stein_keramik_formen', 'glas_bearbeiten', 'schmuck_fertigen',
             'praezisionsarbeit_hand']
    },
    technik_maschinen: {
      label: 'Technik & Maschinen',
      tags: ['maschine_bedienen', 'maschine_warten_reparieren',
             'motor_diagnostizieren', 'fahrzeug_reparieren',
             'hydraulik_pneumatik', 'schweissen_loeten']
    },
    elektronik_it: {
      label: 'Elektronik & IT',
      tags: ['stromkreis_verdrahten', 'elektronik_loeten',
             'computer_reparieren', 'netzwerk_einrichten',
             'code_schreiben', 'datenbank_auswerten',
             'app_website_gestalten', 'ki_datenanalyse']
    },
    medizin_pflege: {
      label: 'Medizin & Pflege',
      tags: ['wunde_versorgen', 'patient_untersuchen',
             'medikament_verabreichen', 'senior_pflegen',
             'kind_medizinisch_betreuen', 'therapie_anleiten',
             'zahn_behandeln']
    },
    labor_naturwissenschaft: {
      label: 'Labor & Naturwissenschaft',
      tags: ['mikroskop_bedienen', 'probe_analysieren',
             'experiment_durchfuehren', 'messdaten_dokumentieren',
             'chemikalie_mischen']
    },
    bau_architektur: {
      label: 'Bau & Architektur',
      tags: ['mauer_errichten', 'dach_decken', 'rohr_verlegen',
             'fliesen_setzen', 'gebaeude_planen_zeichnen',
             'vermessen_im_gelaende']
    },
    natur_umwelt: {
      label: 'Natur & Umwelt',
      tags: ['pflanze_bestimmen_pflegen', 'boden_wasser_untersuchen',
             'wald_bewirtschaften', 'garten_anlegen', 'ernte_verarbeiten']
    },
    tiere: {
      label: 'Tiere',
      tags: ['tier_untersuchen_behandeln', 'tier_versorgen_fuettern',
             'tier_trainieren', 'zuchttier_beurteilen']
    },
    gestaltung_design: {
      label: 'Gestaltung & Design',
      tags: ['zeichnen_illustrieren', 'grafik_am_computer_gestalten',
             'foto_video_aufnehmen', 'raum_innen_gestalten',
             'mode_entwerfen', 'produkt_entwerfen']
    },
    sprache_kommunikation: {
      label: 'Sprache & Kommunikation',
      tags: ['text_schreiben_redigieren', 'uebersetzen_dolmetschen',
             'moderieren_praesentieren', 'recherche_journalistisch']
    },
    bildung_soziales: {
      label: 'Bildung & Soziales',
      tags: ['unterricht_halten_erklaeren', 'kind_betreuen_erziehen',
             'mensch_beraten_begleiten', 'gruppe_anleiten',
             'konflikt_vermitteln']
    },
    wirtschaft_verwaltung: {
      label: 'Wirtschaft & Verwaltung',
      tags: ['zahlen_buchhaltung', 'tabelle_auswerten',
             'kunde_beraten_verkaufen', 'projekt_planen_organisieren',
             'personal_verwalten', 'einkauf_handel']
    },
    recht_sicherheit: {
      label: 'Recht & Sicherheit',
      tags: ['gesetz_recherchieren_anwenden', 'vertrag_aufsetzen',
             'ordnung_sicherheit_durchsetzen', 'ermitteln_untersuchen']
    },
    gastronomie_lebensmittel: {
      label: 'Gastronomie & Lebensmittel',
      tags: ['speise_zubereiten', 'lebensmittel_herstellen',
             'gast_bedienen', 'getraenk_mixen_servieren']
    },
    verkehr_logistik: {
      label: 'Verkehr & Logistik',
      tags: ['fahrzeug_fuehren', 'route_planen_navigieren',
             'waren_verladen_lagern', 'flugzeug_schiff_fuehren']
    }
  }
};

const ALLE_TAGS = new Set();
const ALLE_KATEGORIEN = new Set(Object.keys(TAG_VOKABULAR.kategorien));
for (const kat of Object.values(TAG_VOKABULAR.kategorien)) {
  for (const t of kat.tags) ALLE_TAGS.add(t);
}

// ---------- System-Prompt (wird gecacht) ----------

const SYSTEM_PROMPT = `Du taggst einen Ausbildungsberuf fuer ein Berufsorientierungs-Tool.

REGELN:
- Verwende ausschliesslich Tags und Kategorien aus dem unten angefuehrten Vokabular.
- Erfinde keine neuen Tags.
- Vergib pro Beruf 3 bis 6 Tags, die CHARAKTERISTISCH sind (nicht nur peripher zutreffend).
- Vergib 1 bis 3 Oberkategorien.
- Schaetze vier Umgebungs-Werte auf einer Skala von 0 bis 100:
    drinnen_draussen: 0 = komplett drinnen, 100 = komplett draussen
    allein_team: 0 = komplett allein, 100 = komplett im Team
    routine_wechsel: 0 = ruhige Routine, 100 = staendiger Wechsel
    anpacken_konzentriert: 0 = koerperlich anpackend, 100 = still konzentriert
- Wenn die Beschreibung unklar ist oder der Beruf nicht in das Tag-Vokabular passt: setze needs_review auf true.
- Antworte AUSSCHLIESSLICH mit gueltigem JSON. Keine Prosa, keine Markdown-Codebloecke, keine Erklaerungen drumherum.

FORMAT:
{
  "id": "<id aus Input>",
  "name": "<name aus Input>",
  "kategorien": ["<kategorie1>", ...],
  "tags": ["<tag1>", ...],
  "umgebung": {
    "drinnen_draussen": <0-100>,
    "allein_team": <0-100>,
    "routine_wechsel": <0-100>,
    "anpacken_konzentriert": <0-100>
  },
  "dauer_jahre": <aus Input>,
  "needs_review": <true|false>
}

TAG-VOKABULAR:
${JSON.stringify(TAG_VOKABULAR, null, 2)}`;

// ---------- Hilfsfunktionen ----------

function ladeEnv() {
  const envPath = path.join(__dirname, '..', '.env');
  if (!fs.existsSync(envPath)) {
    console.error('FEHLER: .env nicht gefunden:', envPath);
    process.exit(1);
  }
  const content = fs.readFileSync(envPath, 'utf8');
  for (const line of content.split(/\r?\n/)) {
    const m = line.match(/^([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$/);
    if (m) process.env[m[1]] = m[2].trim();
  }
  if (!process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_API_KEY.includes('DEIN_NEUER_KEY')) {
    console.error('FEHLER: ANTHROPIC_API_KEY nicht gesetzt oder noch Platzhalter.');
    process.exit(1);
  }
}

function ladeExistierendeTags() {
  if (!fs.existsSync(OUTPUT_FILE)) return new Map();
  try {
    const existing = JSON.parse(fs.readFileSync(OUTPUT_FILE, 'utf8'));
    return new Map(existing.map(b => [b.id, b]));
  } catch (e) {
    console.warn('Konnte berufe.json nicht lesen, starte von vorn:', e.message);
    return new Map();
  }
}

function speichereZwischenstand(berufeMap) {
  const arr = Array.from(berufeMap.values());
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(arr, null, 2), 'utf8');
}

function validiereAntwort(parsed, roh) {
  const errors = [];
  if (parsed.id !== roh.id) errors.push(`id stimmt nicht: ${parsed.id} vs ${roh.id}`);
  if (!Array.isArray(parsed.tags) || parsed.tags.length < 3 || parsed.tags.length > 6) {
    errors.push(`tags muss Array mit 3-6 Eintraegen sein (hat ${parsed.tags?.length})`);
  }
  if (!Array.isArray(parsed.kategorien) || parsed.kategorien.length < 1 || parsed.kategorien.length > 3) {
    errors.push(`kategorien muss Array mit 1-3 Eintraegen sein`);
  }
  const unbekannteTags = (parsed.tags || []).filter(t => !ALLE_TAGS.has(t));
  if (unbekannteTags.length) errors.push(`unbekannte Tags: ${unbekannteTags.join(', ')}`);
  const unbekannteKat = (parsed.kategorien || []).filter(k => !ALLE_KATEGORIEN.has(k));
  if (unbekannteKat.length) errors.push(`unbekannte Kategorien: ${unbekannteKat.join(', ')}`);
  const u = parsed.umgebung || {};
  for (const k of ['drinnen_draussen', 'allein_team', 'routine_wechsel', 'anpacken_konzentriert']) {
    if (typeof u[k] !== 'number' || u[k] < 0 || u[k] > 100) {
      errors.push(`umgebung.${k} muss Zahl 0-100 sein (ist ${u[k]})`);
    }
  }
  return errors;
}

async function taggeEinzelBeruf(client, roh) {
  const userMessage = `Berufs-Input:
${JSON.stringify({
  id: roh.id,
  name: roh.name,
  beschreibung: roh.beschreibung,
  dauer_jahre: roh.dauer_jahre,
  ausbildungsart: roh.ausbildungsart
}, null, 2)}`;

  const response = await client.messages.create({
    model: MODEL,
    max_tokens: MAX_TOKENS,
    system: [
      {
        type: 'text',
        text: SYSTEM_PROMPT,
        cache_control: { type: 'ephemeral' }
      }
    ],
    messages: [{ role: 'user', content: userMessage }]
  });

  const text = response.content.map(c => c.text || '').join('').trim();
  let parsed;
  try {
    const cleaned = text.replace(/^```json\s*/i, '').replace(/\s*```$/i, '').trim();
    parsed = JSON.parse(cleaned);
  } catch (e) {
    throw new Error(`JSON-Parse-Fehler fuer ${roh.id}: ${e.message}\nAntwort: ${text.slice(0, 500)}`);
  }

  const errors = validiereAntwort(parsed, roh);
  if (errors.length) {
    console.warn(`  ⚠  ${roh.id}: ${errors.join('; ')} — markiere needs_review`);
    parsed.needs_review = true;
  }

  return parsed;
}

async function taggeBatch(client, batch, bereitsGetaggt) {
  const promises = batch.map(async (roh) => {
    try {
      const result = await taggeEinzelBeruf(client, roh);
      bereitsGetaggt.set(roh.id, result);
      return { id: roh.id, ok: true };
    } catch (e) {
      console.error(`  ✗ ${roh.id}: ${e.message}`);
      return { id: roh.id, ok: false, error: e.message };
    }
  });
  return Promise.all(promises);
}

// ---------- Hauptablauf ----------

async function main() {
  ladeEnv();
  const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

  const berufeRoh = JSON.parse(fs.readFileSync(INPUT_FILE, 'utf8'));
  const bereitsGetaggt = ladeExistierendeTags();

  const todo = berufeRoh.filter(b => !bereitsGetaggt.has(b.id));
  console.log(`Input: ${berufeRoh.length} Berufe, bereits getaggt: ${bereitsGetaggt.size}, offen: ${todo.length}`);

  if (todo.length === 0) {
    console.log('Nichts zu tun.');
    return;
  }

  const start = Date.now();
  for (let i = 0; i < todo.length; i += BATCH_SIZE) {
    const batch = todo.slice(i, i + BATCH_SIZE);
    const batchNr = Math.floor(i / BATCH_SIZE) + 1;
    const totalBatches = Math.ceil(todo.length / BATCH_SIZE);
    console.log(`\nBatch ${batchNr}/${totalBatches} (${batch.length} Berufe)...`);
    const results = await taggeBatch(client, batch, bereitsGetaggt);
    const ok = results.filter(r => r.ok).length;
    console.log(`  ${ok}/${results.length} erfolgreich`);
    speichereZwischenstand(bereitsGetaggt);
  }

  const dauerSek = Math.round((Date.now() - start) / 1000);
  const alle = Array.from(bereitsGetaggt.values());
  const review = alle.filter(b => b.needs_review).length;
  const tagVerteilung = {};
  for (const b of alle) for (const t of b.tags) tagVerteilung[t] = (tagVerteilung[t] || 0) + 1;
  const nichtBenutzt = Array.from(ALLE_TAGS).filter(t => !tagVerteilung[t]);

  console.log('\n=== FERTIG ===');
  console.log(`Getaggt: ${alle.length} / ${berufeRoh.length}`);
  console.log(`needs_review: ${review}`);
  console.log(`Dauer: ${dauerSek} s`);
  console.log(`Nicht benutzte Tags (${nichtBenutzt.length}): ${nichtBenutzt.join(', ') || '(alle benutzt)'}`);
}

main().catch(e => {
  console.error('\nFATAL:', e);
  process.exit(1);
});
