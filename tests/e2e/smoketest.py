"""Smoketest: Fragebogen durchklicken, Ergebnisansicht prüfen, Screenshot."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
INDEX_URL = (ROOT / "index.html").as_uri()
SCREENSHOT = Path(__file__).parent / "ergebnis.png"
ANZAHL_FRAGEN = 11


def run(headless: bool = True) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1200, "height": 900})
        page.goto(INDEX_URL)

        page.locator("#btn-start").click()

        # Ein paar Tätigkeiten ankreuzen, damit nicht das "wenige Berufe"-Ergebnis greift
        for i in range(ANZAHL_FRAGEN - 1):
            for cb in page.locator('input[data-tag]').all()[:3]:
                cb.check()
            page.locator("#btn-weiter").click()

        # Motivationsfrage: bis zu 3 anhaken
        for cb in page.locator('input[data-motivation]').all()[:3]:
            cb.check()
        page.locator("#btn-weiter").click()

        # Ergebnis-Assertions
        expect(page.locator(".ergebnis-kopf h1")).to_be_visible()
        karten = page.locator(".ergebnis-karte")
        assert karten.count() >= 3, f"Erwartet mind. 3 Karten, gefunden {karten.count()}"
        top = page.locator(".ergebnis-karte.top")
        assert top.count() == 3, f"Erwartet 3 Top-Karten, gefunden {top.count()}"
        expect(page.locator(".match-fuellung").first).to_be_visible()

        page.screenshot(path=str(SCREENSHOT), full_page=True)
        print(f"OK — {karten.count()} Karten, Screenshot: {SCREENSHOT}")
        browser.close()


if __name__ == "__main__":
    run(headless="--headed" not in sys.argv)
