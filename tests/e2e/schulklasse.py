"""24 simulierte Schüler:innen durchlaufen den Fragebogen parallel.

Acht Persona-Archetypen × 3 Varianten. Die Varianz entsteht durch
probabilistisches Ankreuzen: jeder Tag der Persona wird mit hoher
Wahrscheinlichkeit angehakt, andere mit kleiner Basis-Wahrscheinlichkeit.
Ergebnis: Markdown-Report unter tests/e2e/schulklasse_report.md.
"""
import asyncio
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from playwright.async_api import async_playwright, Page

ROOT = Path(__file__).resolve().parents[2]
INDEX_URL = (ROOT / "index.html").as_uri()
REPORT = Path(__file__).parent / "schulklasse_report.md"

BASIS_WAHRSCHEINLICHKEIT = 0.05  # Tags außerhalb der Persona


@dataclass
class Persona:
    name: str
    regler: dict  # id → 0/25/50/75/100
    tags: set     # Kern-Tags der Persona
    motivation: list  # bis zu 3 motivation-ids
    kern_wahrscheinlichkeit: float = 0.8


PERSONAS = [
    Persona(
        name="Techie",
        regler={"drinnen_draussen": 0, "allein_team": 25, "routine_wechsel": 75, "anpacken_konzentriert": 100},
        tags={"code_schreiben", "datenbank_auswerten", "app_website_gestalten", "ki_datenanalyse",
              "netzwerk_einrichten", "computer_reparieren", "elektronik_loeten"},
        motivation=["neues_lernen", "gut_verdienen", "eigenstaendig"],
    ),
    Persona(
        name="Sozial-Medizin",
        regler={"drinnen_draussen": 0, "allein_team": 100, "routine_wechsel": 50, "anpacken_konzentriert": 25},
        tags={"wunde_versorgen", "patient_untersuchen", "senior_pflegen", "kind_medizinisch_betreuen",
              "medikament_verabreichen", "mensch_beraten_begleiten", "kind_betreuen_erziehen", "therapie_anleiten"},
        motivation=["anderen_helfen", "verantwortung", "sicherheit"],
    ),
    Persona(
        name="Kreativ-Design",
        regler={"drinnen_draussen": 25, "allein_team": 25, "routine_wechsel": 75, "anpacken_konzentriert": 50},
        tags={"zeichnen_illustrieren", "grafik_am_computer_gestalten", "foto_video_aufnehmen",
              "raum_innen_gestalten", "mode_entwerfen", "produkt_entwerfen", "text_schreiben_redigieren"},
        motivation=["sichtbares_schaffen", "eigenstaendig", "neues_lernen"],
    ),
    Persona(
        name="Handwerk-Bau",
        regler={"drinnen_draussen": 75, "allein_team": 75, "routine_wechsel": 50, "anpacken_konzentriert": 0},
        tags={"holz_bearbeiten", "metall_bearbeiten", "mauer_errichten", "fliesen_setzen",
              "schweissen_loeten", "rohr_verlegen", "dach_decken"},
        motivation=["mit_haenden", "sichtbares_schaffen", "sicherheit"],
    ),
    Persona(
        name="Natur-Outdoor",
        regler={"drinnen_draussen": 100, "allein_team": 50, "routine_wechsel": 50, "anpacken_konzentriert": 25},
        tags={"pflanze_bestimmen_pflegen", "garten_anlegen", "wald_bewirtschaften",
              "tier_versorgen_fuettern", "tier_trainieren", "boden_wasser_untersuchen", "ernte_verarbeiten"},
        motivation=["eigenstaendig", "mit_haenden", "neues_lernen"],
    ),
    Persona(
        name="Kaufmännisch",
        regler={"drinnen_draussen": 0, "allein_team": 75, "routine_wechsel": 25, "anpacken_konzentriert": 100},
        tags={"zahlen_buchhaltung", "tabelle_auswerten", "kunde_beraten_verkaufen",
              "projekt_planen_organisieren", "einkauf_handel", "personal_verwalten", "vertrag_aufsetzen"},
        motivation=["sicherheit", "gut_verdienen", "verantwortung"],
    ),
    Persona(
        name="Gastro-Lebensmittel",
        regler={"drinnen_draussen": 25, "allein_team": 75, "routine_wechsel": 75, "anpacken_konzentriert": 0},
        tags={"speise_zubereiten", "lebensmittel_herstellen", "gast_bedienen", "getraenk_mixen_servieren"},
        motivation=["mit_haenden", "sichtbares_schaffen", "anderen_helfen"],
    ),
    Persona(
        name="Technik-Mechanik",
        regler={"drinnen_draussen": 50, "allein_team": 50, "routine_wechsel": 50, "anpacken_konzentriert": 25},
        tags={"maschine_bedienen", "maschine_warten_reparieren", "motor_diagnostizieren",
              "fahrzeug_reparieren", "hydraulik_pneumatik", "schweissen_loeten"},
        motivation=["mit_haenden", "gut_verdienen", "sicherheit"],
    ),
]


@dataclass
class Ergebnis:
    persona: str
    seed: int
    berufe: list = field(default_factory=list)  # [(name, prozent, ist_top)]
    anzahl_selten: int = 0


async def setze_regler(page: Page, wert: int) -> None:
    # Range-Inputs reagieren verlässlich nur auf Tastatur / gezieltes Setzen
    slider = page.locator("#regler-input")
    await slider.evaluate(
        "(el, w) => { el.value = w; el.dispatchEvent(new Event('input', {bubbles:true})); }",
        wert,
    )


async def haken_setzen(page: Page, selektor: str, wkt_fn) -> None:
    boxen = page.locator(selektor)
    anzahl = await boxen.count()
    for i in range(anzahl):
        el = boxen.nth(i)
        tag = await el.get_attribute("data-tag") or await el.get_attribute("data-motivation")
        if random.random() < wkt_fn(tag):
            await el.check()


async def laufe_schueler(browser, persona: Persona, seed: int) -> Ergebnis:
    random.seed(seed)
    ctx = await browser.new_context(viewport={"width": 1200, "height": 900})
    page = await ctx.new_page()
    await page.goto(INDEX_URL)
    await page.locator("#btn-start").click()

    for rid in ["drinnen_draussen", "allein_team", "routine_wechsel", "anpacken_konzentriert"]:
        await setze_regler(page, persona.regler[rid])
        await page.locator("#btn-weiter").click()

    for _ in range(6):
        await haken_setzen(
            page, "input[data-tag]",
            lambda t: persona.kern_wahrscheinlichkeit if t in persona.tags else BASIS_WAHRSCHEINLICHKEIT,
        )
        await page.locator("#btn-weiter").click()

    # Motivation: nur aus Persona-Set, max 3
    gewuenscht = random.sample(persona.motivation, k=min(3, len(persona.motivation)))
    for mid in gewuenscht:
        await page.locator(f'input[data-motivation="{mid}"]').check()
    await page.locator("#btn-weiter").click()

    await page.wait_for_selector(".ergebnis-karte")
    karten = page.locator(".ergebnis-karte")
    n = await karten.count()
    erg = Ergebnis(persona=persona.name, seed=seed)
    for i in range(n):
        k = karten.nth(i)
        name = (await k.locator("h3").inner_text()).replace("selten", "").strip()
        prozent_txt = await k.locator(".match-prozent").inner_text()
        prozent = int(prozent_txt.rstrip("%").strip())
        ist_top = "top" in (await k.get_attribute("class") or "")
        erg.berufe.append((name, prozent, ist_top))
        if await k.locator(".selten-badge").count() > 0:
            erg.anzahl_selten += 1
    await ctx.close()
    return erg


async def run() -> list:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        aufgaben = []
        for idx, persona in enumerate(PERSONAS):
            for variante in range(3):
                seed = idx * 100 + variante
                aufgaben.append(laufe_schueler(browser, persona, seed))
        ergebnisse = await asyncio.gather(*aufgaben)
        await browser.close()
        return ergebnisse


def report(ergebnisse: list) -> str:
    zeilen = ["# Schulklassen-Simulation — 24 Schüler:innen\n"]
    zeilen.append(f"**Personas:** {len(PERSONAS)} × 3 Varianten = {len(ergebnisse)} Läufe\n")

    # Gesamt-Häufigkeit in Top-3
    top3_zaehler = Counter()
    alle_zaehler = Counter()
    scores_top1 = []
    anzahl_vorschlaege = []
    selten_gesamt = 0
    for e in ergebnisse:
        anzahl_vorschlaege.append(len(e.berufe))
        selten_gesamt += e.anzahl_selten
        if e.berufe:
            scores_top1.append(e.berufe[0][1])
        for i, (name, _, _) in enumerate(e.berufe):
            alle_zaehler[name] += 1
            if i < 3:
                top3_zaehler[name] += 1

    zeilen.append("## Übersicht\n")
    zeilen.append(f"- Anzahl Vorschläge pro Schüler:in: min={min(anzahl_vorschlaege)}, "
                  f"max={max(anzahl_vorschlaege)}, Ø={sum(anzahl_vorschlaege)/len(anzahl_vorschlaege):.1f}")
    zeilen.append(f"- Top-1 Match-Score: min={min(scores_top1)}%, max={max(scores_top1)}%, "
                  f"Ø={sum(scores_top1)/len(scores_top1):.1f}%")
    zeilen.append(f"- Schüler:innen mit <5 Vorschlägen: {sum(1 for n in anzahl_vorschlaege if n < 5)}")
    zeilen.append(f"- selten-Badges insgesamt angezeigt: {selten_gesamt}\n")

    zeilen.append("## Top-10 häufigste Berufe in Top-3 (über alle Schüler:innen)\n")
    zeilen.append("| Beruf | Treffer in Top-3 |")
    zeilen.append("|---|---|")
    for name, anz in top3_zaehler.most_common(10):
        zeilen.append(f"| {name} | {anz} |")
    zeilen.append("")

    zeilen.append("## Trennschärfe: Top-3 pro Persona\n")
    per_persona = defaultdict(list)
    for e in ergebnisse:
        per_persona[e.persona].append(e)
    for persona_name, laeufe in per_persona.items():
        zeilen.append(f"### {persona_name}")
        for e in laeufe:
            top3 = e.berufe[:3]
            beschr = ", ".join(f"{n} ({p}%)" for n, p, _ in top3)
            zeilen.append(f"- Seed {e.seed}: {beschr}")
        # Schnittmenge Top-3 über die 3 Varianten:
        mengen = [set(n for n, _, _ in e.berufe[:3]) for e in laeufe]
        schnitt = set.intersection(*mengen) if mengen else set()
        zeilen.append(f"- **Schnittmenge (3/3 Varianten):** {', '.join(schnitt) or '—'}\n")

    # Top-10-Schnittmenge pro Persona: diagnostiziert, ob Ranking-Rotation
    # nur Platz 1-3 betrifft (Spektrum stabil) oder auch das Gesamtbild zerfällt.
    zeilen.append("## Top-10-Stabilität pro Persona\n")
    zeilen.append("| Persona | Top-3 Schnitt (von 3) | Top-10 Schnitt (von 10) |")
    zeilen.append("|---|---|---|")
    for persona_name, laeufe in per_persona.items():
        top3_mengen = [set(n for n, _, _ in e.berufe[:3]) for e in laeufe]
        top10_mengen = [set(n for n, _, _ in e.berufe[:10]) for e in laeufe]
        schnitt3 = len(set.intersection(*top3_mengen)) if top3_mengen else 0
        schnitt10 = len(set.intersection(*top10_mengen)) if top10_mengen else 0
        zeilen.append(f"| {persona_name} | {schnitt3}/3 | {schnitt10}/10 |")
    zeilen.append("")

    # Kreuzvergleich: taucht ein Beruf bei MEHREREN Personas in Top-3 auf?
    zeilen.append("## Persona-Trennschärfe: Berufe die bei mehreren Personas in Top-3 landen\n")
    beruf_zu_personas = defaultdict(set)
    for e in ergebnisse:
        for name, _, _ in e.berufe[:3]:
            beruf_zu_personas[name].add(e.persona)
    mehrfach = [(b, sorted(ps)) for b, ps in beruf_zu_personas.items() if len(ps) >= 2]
    mehrfach.sort(key=lambda x: -len(x[1]))
    if not mehrfach:
        zeilen.append("Keine Überschneidungen — Matching trennt Personas perfekt.\n")
    else:
        zeilen.append("| Beruf | Anzahl Personas | Personas |")
        zeilen.append("|---|---|---|")
        for name, ps in mehrfach[:15]:
            zeilen.append(f"| {name} | {len(ps)} | {', '.join(ps)} |")
    return "\n".join(zeilen) + "\n"


def main():
    ergebnisse = asyncio.run(run())
    md = report(ergebnisse)
    REPORT.write_text(md, encoding="utf-8")
    print(f"OK — {len(ergebnisse)} Schüler:innen simuliert. Report: {REPORT}")


if __name__ == "__main__":
    main()
