"""50 simulierte Schüler:innen: 32 reine Personas + 18 gemischte Profile.

Gemischte Profile = 2 zufällig kombinierte Personas mit gemittelten Reglern,
Tags-Union bei reduzierter Wahrscheinlichkeit. Realistischer: echte Jugendliche
sind selten reine Archetypen.
Report: tests/e2e/schulklasse50_report.md
"""
import asyncio
import random
from collections import Counter, defaultdict
from pathlib import Path

from playwright.async_api import async_playwright

from schulklasse import (
    PERSONAS, Persona, Ergebnis, laufe_schueler, INDEX_URL,
)

REPORT = Path(__file__).parent / "schulklasse50_report.md"
ANZAHL_REIN = 32   # 4 pro Persona
ANZAHL_MIX = 18


def baue_mix(p1: Persona, p2: Persona, seed: int) -> Persona:
    rng = random.Random(seed)
    # Tags: Union beider Sets, reduzierte Kern-Wahrscheinlichkeit
    tags = p1.tags | p2.tags
    regler = {k: (p1.regler[k] + p2.regler[k]) // 2 for k in p1.regler}
    # Regler leicht verrauschen (±25, snap auf 0/25/50/75/100)
    for k in regler:
        regler[k] = max(0, min(100, 25 * round((regler[k] + rng.choice([-25, 0, 0, 25])) / 25)))
    motivation = list({*p1.motivation, *p2.motivation})
    rng.shuffle(motivation)
    return Persona(
        name=f"Mix:{p1.name}+{p2.name}",
        regler=regler,
        tags=tags,
        motivation=motivation[:3],
        kern_wahrscheinlichkeit=0.5,  # mehr Streuung als bei reinen Personas
    )


def baue_klasse() -> list:
    schueler = []
    for idx, persona in enumerate(PERSONAS):
        for variante in range(ANZAHL_REIN // len(PERSONAS)):
            schueler.append((persona, 10_000 + idx * 100 + variante))
    rng = random.Random(42)
    for i in range(ANZAHL_MIX):
        p1, p2 = rng.sample(PERSONAS, 2)
        schueler.append((baue_mix(p1, p2, 20_000 + i), 20_000 + i))
    return schueler


async def run() -> list:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        aufgaben = [laufe_schueler(browser, persona, seed) for persona, seed in baue_klasse()]
        ergebnisse = await asyncio.gather(*aufgaben)
        await browser.close()
        return ergebnisse


def report(ergebnisse: list) -> str:
    rein = [e for e in ergebnisse if not e.persona.startswith("Mix:")]
    mix = [e for e in ergebnisse if e.persona.startswith("Mix:")]

    zeilen = ["# Schulklassen-Simulation XL — 50 Schüler:innen\n"]
    zeilen.append(f"**Reine Personas:** {len(rein)} · **Gemischte Profile:** {len(mix)}\n")

    def uebersicht(titel: str, gruppe: list) -> list:
        if not gruppe:
            return []
        scores = [e.berufe[0][1] for e in gruppe if e.berufe]
        anz = [len(e.berufe) for e in gruppe]
        unter5 = sum(1 for n in anz if n < 5)
        return [
            f"### {titel}",
            f"- Vorschläge: min={min(anz)}, max={max(anz)}, Ø={sum(anz)/len(anz):.1f}",
            f"- Top-1 Score: min={min(scores)}%, max={max(scores)}%, Ø={sum(scores)/len(scores):.1f}%",
            f"- Schüler:innen mit <5 Vorschlägen: {unter5}",
            "",
        ]

    zeilen.append("## Übersicht\n")
    zeilen.extend(uebersicht("Reine Personas", rein))
    zeilen.extend(uebersicht("Gemischte Profile", mix))

    # Score-Histogramm Top-1 (Buckets von 10%) — beide Gruppen gegenübergestellt
    zeilen.append("## Top-1-Score-Verteilung (Histogramm)\n")
    zeilen.append("| Bucket | Rein | Mix |")
    zeilen.append("|---|---|---|")
    buckets = list(range(0, 101, 10))
    for untere in buckets[:-1]:
        obere = untere + 10
        r = sum(1 for e in rein if e.berufe and untere <= e.berufe[0][1] < obere)
        m = sum(1 for e in mix if e.berufe and untere <= e.berufe[0][1] < obere)
        if r or m:
            zeilen.append(f"| {untere}–{obere-1}% | {r} | {m} |")
    # 100% separat (Bucket-Obergrenze inklusiv)
    r100 = sum(1 for e in rein if e.berufe and e.berufe[0][1] == 100)
    m100 = sum(1 for e in mix if e.berufe and e.berufe[0][1] == 100)
    zeilen.append(f"| exakt 100% | {r100} | {m100} |")
    zeilen.append("")

    zeilen.append("## Top-10 häufigste Berufe in Top-3 (alle 50)\n")
    top3_z = Counter()
    for e in ergebnisse:
        for n, _, _ in e.berufe[:3]:
            top3_z[n] += 1
    zeilen.append("| Beruf | Treffer |")
    zeilen.append("|---|---|")
    for n, anz in top3_z.most_common(10):
        zeilen.append(f"| {n} | {anz} |")
    zeilen.append("")

    # Stabilität pro reiner Persona: Top-3 und Top-10 Schnittmenge
    zeilen.append("## Stabilität reiner Personas (4 Varianten je Persona)\n")
    zeilen.append("| Persona | Top-3 Schnitt | Top-10 Schnitt |")
    zeilen.append("|---|---|---|")
    per_pers = defaultdict(list)
    for e in rein:
        per_pers[e.persona].append(e)
    for name, laeufe in per_pers.items():
        t3 = [set(n for n, _, _ in e.berufe[:3]) for e in laeufe]
        t10 = [set(n for n, _, _ in e.berufe[:10]) for e in laeufe]
        s3 = len(set.intersection(*t3)) if t3 else 0
        s10 = len(set.intersection(*t10)) if t10 else 0
        zeilen.append(f"| {name} | {s3}/3 | {s10}/10 |")
    zeilen.append("")

    # Gemischte Profile: was bekommen sie?
    zeilen.append("## Gemischte Profile: Top-3 je Mix-Schüler\n")
    for e in sorted(mix, key=lambda x: x.persona):
        top3 = ", ".join(f"{n} ({p}%)" for n, p, _ in e.berufe[:3])
        zeilen.append(f"- **{e.persona}** (seed {e.seed}): {top3}")
    zeilen.append("")

    # Cross-Persona Überschneidung
    zeilen.append("## Persona-Trennschärfe (nur reine Personas)\n")
    beruf_zu_personas = defaultdict(set)
    for e in rein:
        for n, _, _ in e.berufe[:3]:
            beruf_zu_personas[n].add(e.persona)
    mehrfach = sorted(
        [(b, sorted(ps)) for b, ps in beruf_zu_personas.items() if len(ps) >= 2],
        key=lambda x: -len(x[1]),
    )
    if not mehrfach:
        zeilen.append("Keine Überschneidungen.\n")
    else:
        zeilen.append("| Beruf | # Personas | Personas |")
        zeilen.append("|---|---|---|")
        for n, ps in mehrfach[:15]:
            zeilen.append(f"| {n} | {len(ps)} | {', '.join(ps)} |")
    return "\n".join(zeilen) + "\n"


def main():
    ergebnisse = asyncio.run(run())
    md = report(ergebnisse)
    REPORT.write_text(md, encoding="utf-8")
    print(f"OK - {len(ergebnisse)} Schueler:innen. Report: {REPORT}")


if __name__ == "__main__":
    main()
