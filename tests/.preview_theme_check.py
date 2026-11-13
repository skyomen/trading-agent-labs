from pathlib import Path

from playwright.sync_api import sync_playwright


source = Path("trading-lab-preview.html").resolve().as_uri()
review = Path(".impeccable/review")
review.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    for width, height, device in ((390, 844, "mobile"), (1440, 1000, "desktop")):
        page = browser.new_page(viewport={"width": width, "height": height})
        page.route("https://fonts.googleapis.com/**", lambda route: route.fulfill(body="", content_type="text/css"))
        page.goto(source, wait_until="networkidle")
        page.locator("#trading-floor-preview").wait_for()
        page.locator(".station").first.wait_for()
        dark = page.locator(".window").evaluate(
            "(el) => getComputedStyle(el).backgroundColor"
        )
        page.locator(".theme").click()
        light = page.locator("#trading-floor-preview").evaluate(
            "(el) => ({root: getComputedStyle(el).backgroundColor, "
            "theme: el.dataset.theme, raised: getComputedStyle(el).getPropertyValue('--raised').trim(), "
            "stationActive: getComputedStyle(el).getPropertyValue('--station-active').trim(), "
            "stationBg: getComputedStyle(el).getPropertyValue('--station-bg').trim(), "
            "window: getComputedStyle(el.querySelector('.window')).backgroundColor, "
            "station: getComputedStyle(el.querySelector('.station')).backgroundColor, "
            "stationRaised: getComputedStyle(el.querySelector('.station')).getPropertyValue('--raised').trim(), "
            "stationPressed: el.querySelector('.station').getAttribute('aria-pressed'), "
            "lightSelector: el.querySelector('.station').matches('#trading-floor-preview[data-theme=light] .station'), "
            "stationInline: el.querySelector('.station').getAttribute('style'), "
            "stationBgValue: getComputedStyle(el.querySelector('.station')).background, "
            "rules: Array.from(document.styleSheets).flatMap(s=>{try{return Array.from(s.cssRules).map(x=>x.cssText).filter(x=>x.includes('station'))}catch{return []}}), "
            "stationHover: el.querySelector('.station').matches(':hover'), "
            "overflow: document.documentElement.scrollWidth > innerWidth})"
        )
        print(f"{device} after light toggle: dark={dark}, light={light}")
        assert dark == "rgb(16, 23, 28)", dark
        assert light["root"] == "rgba(0, 0, 0, 0)", light
        assert light["window"] == "rgb(240, 244, 242)", light
        assert light["station"] == "rgb(247, 250, 248)", light
        assert not light["overflow"], light
        assert page.locator(".station").count() == 6
        page.locator('.station[data-agent="Risk Manager"]').click()
        assert page.locator('[data-detail="name"]').inner_text() == "Risk Manager"
        page.screenshot(path=str(review / f"preview-{device}-light.png"), full_page=True)
        page.locator(".theme").click()
        dark_after_toggle = page.locator(".window").evaluate(
            "(el) => getComputedStyle(el).backgroundColor"
        )
        assert dark_after_toggle == "rgb(23, 31, 37)", dark_after_toggle
        page.screenshot(path=str(review / f"preview-{device}-dark.png"), full_page=True)
        print(
            f"{device}: dark-root={dark}; light={light}; "
            f"dark-after-toggle={dark_after_toggle}"
        )
        page.close()
    browser.close()
