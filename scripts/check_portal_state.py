"""Read-only browser check for local market, simulation and validation state.

Every locator is scoped to the panel that owns it. An unscoped
`get_by_text(...).first` once matched a hidden element in another panel and
timed out; the scope is the fix, not a longer timeout.
"""

import os
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWPORTS = ((1440, 1000), (390, 844), (320, 740))
ROOM_VIEWPORTS = ((1440, 1000), (390, 844))
ANALYSTS = ("Research Agent", "Market Analyst", "Fundamental Analyst",
            "Strategy & Backtest", "Risk Manager")
SHOTS = Path(os.environ.get("PORTAL_SHOTS") or (Path(tempfile.gettempdir()) / "portal-shots"))


def check_default_portal(browser, width, height):
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
    frame.locator("#p-inf").get_by_text("Validações executadas", exact=False).first.wait_for()
    frame.locator("#p-inf").get_by_text("Validações com amostra insuficiente", exact=False).first.wait_for()
    frame.locator("#p-inf .local-flag").first.wait_for()
    frame.locator('#tabs .tab[data-t="ops"]').click()
    frame.locator("#p-ops").get_by_text("Nenhuma operação simulada conciliada", exact=False).first.wait_for()
    frame.locator('#vtabs button[data-v="lab"]').click()
    frame.locator("#labtxt").get_by_text("VBS · BTCUSDT · 2m", exact=False).first.wait_for()
    frame.locator("#labtxt").get_by_text("Validação de setups", exact=False).first.wait_for()
    frame.locator("#labtxt").get_by_text("validações executadas", exact=False).first.wait_for()
    frame.locator("#labtxt").get_by_text("com amostra insuficiente", exact=False).first.wait_for()
    frame.locator("#labtxt .local-flag").first.wait_for()
    frame.locator("#labtxt .local-flag-inline").first.wait_for()
    frame.locator('#vtabs button[data-v="evo"]').click()
    frame.locator("#evnote").get_by_text("Backtests históricos não são operações de conta", exact=False).first.wait_for()
    frame.locator('#vtabs button[data-v="sala"]').click()
    assert not errors, errors
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
    print(f"portal {width}x{height}: mercado, controle, informe, operações e validação OK", flush=True)
    page.close()


def desk_names(frame):
    """Nomes das mesas desenhadas na cena isométrica, lidos do aria-label."""
    labels = frame.locator("#floor .desk").evaluate_all(
        "nodes => nodes.map(n => n.getAttribute('aria-label') || '')")
    return [label.replace("Mesa de ", "").split(":")[0].strip() for label in labels]


def check_rooms(browser, width, height):
    """A sala do portal padrão separa analistas do posto de execução."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    page = browser.new_page(viewport={"width": width, "height": height})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://localhost:8501/")
    page.wait_for_load_state("networkidle")
    frame = page.frame_locator("iframe").first
    frame.locator('#tabs .tab[data-t="rank"]').click()
    frame.locator('#vtabs button[data-v="sala"]').click()
    analistas = frame.locator('#roomsel button[data-room="Analistas"]')
    execucao = frame.locator('#roomsel button[data-room="Execução"]')
    analistas.wait_for(timeout=30000)
    execucao.wait_for()

    assert analistas.get_attribute("aria-pressed") == "true"
    names = desk_names(frame)
    assert sorted(names) == sorted(ANALYSTS), names
    assert "Execution Agent" not in names, names
    legend = frame.locator("#roomleg").inner_text()
    assert legend == "5 mesas de análise", legend
    assert frame.locator("#p-rank .row").count() == 6
    assert frame.locator("#glance .gl").count() == 6
    page.screenshot(path=str(SHOTS / f"sala-analistas-{width}x{height}.png"))

    execucao.click()
    names = desk_names(frame)
    assert names == ["Execution Agent"], names
    legend = frame.locator("#roomleg").inner_text()
    assert legend == "1 posto de execução · recepção bloqueada", legend
    assert execucao.get_attribute("aria-pressed") == "true"
    assert analistas.get_attribute("aria-pressed") == "false"
    assert "Execution Agent" in frame.locator("#ficha").inner_text()
    assert frame.locator("#p-rank .row").count() == 6
    assert frame.locator("#glance .gl").count() == 6
    page.screenshot(path=str(SHOTS / f"sala-execucao-{width}x{height}.png"))

    frame.locator('#p-rank .row[data-i="1"]').click()
    assert analistas.get_attribute("aria-pressed") == "true"
    assert "Execution Agent" not in frame.locator("#ficha").inner_text()
    assert "Execution Agent" not in desk_names(frame)

    frame.locator('#vtabs button[data-v="lab"]').click()
    assert not frame.locator("#roomsel").is_visible()
    frame.locator('#vtabs button[data-v="sala"]').click()
    assert frame.locator("#roomsel").is_visible()

    assert not errors, errors
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
    assert not frame.locator("body").evaluate(
        "body => body.ownerDocument.documentElement.scrollWidth > body.ownerDocument.documentElement.clientWidth + 1")
    print(f"salas {width}x{height}: analistas e execução separadas OK", flush=True)
    page.close()


def check_local_lab(browser, width, height):
    page = browser.new_page(viewport={"width": width, "height": height})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://localhost:8501/?lab=1")
    page.wait_for_load_state("networkidle")
    nav, side, stage = (page.locator(".st-key-tal-nav"), page.locator(".st-key-tal-side"),
                        page.locator(".st-key-tal-stage"))
    stage.locator(".st-key-tal-view").get_by_text("Laboratório", exact=True).click()
    page.wait_for_load_state("networkidle")
    stage.get_by_text("Validation Engine · treino e out-of-sample", exact=False).first.wait_for(timeout=30000)
    stage.get_by_role("button", name="Rodar validação").first.wait_for()
    stage.get_by_text("Validações persistidas", exact=False).first.wait_for()
    stage.get_by_text("validações registradas", exact=False).first.wait_for()
    stage.get_by_text("AMOSTRA INSUFICIENTE", exact=False).first.wait_for()
    nav.get_by_text("Informe", exact=True).click()
    page.wait_for_load_state("networkidle")
    side.get_by_text("validações executadas", exact=False).first.wait_for(timeout=30000)
    side.get_by_text("com amostra insuficiente", exact=False).first.wait_for()
    assert not errors, errors
    assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
    print(f"laboratório {width}x{height}: validação e informe OK", flush=True)
    page.close()


def check_local_lab_market(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto("http://localhost:8501/?lab=1")
    page.wait_for_load_state("networkidle")
    nav, side = page.locator(".st-key-tal-nav"), page.locator(".st-key-tal-side")
    nav.get_by_text("Mercado", exact=True).click()
    side.get_by_role("tab", name="Ações dos EUA").click()
    side.get_by_text("AAPL e MSFT · históricos locais", exact=False).first.wait_for(timeout=30000)
    side.get_by_text("Alpaca IEX", exact=False).first.wait_for()
    nav.get_by_text("Controle", exact=True).click()
    side.get_by_text("Credenciais presentes", exact=False).first.wait_for(timeout=30000)
    nav.get_by_text("Informe", exact=True).click()
    side.get_by_text("6 snapshots históricos", exact=False).first.wait_for(timeout=30000)
    nav.get_by_text("Operações", exact=True).click()
    side.get_by_text("Nenhuma operação simulada conciliada", exact=False).first.wait_for(timeout=30000)
    print("laboratório local: mercado e controle OK", flush=True)
    page.close()


def main():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for width, height in VIEWPORTS:
            check_default_portal(browser, width, height)
        for width, height in ROOM_VIEWPORTS:
            check_rooms(browser, width, height)
        for width, height in VIEWPORTS:
            check_local_lab(browser, width, height)
        check_local_lab_market(browser)
        browser.close()


if __name__ == "__main__":
    main()
