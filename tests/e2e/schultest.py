"""Schultest: 300 Schüler:innen mit diversen Verhaltensmustern.

Verhaltensgruppen:
- Enthusiast:    kreuzt viel an (4-6 Tätigkeiten pro Frage), alle Motivationen
- Introvert:     drinnen+allein, wenige Kreuze (0-2 pro Frage), 1 Motivation
- Unschlüssig:   Regler mittig, 0-1 Tag pro Frage, 0-1 Motivation
- Widersprüchlich: Regler sagen A, Tags kreuzen B an
- Minimalist:    0 Tags, nur Regler + 1 Motivation
- Speed-Run:     haut alles an (Stressfall, Score-Sättigung)
- Fokussiert:    reine Persona (15 × 8 Personas = 120)
- Gemischt:      Persona-Paar (Tags-Union, reduzierte Wkt.)

Ausführung in Batches (sonst Chromium-Overhead zu hoch). Report:
tests/e2e/schultest_report.md
"""
import asyncio
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from playwright.async_api import async_playwright, Page

from schulklasse import PERSONAS, Persona

ROOT = Path(__file__).resolve().parents[2]
INDEX_URL = (ROOT / "index.html").as_uri()
REPORT = Path(__file__).parent / "schultest_report.md"
BATCH_SIZE = 30


@dataclass
class SchuelerSpec:
    """Ein Schüler-Profil: Verhaltensgruppe + Generator für Antworten."""
    gruppe: str
    label: str
    seed: int
    # regler[id] -> 0..100
    regler: dict
    # Callback pro Tätigkeitsfrage: tag -> bool (ankreuzen?)
    tag_entscheider: Callable[[str, random.Random], bool]
    # Motivation-IDs die angehakt werden sollen
    motivationen: list


@dataclass
class Ergebnis:
    gruppe: str
    label: str
    seed: int
    berufe: list = field(default_factory=list)  # [(name, prozent, ist_top)]
    anzahl_selten: int = 0


# Alle verfügbaren Tags aus den Personas (für gezieltes An-/Abkreuzen)
ALLE_TAGS = set().union(*(p.tags for p in PERSONAS))
ALLE_MOTIV = ["anderen_helfen", "sichtbares_schaffen", "gut_verdienen", "sicherheit",
              "eigenstaendig", "neues_lernen", "mit_haenden", "verantwortung"]


# ---------- Verhaltensgruppen-Generatoren ----------

def spec_fokussiert(persona: Persona, seed: int) -> SchuelerSpec:
    def entscheider(tag, rng):
        return rng.random() < (0.8 if tag in persona.tags else 0.05)
    return SchuelerSpec(
        gruppe="Fokussiert",
        label=persona.name,
        seed=seed,
        regler=dict(persona.regler),
        tag_entscheider=entscheider,
        motivationen=persona.motivation[:3],
    )


def spec_gemischt(p1: Persona, p2: Persona, seed: int) -> SchuelerSpec:
    rng = random.Random(seed)
    tags = p1.tags | p2.tags
    regler = {k: (p1.regler[k] + p2.regler[k]) // 2 for k in p1.regler}
    motivation = list({*p1.motivation, *p2.motivation})
    rng.shuffle(motivation)
    def entscheider(tag, r):
        return r.random() < (0.5 if tag in tags else 0.08)
    return SchuelerSpec(
        gruppe="Gemischt",
        label=f"{p1.name}+{p2.name}",
        seed=seed,
        regler=regler,
        tag_entscheider=entscheider,
        motivationen=motivation[:3],
    )


def spec_enthusiast(seed: int) -> SchuelerSpec:
    rng = random.Random(seed)
    regler = {r: rng.choice([0, 25, 50, 75, 100]) for r in
              ["drinnen_draussen", "allein_team", "routine_wechsel", "anpacken_konzentriert"]}
    return SchuelerSpec(
        gruppe="Enthusiast",
        label="alles-interessant",
        seed=seed,
        regler=regler,
        tag_entscheider=lambda t, r: r.random() < 0.45,
        motivationen=rng.sample(ALLE_MOTIV, k=5),
    )


def spec_introvert(seed: int) -> SchuelerSpec:
    rng = random.Random(seed)
    # Introvert-Tags: Ruhe, Präzision, Allein-Arbeit
    intro_tags = {"code_schreiben", "datenbank_auswerten", "elektronik_loeten",
                  "praezisionsarbeit_hand", "text_schreiben_redigieren", "messdaten_dokumentieren",
                  "zeichnen_illustrieren", "grafik_am_computer_gestalten",
                  "zahlen_buchhaltung", "schmuck_fertigen"}
    def entscheider(tag, r):
        if tag in intro_tags:
            return r.random() < 0.35  # selektiv
        return r.random() < 0.02
    return SchuelerSpec(
        gruppe="Introvert",
        label="ruhig-allein",
        seed=seed,
        regler={"drinnen_draussen": 0, "allein_team": 0, "routine_wechsel": 25, "anpacken_konzentriert": 100},
        tag_entscheider=entscheider,
        motivationen=rng.sample(["eigenstaendig", "neues_lernen", "sichtbares_schaffen"], k=1),
    )


def spec_unschluessig(seed: int) -> SchuelerSpec:
    rng = random.Random(seed)
    return SchuelerSpec(
        gruppe="Unschlüssig",
        label="alles-50-wenig-ahnung",
        seed=seed,
        regler={r: 50 for r in
                ["drinnen_draussen", "allein_team", "routine_wechsel", "anpacken_konzentriert"]},
        tag_entscheider=lambda t, r: r.random() < 0.08,
        motivationen=rng.sample(ALLE_MOTIV, k=rng.randint(0, 1)),
    )


def spec_widerspruechlich(seed: int) -> SchuelerSpec:
    """Regler sagen draußen/anpacken, Tags zeigen Indoor/Kopfarbeit."""
    rng = random.Random(seed)
    kopf_tags = {"code_schreiben", "datenbank_auswerten", "ki_datenanalyse",
                 "zahlen_buchhaltung", "text_schreiben_redigieren", "gesetz_recherchieren_anwenden",
                 "mikroskop_bedienen", "probe_analysieren"}
    def entscheider(tag, r):
        return r.random() < (0.6 if tag in kopf_tags else 0.03)
    return SchuelerSpec(
        gruppe="Widersprüchlich",
        label="draussen-regler-indoor-tags",
        seed=seed,
        regler={"drinnen_draussen": 100, "allein_team": 75, "routine_wechsel": 75, "anpacken_konzentriert": 0},
        tag_entscheider=entscheider,
        motivationen=["mit_haenden", "neues_lernen"],
    )


def spec_minimalist(seed: int) -> SchuelerSpec:
    rng = random.Random(seed)
    return SchuelerSpec(
        gruppe="Minimalist",
        label="nur-regler",
        seed=seed,
        regler={r: rng.choice([0, 50, 100]) for r in
                ["drinnen_draussen", "allein_team", "routine_wechsel", "anpacken_konzentriert"]},
        tag_entscheider=lambda t, r: False,
        motivationen=[rng.choice(ALLE_MOTIV)],
    )


def spec_speedrun(seed: int) -> SchuelerSpec:
    return SchuelerSpec(
        gruppe="Speed-Run",
        label="alles-angehakt",
        seed=seed,
        regler={"drinnen_draussen": 50, "allein_team": 50, "routine_wechsel": 50, "anpacken_konzentriert": 50},
        tag_entscheider=lambda t, r: True,
        motivationen=ALLE_MOTIV[:3],
    )


# ---------- Klasse zusammenbauen ----------

def baue_klasse() -> list:
    specs = []
    seed_cursor = 10_000

    # 120 Fokussiert: 15 × 8 Personas
    for p_idx, persona in enumerate(PERSONAS):
        for v in range(15):
            specs.append(spec_fokussiert(persona, seed_cursor))
            seed_cursor += 1

    # 60 Gemischt: alle 28 Paare + 32 zufällige Wiederholungen
    rng = random.Random(7)
    paare = [(PERSONAS[i], PERSONAS[j]) for i in range(len(PERSONAS)) for j in range(i+1, len(PERSONAS))]
    for p1, p2 in paare:
        specs.append(spec_gemischt(p1, p2, seed_cursor))
        seed_cursor += 1
    for _ in range(60 - len(paare)):
        p1, p2 = rng.sample(PERSONAS, 2)
        specs.append(spec_gemischt(p1, p2, seed_cursor))
        seed_cursor += 1

    # 35 Enthusiast, 35 Introvert, 30 Unschlüssig, 15 Widersprüchlich, 10 Minimalist, 5 Speed-Run
    for _ in range(35):
        specs.append(spec_enthusiast(seed_cursor)); seed_cursor += 1
    for _ in range(35):
        specs.append(spec_introvert(seed_cursor)); seed_cursor += 1
    for _ in range(30):
        specs.append(spec_unschluessig(seed_cursor)); seed_cursor += 1
    for _ in range(15):
        specs.append(spec_widerspruechlich(seed_cursor)); seed_cursor += 1
    for _ in range(10):
        specs.append(spec_minimalist(seed_cursor)); seed_cursor += 1
    for _ in range(5):
        specs.append(spec_speedrun(seed_cursor)); seed_cursor += 1

    return specs


# ---------- Playwright-Runner ----------

async def setze_regler(page: Page, wert: int) -> None:
    await page.locator("#regler-input").evaluate(
        "(el, w) => { el.value = w; el.dispatchEvent(new Event('input', {bubbles:true})); }",
        wert,
    )


async def haken_fuer(page: Page, selektor: str, attr: str, entscheider, rng) -> None:
    boxen = page.locator(selektor)
    anzahl = await boxen.count()
    for i in range(anzahl):
        el = boxen.nth(i)
        tag = await el.get_attribute(attr)
        if entscheider(tag, rng):
            await el.check()


async def laufe_schueler(browser, spec: SchuelerSpec) -> Ergebnis:
    rng = random.Random(spec.seed)
    ctx = await browser.new_context(viewport={"width": 1200, "height": 900})
    page = await ctx.new_page()
    try:
        await page.goto(INDEX_URL)
        await page.locator("#btn-start").click()

        for rid in ["drinnen_draussen", "allein_team", "routine_wechsel", "anpacken_konzentriert"]:
            await setze_regler(page, spec.regler[rid])
            await page.locator("#btn-weiter").click()

        for _ in range(6):
            await haken_fuer(page, "input[data-tag]", "data-tag", spec.tag_entscheider, rng)
            await page.locator("#btn-weiter").click()

        # Motivation: max 3 ankreuzen (UI erlaubt nicht mehr)
        for mid in spec.motivationen[:3]:
            loc = page.locator(f'input[data-motivation="{mid}"]')
            if await loc.count() > 0:
                await loc.check()
        await page.locator("#btn-weiter").click()

        await page.wait_for_selector(".ergebnis-karte, .ergebnis-kopf", timeout=15000)
        karten = page.locator(".ergebnis-karte")
        n = await karten.count()
        erg = Ergebnis(gruppe=spec.gruppe, label=spec.label, seed=spec.seed)
        for i in range(n):
            k = karten.nth(i)
            name_raw = await k.locator("h2").inner_text()
            name = name_raw.replace("selten", "").strip()
            if await k.locator(".match-prozent").count():
                prozent = int((await k.locator(".match-prozent").inner_text()).rstrip("%").strip())
            else:
                prozent = 0
            cls = await k.get_attribute("class") or ""
            erg.berufe.append((name, prozent, "top" in cls))
            if "selten" in name_raw or await k.locator(".selten-badge").count():
                erg.anzahl_selten += 1
        return erg
    finally:
        await ctx.close()


async def run() -> list:
    specs = baue_klasse()
    print(f"Starte {len(specs)} Schüler:innen in Batches zu {BATCH_SIZE}…")
    ergebnisse = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for i in range(0, len(specs), BATCH_SIZE):
            batch = specs[i:i+BATCH_SIZE]
            res = await asyncio.gather(*(laufe_schueler(browser, s) for s in batch))
            ergebnisse.extend(res)
            print(f"  Batch {i//BATCH_SIZE + 1}/{(len(specs)+BATCH_SIZE-1)//BATCH_SIZE} — {len(ergebnisse)}/{len(specs)}")
        await browser.close()
    return ergebnisse


# ---------- Auswertung ----------

def stats_gruppe(gruppe: list):
    if not gruppe:
        return None
    scores = [e.berufe[0][1] for e in gruppe if e.berufe]
    anz = [len(e.berufe) for e in gruppe]
    return {
        "n": len(gruppe),
        "anz_min": min(anz), "anz_max": max(anz), "anz_avg": sum(anz)/len(anz),
        "score_min": min(scores) if scores else 0,
        "score_max": max(scores) if scores else 0,
        "score_avg": sum(scores)/len(scores) if scores else 0,
        "unter5": sum(1 for n in anz if n < 5),
        "leer": sum(1 for n in anz if n == 0),
        "selten_total": sum(e.anzahl_selten for e in gruppe),
    }


def report(ergebnisse: list) -> str:
    z = ["# Schultest — 300 Schüler:innen\n"]
    z.append(f"**Gesamtzahl:** {len(ergebnisse)}\n")

    nach_gruppe = defaultdict(list)
    for e in ergebnisse:
        nach_gruppe[e.gruppe].append(e)

    z.append("## Übersicht pro Verhaltensgruppe\n")
    z.append("| Gruppe | n | Ø Vorschläge | <5 Vorschl. | 0 Vorschl. | Top-1 Ø% | Top-1 min% | selten gesamt |")
    z.append("|---|---|---|---|---|---|---|---|")
    for gruppe, liste in nach_gruppe.items():
        s = stats_gruppe(liste)
        z.append(f"| {gruppe} | {s['n']} | {s['anz_avg']:.1f} | {s['unter5']} | {s['leer']} | "
                 f"{s['score_avg']:.1f} | {s['score_min']} | {s['selten_total']} |")
    z.append("")

    # Top-1-Score-Histogramm pro Gruppe
    z.append("## Top-1-Score-Verteilung pro Gruppe\n")
    buckets = [(0, 49), (50, 69), (70, 84), (85, 94), (95, 99), (100, 100)]
    header = "| Gruppe | " + " | ".join(f"{a}-{b}%" for a, b in buckets) + " |"
    z.append(header)
    z.append("|" + "---|" * (len(buckets) + 1))
    for gruppe, liste in nach_gruppe.items():
        zeile = [gruppe]
        for a, b in buckets:
            cnt = sum(1 for e in liste if e.berufe and a <= e.berufe[0][1] <= b)
            zeile.append(str(cnt))
        z.append("| " + " | ".join(zeile) + " |")
    z.append("")

    # Top-10 Berufe pro Gruppe
    z.append("## Top-5 Berufe in Top-3 — pro Gruppe\n")
    for gruppe, liste in nach_gruppe.items():
        zaehler = Counter()
        for e in liste:
            for n, _, _ in e.berufe[:3]:
                zaehler[n] += 1
        top5 = ", ".join(f"{n} ({c})" for n, c in zaehler.most_common(5))
        z.append(f"- **{gruppe}** (n={len(liste)}): {top5}")
    z.append("")

    # Universal-Berufe: tauchen in Top-3 von >50% aller Schüler auf
    alle = len(ergebnisse)
    universal = Counter()
    for e in ergebnisse:
        for n, _, _ in e.berufe[:3]:
            universal[n] += 1
    z.append("## Häufigste Berufe über ALLE 300 (Top-15 in Top-3)\n")
    z.append("| Beruf | Treffer | % der Klasse |")
    z.append("|---|---|---|")
    for n, c in universal.most_common(15):
        z.append(f"| {n} | {c} | {100*c/alle:.1f}% |")
    z.append("")

    # Berufe die NIE empfohlen wurden (aus Datenbank? brauchen wir nicht — stattdessen:
    # wieviele unterschiedliche Berufe tauchen insgesamt auf?)
    unique_top10 = set()
    unique_top3 = set()
    for e in ergebnisse:
        for i, (n, _, _) in enumerate(e.berufe):
            unique_top10.add(n)
            if i < 3:
                unique_top3.add(n)
    z.append("## Diversität\n")
    z.append(f"- Unterschiedliche Berufe insgesamt (Top-10): **{len(unique_top10)}**")
    z.append(f"- Unterschiedliche Berufe auf Podest (Top-3): **{len(unique_top3)}**\n")

    # Fokussiert-Stabilität: Schnittmenge über 15 Varianten pro Persona
    z.append("## Stabilität fokussierter Personas (15 Varianten je)\n")
    z.append("| Persona | Top-3 Schnitt | Top-10 Schnitt | Top-3 Anteil (≥80%) |")
    z.append("|---|---|---|---|")
    fokus_pro_persona = defaultdict(list)
    for e in ergebnisse:
        if e.gruppe == "Fokussiert":
            fokus_pro_persona[e.label].append(e)
    for pname, laeufe in fokus_pro_persona.items():
        t3 = [set(n for n, _, _ in e.berufe[:3]) for e in laeufe]
        t10 = [set(n for n, _, _ in e.berufe[:10]) for e in laeufe]
        schnitt3 = len(set.intersection(*t3)) if t3 else 0
        schnitt10 = len(set.intersection(*t10)) if t10 else 0
        # "Stabile Top-3": Berufe die bei ≥80% der Läufe in Top-3 sind
        zaehler = Counter()
        for s in t3:
            for n in s:
                zaehler[n] += 1
        stabil = [n for n, c in zaehler.items() if c >= 0.8 * len(laeufe)]
        z.append(f"| {pname} | {schnitt3}/3 | {schnitt10}/10 | {', '.join(stabil) or '—'} |")
    z.append("")

    # Verhaltenseinsichten
    z.append("## Verhaltenseinsichten\n")
    min_stats = stats_gruppe(nach_gruppe.get("Minimalist", []))
    unsch_stats = stats_gruppe(nach_gruppe.get("Unschlüssig", []))
    wider_stats = stats_gruppe(nach_gruppe.get("Widersprüchlich", []))
    if min_stats:
        z.append(f"- **Minimalist** (nur Regler, 0 Tätigkeiten): {min_stats['anz_avg']:.1f} Vorschläge Ø, "
                 f"Top-1 Ø{min_stats['score_avg']:.1f}%. Bei {min_stats['leer']}/{min_stats['n']} leer.")
    if unsch_stats:
        z.append(f"- **Unschlüssig** (alles mittig, kaum Kreuze): {unsch_stats['anz_avg']:.1f} Vorschläge Ø, "
                 f"Top-1 Ø{unsch_stats['score_avg']:.1f}%.")
    if wider_stats:
        z.append(f"- **Widersprüchlich** (Regler vs. Tags uneinig): Top-1 Ø{wider_stats['score_avg']:.1f}% — "
                 f"zeigt ob das Matching Tags oder Regler höher gewichtet.")
    return "\n".join(z) + "\n"


def main():
    ergebnisse = asyncio.run(run())
    md = report(ergebnisse)
    REPORT.write_text(md, encoding="utf-8")
    print(f"OK — {len(ergebnisse)} Schueler:innen. Report: {REPORT}")


if __name__ == "__main__":
    main()
