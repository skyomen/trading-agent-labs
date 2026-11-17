"""Read-only responsive check of the paper journal on a local Streamlit server."""

import os

from playwright.sync_api import sync_playwright


def main():
    base = os.environ.get("TAL_UI_URL", "http://localhost:8502")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        for width, height in ((1440, 1000), (390, 844), (320, 740)):
            page = browser.new_page(viewport={"width": width, "height": height})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base + "/")
            frame = page.frame_locator("iframe").first
            frame.locator('#vtabs button[data-v="lab"]').click(timeout=30000)
            frame.locator("#labtxt").get_by_text("Diário paper").wait_for()
            frame.locator("#labtxt").get_by_text("Aprendizado controlado").wait_for()
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
            assert not frame.locator("body").evaluate(
                "element => element.scrollWidth > element.clientWidth + 1")
            assert not errors, errors
            page.close()

            lab = browser.new_page(viewport={"width": width, "height": height})
            lab_errors = []
            lab.on("pageerror", lambda error: lab_errors.append(str(error)))
            lab.goto(base + "/?lab=1")
            lab.get_by_text("Trading Agent Lab").first.wait_for(timeout=30000)
            assert not lab.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
            assert not lab_errors, lab_errors
            lab.close()
            print(f"UI {width}x{height}: portal e laboratório sem erro ou rolagem horizontal", flush=True)
        browser.close()


if __name__ == "__main__":
    main()
