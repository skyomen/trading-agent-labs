"""Read-only browser smoke check for the historical setup form and reports."""

from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for width, height in ((1440, 1000), (390, 844), (320, 740)):
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto("http://localhost:8501/?lab=1")
            page.wait_for_load_state("networkidle")
            page.get_by_text("Laboratório", exact=True).first.click()
            page.get_by_text("Executar simulação histórica", exact=True).first.wait_for(timeout=30000)
            form_count = page.get_by_text("Executar simulação histórica", exact=True).count()
            print(f"form_count={form_count}", flush=True)
            assert form_count == 4
            assert page.get_by_text("Resultados históricos persistidos", exact=False).count() > 0
            overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
            print(f"{width}x{height}: form=4 reports=present horizontal_overflow={overflow}")
            assert not overflow
            page.close()
        browser.close()


if __name__ == "__main__":
    main()
