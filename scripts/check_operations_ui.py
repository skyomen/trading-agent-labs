"""Browser proof of Operations, Market and fixed navigation using isolated paper data."""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def seed(root):
    os.environ["TRADING_LAB_DATA_DIR"] = str(root)
    from database import store
    from services import auth, market_data

    store.initialize()
    owner = auth.create_account("visual_owner", "synthetic-password-123", role="owner")
    with store.user_workspace(owner["id"]):
        store.initialize()
        rules = {"engine": "setup_pattern_v1", "approval": "rules_human_approved",
                 "setup_id": "SETUP_03", "setup_name": "BOP", "side": "buy",
                 "pattern": {"kind": "compressed_base", "min_bars": 3, "max_bars": 8,
                             "max_range_atr20": 1.5, "trend_ma": 8}}
        sid = store.save_strategy("BOP fixture", rules, "synthetic")
        store.approve_strategy(sid)
        signal = "2026-11-18T16:05:00+00:00"
        entry = "2026-11-18T16:10:00+00:00"
        exit_time = "2026-11-18T16:45:00+00:00"
        report = {"execution": {"entrada": 100.0, "stop": 99.0, "alvo": 101.0,
                                "side": "buy", "barra_de_entrada_utc": entry},
                  "decision": {"decisao": "trade_candidate", "fatores_contrarios": ["Amostra curta."]},
                  "risk": {"verdict": "autorizado", "checks": [{"estado": "ok", "detalhe": "Limite respeitado."}]},
                  "market": {"provedor": market_data.PROVIDER, "feed_status": "connected",
                             "tendencia": {"media_movel_periodo": 8, "inclinacao": 0.4}}}
        run = store.save_pipeline_run("agent_pipeline_v1", sid, "SETUP_03", "BOP",
                                      "ETHUSDT", "5m", signal, "trade_candidate",
                                      risk_verdict="autorizado", status="aguardando_quantidade", report=report)
        op = store.open_paper_operation("ETHUSDT", "buy", 0.02, 100.0,
                                        "pipeline fixture", pipeline_run_id=run)
        store.close_paper_operation(
            op, 99.9, "stop", datetime.now(timezone.utc).isoformat(), fees=0.004,
            realized_r=-0.7, journal_details={"entry_time": entry, "exit_time": exit_time,
                                              "net_pnl": -0.006, "quote_currency": "USDT",
                                              "fee_bps_per_side": 10.0,
                                              "slippage_bps_per_side": 5.0,
                                              "conduction": {"initial_stop": 99.0, "final_stop": 99.0}})
        origin = datetime(2026, 11, 18, 15, 0, tzinfo=timezone.utc)
        bars = [{"timestamp": (origin + timedelta(minutes=i)).isoformat(),
                 "open": 100.0 + (i % 15) * 0.04, "high": 101.0 + (i % 15) * 0.04,
                 "low": 99.0 + (i % 15) * 0.04, "close": 100.0 + (i % 15) * 0.04,
                 "volume": 3.0} for i in range(150)]
        store.upsert_market_bars(market_data.PROVIDER, "ETHUSDT", "1m", bars)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        seed(root)
        env = dict(os.environ, TRADING_LAB_DATA_DIR=tmp)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", str(ROOT / "app.py"),
             "--server.address", "127.0.0.1", "--server.port", str(port),
             "--server.headless", "true", "--browser.gatherUsageStats", "false"],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(60):
                try:
                    with urlopen(base + "/_stcore/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except (URLError, TimeoutError):
                    time.sleep(0.5)
            else:
                raise RuntimeError("Servidor de prova não iniciou.")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    review = ROOT / ".impeccable" / "review"
                    review.mkdir(parents=True, exist_ok=True)
                    for width, height in ((1440, 1000), (390, 844), (320, 740)):
                        page = browser.new_page(viewport={"width": width, "height": height})
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.goto(base)
                        page.get_by_role("heading", name="Operações").first.wait_for(timeout=30000)
                        assert page.get_by_role("textbox", name="Usuário").count() == 0
                        assert page.get_by_label("Senha", exact=True).count() == 0
                        page.get_by_text("-0.006000 USDT").first.wait_for(timeout=30000)
                        assert page.get_by_text("Estado geral", exact=True).count() == 0
                        page.screenshot(path=str(review / f"operations-list-{width}.png"), full_page=True)
                        page.get_by_role("link", name="Ver detalhes da operação #1").click()
                        page.get_by_text("Por que entrou").wait_for(timeout=30000)
                        chart = page.locator("iframe").last
                        chart.wait_for(timeout=30000)
                        chart_box = chart.bounding_box()
                        assert chart_box, "Gráfico sem área renderizada"
                        chart_frame = next(frame for frame in page.frames
                                           if frame.locator("#overlay").count())
                        chart_frame.wait_for_function(
                            "document.querySelectorAll('#overlay path').length >= 2", timeout=15000)
                        chart.screenshot(path=str(review / f"operations-chart-{width}.png"))
                        page.get_by_role("button", name="Próxima etapa: Stop definido no plano").click()
                        page.locator(".ops-step-panel h3").get_by_text("Stop definido no plano").wait_for(timeout=30000)
                        page.screenshot(path=str(review / f"operations-detail-{width}.png"), full_page=True)
                        page.get_by_text("Conferir OHLCV dos candles marcados").click()
                        page.get_by_text("2026-11-18T16:45:00Z").first.wait_for(
                            state="attached", timeout=30000)
                        page.locator(".ops-back").click()
                        page.get_by_role("link", name="Ver detalhes da operação #1").wait_for(timeout=30000)
                        dock = page.locator(".tal-bottom-nav")
                        dock.wait_for()
                        assert dock.evaluate("el => getComputedStyle(el).position") == "fixed"
                        page.get_by_role("link", name="Mercado").click()
                        page.get_by_role("heading", name="Mercado").wait_for(timeout=30000)
                        page.locator(".market-hero").wait_for(state="visible", timeout=10000)
                        assert page.locator(".market-source").count() == 0
                        assert page.locator("iframe").count() >= 1
                        page.wait_for_timeout(6000)
                        tv_frame = next((frame for frame in page.frames
                                         if "tradingview-widget.com/embed-widget/advanced-chart" in frame.url), None)
                        assert tv_frame, "TradingView não carregou seu iframe externo"
                        tv_frame.locator("canvas").first.wait_for(state="visible", timeout=20000)
                        page.screenshot(path=str(review / f"market-{width}.png"), full_page=True)
                        page.get_by_role("link", name="Operações").click()
                        page.get_by_role("heading", name="Operações").wait_for(timeout=30000)
                        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1"), width
                        assert not errors, errors
                        print(f"Operações/Mercado {width}x{height}: rotas, gráfico e dock sem corte", flush=True)
                        page.close()
                finally:
                    browser.close()
        finally:
            process.terminate()
            process.wait(timeout=15)


if __name__ == "__main__":
    main()
