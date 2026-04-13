"""Ready-Check für echten Schüler:innen-Einsatz.

Deckt ab:
- Multi-Browser (Chromium, Firefox, WebKit/Safari)
- Mobile Viewports (iPhone SE, Pixel 5)
- Persistenz/Fortsetzen (localStorage)
- Print-Layout (PDF-Render)
- Axe-Core Accessibility-Scan
- Tastaturnavigation

Jede Prüfung läuft unabhängig. Report: tests/e2e/readyness_report.md
"""
import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from playwright.async_api import async_playwright, Browser, Page, BrowserContext

ROOT = Path(__file__).resolve().parents[2]
INDEX_URL = (ROOT / "index.html").as_uri()
REPORT = Path(__file__).parent / "readyness_report.md"
SCREEN_DIR = Path(__file__).parent / "screens"
SCREEN_DIR.mkdir(exist_ok=True)
AXE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.0/axe.min.js"

ANZAHL_FRAGEN = 11


@dataclass
class Befund:
    bereich: str
    status: str  # "ok" | "warn" | "fail"
    details: str
    artefakte: list = field(default_factory=list)


async def fragebogen_durchklicken(page: Page) -> None:
    """Geht komplett durch bis Ergebnis. Kreuzt 2 Tätigkeiten pro Frage, 2 Motivationen."""
    await page.locator("#btn-start").click()
    for _ in range(4):  # 4 Regler
        await page.locator("#btn-weiter").click()
    for _ in range(6):  # 6 Tätigkeitsfragen
        cbs = page.locator('input[data-tag]')
        n = await cbs.count()
        for i in range(min(2, n)):
            await cbs.nth(i).check()
        await page.locator("#btn-weiter").click()
    motivs = page.locator('input[data-motivation]')
    for i in range(min(2, await motivs.count())):
        await motivs.nth(i).check()
    await page.locator("#btn-weiter").click()
    await page.wait_for_selector(".ergebnis-karte", timeout=15000)


# ---------- Prüfungen ----------

async def check_browser(browser_name: str, launcher) -> Befund:
    try:
        browser = await launcher.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1200, "height": 900})
        page = await ctx.new_page()
        fehler = []
        page.on("pageerror", lambda e: fehler.append(f"JS-Error: {e}"))
        page.on("console", lambda msg: fehler.append(f"Console-Error: {msg.text}") if msg.type == "error" else None)
        await page.goto(INDEX_URL)
        await fragebogen_durchklicken(page)
        karten = await page.locator(".ergebnis-karte").count()
        await browser.close()
        if fehler:
            return Befund(f"Browser: {browser_name}", "fail",
                          f"{karten} Karten, aber {len(fehler)} Fehler: {fehler[:3]}")
        if karten < 5:
            return Befund(f"Browser: {browser_name}", "warn",
                          f"Nur {karten} Ergebniskarten (erwartet ≥5)")
        return Befund(f"Browser: {browser_name}", "ok",
                      f"{karten} Ergebniskarten, keine JS-Fehler")
    except Exception as e:
        return Befund(f"Browser: {browser_name}", "fail", f"Ausnahme: {e}")


async def check_mobile(geraet_name: str, viewport: dict, user_agent: str) -> Befund:
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context(viewport=viewport, user_agent=user_agent, is_mobile=True, has_touch=True)
            page = await ctx.new_page()
            fehler = []
            page.on("pageerror", lambda e: fehler.append(str(e)))
            await page.goto(INDEX_URL)
            # Startseite Screenshot
            start_png = SCREEN_DIR / f"mobile_{geraet_name}_start.png"
            await page.screenshot(path=str(start_png), full_page=True)
            # Horizontales Overflow prüfen (schlechte mobile UX wenn ja)
            overflow = await page.evaluate("() => document.documentElement.scrollWidth > window.innerWidth")
            # Button-Größe prüfen (Daumenregel: ≥44×44 px Touch-Target)
            btn_box = await page.locator("#btn-start").bounding_box()
            btn_h = btn_box["height"] if btn_box else 0
            await fragebogen_durchklicken(page)
            erg_png = SCREEN_DIR / f"mobile_{geraet_name}_ergebnis.png"
            await page.screenshot(path=str(erg_png), full_page=True)
            await browser.close()
            probleme = []
            if overflow:
                probleme.append("horizontales Scrollen")
            if btn_h < 40:
                probleme.append(f"Start-Button zu klein ({btn_h:.0f}px hoch)")
            if fehler:
                probleme.append(f"{len(fehler)} JS-Fehler")
            status = "fail" if fehler else "warn" if probleme else "ok"
            return Befund(f"Mobile: {geraet_name}", status,
                          ", ".join(probleme) if probleme else "Layout ok, Touch-Ziele ok",
                          [str(start_png.name), str(erg_png.name)])
        except Exception as e:
            return Befund(f"Mobile: {geraet_name}", "fail", f"Ausnahme: {e}")


async def check_persistenz() -> Befund:
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            page = await ctx.new_page()
            await page.goto(INDEX_URL)
            await page.locator("#btn-start").click()
            # 4 Regler + 1 Tätigkeitsfrage durchklicken, eine Tätigkeit ankreuzen
            for _ in range(4):
                await page.locator("#btn-weiter").click()
            erste_cb = page.locator('input[data-tag]').first
            await erste_cb.check()
            gewaehlter_tag = await erste_cb.get_attribute("data-tag")
            # Reload
            await page.reload()
            # Startseite — gibt es "Fortsetzen" Button?
            fortsetzen_sichtbar = await page.locator('#btn-weiter').count() > 0
            # localStorage-Inhalt
            ls = await page.evaluate("() => localStorage.getItem('kleinerpfadfinder_state_v1')")
            await browser.close()
            if not ls:
                return Befund("Persistenz", "fail", "localStorage leer nach Reload")
            parsed = json.loads(ls)
            tags = parsed.get("antworten", {}).get("taetigkeiten", [])
            if gewaehlter_tag not in tags:
                return Befund("Persistenz", "fail",
                              f"Tag '{gewaehlter_tag}' nicht in localStorage nach Reload")
            if not fortsetzen_sichtbar:
                return Befund("Persistenz", "warn",
                              f"Tag gespeichert, aber 'Fortsetzen'-Button fehlt")
            return Befund("Persistenz", "ok",
                          f"Tag '{gewaehlter_tag}' überlebt Reload, Fortsetzen-Button da")
        except Exception as e:
            return Befund("Persistenz", "fail", f"Ausnahme: {e}")


async def check_print() -> Befund:
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            page = await ctx.new_page()
            await page.goto(INDEX_URL)
            await fragebogen_durchklicken(page)
            pdf_pfad = SCREEN_DIR / "ergebnis.pdf"
            await page.pdf(path=str(pdf_pfad), format="A4", print_background=True)
            await browser.close()
            groesse_kb = pdf_pfad.stat().st_size / 1024
            return Befund("Print-Layout", "ok",
                          f"PDF erzeugt: {groesse_kb:.0f} KB — bitte manuell sichten",
                          [str(pdf_pfad.name)])
        except Exception as e:
            return Befund("Print-Layout", "fail", f"Ausnahme: {e}")


async def check_tastatur() -> Befund:
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            ctx = await browser.new_context()
            page = await ctx.new_page()
            await page.goto(INDEX_URL)
            # Tab bis zum Start-Button, Enter drücken
            for _ in range(10):
                await page.keyboard.press("Tab")
                fokus = await page.evaluate("() => document.activeElement?.id || document.activeElement?.tagName")
                if fokus == "btn-start":
                    break
            else:
                await browser.close()
                return Befund("Tastatur-Navigation", "fail", "btn-start nicht per Tab erreichbar")
            await page.keyboard.press("Enter")
            await page.wait_for_selector('#regler-input', timeout=5000)
            # Regler per Tastatur? Focus auf Regler dann ArrowRight
            await page.locator('#regler-input').focus()
            vorher = await page.locator('#regler-input').input_value()
            await page.keyboard.press("ArrowRight")
            nachher = await page.locator('#regler-input').input_value()
            await browser.close()
            if vorher == nachher:
                return Befund("Tastatur-Navigation", "warn",
                              "Regler reagiert nicht auf Pfeiltasten")
            return Befund("Tastatur-Navigation", "ok",
                          f"Start per Tab+Enter, Regler {vorher}→{nachher} per Pfeiltaste")
        except Exception as e:
            return Befund("Tastatur-Navigation", "fail", f"Ausnahme: {e}")


async def _scan_axe(launcher, flow) -> dict:
    """Einzelner axe-Scan in frischer Seite. `flow` setzt DOM-Zustand."""
    browser = await launcher.launch(headless=True)
    ctx = await browser.new_context()
    page = await ctx.new_page()
    await page.goto(INDEX_URL)
    await flow(page)
    await page.add_script_tag(url=AXE_CDN)
    result = await page.evaluate("async () => await axe.run()")
    await browser.close()
    return result


async def check_a11y_axe() -> Befund:
    async with async_playwright() as p:
        try:
            async def flow_start(page): pass

            async def flow_frage(page):
                await page.locator("#btn-start").click()
                await page.wait_for_selector("#regler-input")

            async def flow_ergebnis(page):
                await fragebogen_durchklicken(page)

            start_ergebnis, frage_ergebnis, erg_ergebnis = await asyncio.gather(
                _scan_axe(p.chromium, flow_start),
                _scan_axe(p.chromium, flow_frage),
                _scan_axe(p.chromium, flow_ergebnis),
            )

            def fasse_zusammen(res, label):
                verstoesse = res.get("violations", [])
                impacts = {}
                for v in verstoesse:
                    impacts[v["impact"]] = impacts.get(v["impact"], 0) + len(v.get("nodes", []))
                zeilen = [f"  {label}: {len(verstoesse)} Verstöße"]
                if impacts:
                    zeilen.append("    " + ", ".join(f"{k}: {v}" for k, v in impacts.items()))
                for v in verstoesse[:3]:
                    zeilen.append(f"    · [{v['impact']}] {v['id']} — {v['help']} ({len(v['nodes'])}×)")
                return "\n".join(zeilen)

            text = (
                fasse_zusammen(start_ergebnis, "Startseite") + "\n"
                + fasse_zusammen(frage_ergebnis, "Regler-Frage") + "\n"
                + fasse_zusammen(erg_ergebnis, "Ergebnis")
            )
            schwer = sum(
                len(v.get("nodes", []))
                for r in (start_ergebnis, frage_ergebnis, erg_ergebnis)
                for v in r.get("violations", [])
                if v.get("impact") in ("critical", "serious")
            )
            status = "fail" if schwer > 5 else "warn" if schwer > 0 else "ok"
            return Befund("A11y (axe-core)", status, text)
        except Exception as e:
            return Befund("A11y (axe-core)", "fail", f"Ausnahme: {e}")


# ---------- Orchestrierung ----------

async def check_alle_browser() -> list:
    async with async_playwright() as p:
        aufgaben = [
            check_browser("Chromium", p.chromium),
            check_browser("Firefox", p.firefox),
            check_browser("WebKit (Safari)", p.webkit),
        ]
        return await asyncio.gather(*aufgaben)


async def run() -> list:
    befunde = []
    print("Cross-Browser-Tests...")
    befunde.extend(await check_alle_browser())
    print("Mobile-Tests...")
    iphone_se = {"width": 375, "height": 667}
    pixel5 = {"width": 393, "height": 851}
    iphone_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15"
    pixel_ua = "Mozilla/5.0 (Linux; Android 13; Pixel 5) AppleWebKit/537.36"
    befunde.append(await check_mobile("iPhone_SE", iphone_se, iphone_ua))
    befunde.append(await check_mobile("Pixel_5", pixel5, pixel_ua))
    print("Persistenz...")
    befunde.append(await check_persistenz())
    print("Print-Layout...")
    befunde.append(await check_print())
    print("Tastatur-Navigation...")
    befunde.append(await check_tastatur())
    print("A11y (axe-core)...")
    befunde.append(await check_a11y_axe())
    return befunde


def report(befunde: list) -> str:
    z = ["# Ready-Check für Schüler:innen-Einsatz\n"]
    z.append(f"**{len(befunde)} Prüfungen.** Symbole: OK ✓ · Warnung ⚠ · Fehler ✗\n")
    z.append("## Übersicht\n")
    z.append("| Bereich | Status | Details |")
    z.append("|---|---|---|")
    sym = {"ok": "✓", "warn": "⚠", "fail": "✗"}
    for b in befunde:
        kurz = b.details.split("\n")[0][:80]
        z.append(f"| {b.bereich} | {sym.get(b.status, '?')} {b.status} | {kurz} |")
    z.append("")
    z.append("## Details\n")
    for b in befunde:
        z.append(f"### {sym.get(b.status, '?')} {b.bereich}")
        z.append(f"```\n{b.details}\n```")
        if b.artefakte:
            z.append(f"Artefakte: {', '.join(b.artefakte)} (in `tests/e2e/screens/`)\n")
        else:
            z.append("")
    # Gesamt-Urteil
    n_fail = sum(1 for b in befunde if b.status == "fail")
    n_warn = sum(1 for b in befunde if b.status == "warn")
    n_ok = sum(1 for b in befunde if b.status == "ok")
    z.append("## Gesamt-Urteil\n")
    z.append(f"- OK: {n_ok} · Warnung: {n_warn} · Fehler: {n_fail}")
    if n_fail == 0 and n_warn == 0:
        z.append("\n**Ready für Schüler:innen-Einsatz.** Alle automatisierten Checks grün.")
    elif n_fail == 0:
        z.append("\n**Bedingt ready.** Nur Warnungen — manuelle Sichtung erforderlich (Screenshots + PDF).")
    else:
        z.append("\n**Nicht ready.** Fehler-Befunde müssen behoben werden.")
    return "\n".join(z) + "\n"


def main():
    befunde = asyncio.run(run())
    md = report(befunde)
    REPORT.write_text(md, encoding="utf-8")
    print(f"\nOK - {len(befunde)} Pruefungen. Report: {REPORT}")


if __name__ == "__main__":
    main()
