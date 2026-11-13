"""Read-only browser check for local market and simulation state."""

from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for width, height in ((1440, 1000), (390, 844), (320, 740)):
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto("http://localhost:8501/")
            page.wait_for_load_state("networkidle")
            frame = page.frame_locator("iframe").first
            frame.locator('#tabs .tab[data-t="mkt"]').click()
            frame.locator("#mhead").get_by_text("AAPL · Alpaca IEX", exact=False).first.wait_for(timeout=30000)
            frame.locator("#mhead").get_by_text("MSFT · Alpaca IEX", exact=False).first.wait_for()
            frame.locator('#tabs .tab[data-t="ctl"]').click()
            frame.locator("#p-ctl").get_by_text("Credenciais presentes; histórico manual", exact=False).first.wait_for()
            frame.locator('#tabs .tab[data-t="inf"]').click()
            frame.locator("#p-inf").get_by_text("Snapshots históricos", exact=False).first.wait_for()
            frame.locator('#tabs .tab[data-t="ops"]').click()
            frame.locator("#p-ops").get_by_text("Nenhuma operação simulada conciliada", exact=False).first.wait_for()
            frame.locator('#vtabs button[data-v="lab"]').click()
            frame.locator("#labtxt").get_by_text("VBS · BTCUSDT · 2m", exact=False).first.wait_for()
            frame.locator('#vtabs button[data-v="evo"]').click()
            frame.locator("#evnote").get_by_text("Backtests históricos não são operações de conta", exact=False).first.wait_for()
            frame.locator('#vtabs button[data-v="sala"]').click()
            assert not errors, errors
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
            print(f"portal {width}x{height}: mercado, controle, informe e operações OK", flush=True)
            page.close()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto("http://localhost:8501/?lab=1")
        page.wait_for_load_state("networkidle")
        page.get_by_text("Mercado", exact=True).first.click()
        page.get_by_role("tab", name="Ações dos EUA").click()
        page.get_by_text("AAPL e MSFT · históricos locais", exact=False).first.wait_for()
        page.get_by_text("Alpaca IEX", exact=False).first.wait_for()
        page.get_by_text("Controle", exact=True).first.click()
        page.get_by_text("Credenciais presentes", exact=False).first.wait_for()
        page.get_by_text("Informe", exact=True).first.click()
        page.get_by_text("6 snapshots históricos", exact=False).first.wait_for()
        page.get_by_text("Operações", exact=True).first.click()
        page.get_by_text("Nenhuma operação simulada conciliada", exact=False).first.wait_for()
        print("laboratório local: mercado e controle OK", flush=True)
        page.close()
        browser.close()


if __name__ == "__main__":
    main()
