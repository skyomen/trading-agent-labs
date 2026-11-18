"""Headless login/portal/lab layout proof against a disposable local database."""

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    original_cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, TRADING_LAB_DATA_DIR=tmp)
        os.environ["TRADING_LAB_DATA_DIR"] = tmp
        from database import store
        from services import auth
        store.initialize()
        auth.create_account("demo_owner", "synthetic-password-123", role="owner")
        port = _free_port()
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
                raise RuntimeError("Servidor local de prova não iniciou.")
            os.chdir(tmp)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    for width, height in ((1440, 1000), (390, 844), (320, 740)):
                        page = browser.new_page(viewport={"width": width, "height": height})
                        errors = []
                        page.on("pageerror", lambda error: errors.append(str(error)))
                        page.goto(base)
                        page.get_by_role("textbox", name="Usuário").fill("demo_owner")
                        page.get_by_label("Senha", exact=True).fill("synthetic-password-123")
                        page.get_by_role("button", name="Entrar").click()
                        frame = page.frame_locator("iframe").first
                        frame.locator("#p-rank").wait_for(timeout=30000)
                        frame.locator('#vtabs button[data-v="lab"]').click()
                        frame.locator("#labtxt").get_by_text("Diário paper").wait_for()
                        page.get_by_role("radio", name="Laboratório").check(force=True)
                        page.get_by_role("radio", name="Orquestração").check(force=True)
                        page.get_by_text("Ordens virtuais Binance Spot Testnet").wait_for(timeout=30000)
                        assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
                        assert not errors, errors
                        print(f"UI {width}x{height}: login, portal e laboratorio sem erro horizontal", flush=True)
                        page.close()
                finally:
                    browser.close()
        finally:
            os.chdir(original_cwd)
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
