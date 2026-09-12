"""Browser checks for the editable, single-photo carousel.

Start ``python3 server.py``, then run ``python3 tests/carousel_check.py``.
Uses Playwright and installed Chrome; optional --browsers firefox webkit use
their Playwright installations. Fixtures are intercepted in the browser, so
these checks never change the site's JSON or images.
"""

import argparse
import json
import re
from pathlib import Path

from playwright.sync_api import Error, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "data/emission-contribution.json"
INTERVAL_MS = 900


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def index(page):
    return int(page.locator("#gallery").get_attribute("data-active-index"))


def wait_index(page, value):
    page.wait_for_function("value => Number(document.querySelector('#gallery').dataset.activeIndex) === value",
                           arg=value, timeout=5000)


def idle(page):
    page.mouse.move(0, 0)
    page.evaluate("document.activeElement?.blur()")


def reveal(page):
    page.locator("#gallery").evaluate("element => element.scrollIntoView({block: 'center', behavior: 'instant'})")
    idle(page)


def stable(page, message):
    before = index(page)
    page.wait_for_timeout(INTERVAL_MS * 2)
    require(index(page) == before, message)


def fast_config(route):
    response = route.fetch()
    body, replacements = re.subn(r"intervalMs\s*:\s*[\d_]+", f"intervalMs: {INTERVAL_MS}", response.text())
    require(replacements == 1, "Test could not locate the carousel interval in site.config.js")
    route.fulfill(response=response, body=body)


class Fixture:
    def __init__(self, browser, base, slides=None, failure=None, motion="reduce", fast=False):
        self.errors = []
        self.context = browser.new_context(viewport={"width": 1440, "height": 1100},
                                           reduced_motion=motion, has_touch=True)
        self.page = self.context.new_page()
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        if fast:
            self.page.route("**/site.config.js", fast_config)
        if failure == "missing":
            self.page.route(f"**/{MANIFEST}", lambda route: route.abort())
        elif failure == "malformed":
            self.page.route(f"**/{MANIFEST}", lambda route: route.fulfill(
                content_type="application/json", body='[{"overlay_text":'))
        elif slides is not None:
            self.page.route(f"**/{MANIFEST}", lambda route: route.fulfill(json=slides))
        self.page.goto(base, wait_until="networkidle")
        self.page.wait_for_function("document.querySelector('#gallery').dataset.activeIndex !== undefined")

    def __enter__(self):
        return self.page

    def __exit__(self, error_type, error, traceback):
        self.context.close()
        if error_type is None:
            require(not self.errors, f"Browser errors: {self.errors}")


def slides_fixture():
    defaults = json.loads((ROOT / MANIFEST).read_text())
    return [dict(defaults[number % len(defaults)], **{
        "overlay_text": f"A clear message for photograph {number + 1}.",
        "source": f"Research source {number + 1}",
        "source link": f"https://example.org/research/{number + 1}",
        "image_caption": f"A community in Nepal. Photograph {number + 1}, credited to its author.",
    }) for number in range(4)]


def content_and_navigation(browser, base):
    slides = slides_fixture()
    with Fixture(browser, base, slides=slides) as page:
        cards = page.locator("#gallery .gallery-card")
        require(cards.count() == 4, "JSON array did not determine the number of slides")
        for number, slide in enumerate(slides):
            card = cards.nth(number)
            require(card.locator("h3").inner_text() == slide["overlay_text"], "Overlay text did not match JSON")
            source = card.locator(".gallery-source")
            require(slide["source"] in source.inner_text(), "Source label missing")
            link = source if source.evaluate("element => element.tagName === 'A'") else source.locator("a")
            require(link.get_attribute("href") == slide["source link"], "Exact 'source link' JSON key was not used")
            require(slide["image_caption"] in card.locator("figcaption").inner_text(), "Photo credit missing below image")
            require(card.evaluate("element => Math.abs(element.getBoundingClientRect().width - element.parentElement.clientWidth) < 2"),
                    "Slide does not fill the gallery width")
        require(page.locator("#gallery-count").inner_text().strip() == "01 / 04", "Counter is not dynamic")
        require(cards.nth(0).evaluate("element => !element.inert"), "Current card is inert")
        require(cards.nth(1).evaluate("element => element.inert"), "Offscreen card remains keyboard-focusable")
        page.locator("#gallery-prev").click()
        wait_index(page, 3)
        page.locator("#gallery-next").click()
        wait_index(page, 0)
        page.locator("#gallery").focus()
        page.keyboard.press("ArrowRight")
        wait_index(page, 1)
        page.keyboard.press("ArrowLeft")
        wait_index(page, 0)
        page.keyboard.press("ArrowLeft")
        wait_index(page, 3)
        page.locator("#gallery-next").click()
        wait_index(page, 0)
        # Real native scrolling exercises the same snap/scroll event path as touch.
        page.locator("#gallery").evaluate("""element => {
            const cards = element.querySelectorAll('.gallery-card');
            element.scrollTo({left: cards[1].offsetLeft - cards[0].offsetLeft, behavior: 'instant'});
        }""")
        wait_index(page, 1)
        require(cards.nth(1).evaluate("element => !element.inert && element.classList.contains('is-active')"),
                "Native scroll did not update the active card")
        page.locator('.gallery-expand[data-slide="1"]').click()
        require(page.locator("#lightbox").is_visible(), "Expanded photograph did not open")
        require(slides[1]["image_caption"] in page.locator("#lightbox-caption").inner_text(), "Expanded photo lost its credit")
        page.keyboard.press("ArrowRight")
        require(slides[2]["image_caption"] in page.locator("#lightbox-caption").inner_text(), "Lightbox does not use JSON slides")
        page.keyboard.press("Escape")


def safe_content(browser, base):
    slides = slides_fixture()[:2]
    slides[0].update({
        "overlay_text": '<img src=x onerror="window.carouselXss = true"> Keep this as text.',
        "source": "<strong>Research credit</strong>",
        "source link": "javascript:window.carouselXss=true",
        "image_caption": "<script>window.carouselXss=true</script> Photographer credit.",
    })
    with Fixture(browser, base, slides=slides) as page:
        card = page.locator("#gallery .gallery-card").first
        require(card.locator("h3").inner_text() == slides[0]["overlay_text"], "Markup in JSON overlay must remain literal text")
        require(card.locator("h3 img, h3 script, figcaption script").count() == 0, "JSON inserted executable markup")
        require(card.locator("a").evaluate_all("elements => elements.every(element => !/^javascript:/i.test(element.getAttribute('href') || ''))"),
                "Unsafe source URL became a navigable link")
        require(not page.evaluate("Boolean(window.carouselXss)"), "Untrusted JSON executed JavaScript")
        require("Photographer credit." in card.locator("figcaption").inner_text(), "Sanitization removed the photo credit")


def fallback_data(browser, base):
    for failure, slides in [("missing", None), ("malformed", None), (None, []), (None, {"unexpected": []})]:
        with Fixture(browser, base, slides=slides, failure=failure) as page:
            require(page.locator("#gallery .gallery-card").count() == 3,
                    f"Readable static fallback disappeared for {failure or slides!r}")
            page.locator("#gallery-next").click()
            wait_index(page, 1)
            require(page.locator("#gallery .gallery-card").nth(1).locator("h3").inner_text().strip(),
                    "Fallback card has no message")


def missing_image(browser, base):
    slides = slides_fixture()[:2]
    slides[0]["image"] = "missing-carousel-test-image.webp"
    with Fixture(browser, base, slides=slides) as page:
        reveal(page)
        card = page.locator("#gallery .gallery-card").first
        page.wait_for_function("""() => {
            const card = document.querySelector('#gallery .gallery-card');
            const image = card.querySelector('img');
            return !image || image.complete;
        }""")
        require(card.locator("h3").inner_text() == slides[0]["overlay_text"], "Missing image removed the message")
        require(slides[0]["image_caption"] in card.locator("figcaption").inner_text(), "Missing image removed the photo credit")
        require(card.locator(".gallery-image").evaluate("element => element.getBoundingClientRect().height > 100"),
                "Missing photograph collapsed the card layout")
        page.locator("#gallery-next").click()
        wait_index(page, 1)


def single_slide(browser, base):
    with Fixture(browser, base, slides=slides_fixture()[:1], motion="no-preference", fast=True) as page:
        reveal(page)
        require(page.locator("#gallery-count").inner_text().strip() == "01 / 01", "One-image count is wrong")
        for selector in ["#gallery-prev", "#gallery-next", "#gallery-toggle"]:
            control = page.locator(selector)
            require(not control.is_visible() or control.is_disabled(), f"Unusable one-image control remains active: {selector}")
        stable(page, "One-image carousel advanced")


def smooth_navigation(browser, base):
    with Fixture(browser, base, motion="no-preference") as page:
        page.locator("#gallery-next").click()
        wait_index(page, 1)
        page.locator("#gallery-next").click()
        wait_index(page, 2)
        # The requested card must not revert to an intermediate card while the
        # browser is still animating the scroll, including two quick next clicks.
        samples = page.evaluate("""() => new Promise(resolve => {
            const gallery = document.querySelector('#gallery');
            const samples = [];
            const start = performance.now();
            function sample() {
                samples.push(Number(gallery.dataset.activeIndex));
                if (performance.now() - start >= 800) resolve(samples);
                else requestAnimationFrame(sample);
            }
            sample();
        })""")
        require(samples and all(value == 2 for value in samples),
                f"Rapid next clicks lost the requested card during smooth scrolling: {sorted(set(samples))}")
        page.wait_for_function("""() => {
            const gallery = document.querySelector('#gallery');
            const cards = gallery.querySelectorAll('.gallery-card');
            return Math.abs(gallery.scrollLeft - (cards[2].offsetLeft - cards[0].offsetLeft)) < 2;
        }""", timeout=5000)
        for expected in range(3, page.locator("#gallery .gallery-card").count()):
            page.locator("#gallery-next").click()
            wait_index(page, expected)
        page.locator("#gallery-next").click()
        wait_index(page, 0)
        page.wait_for_function("document.querySelector('#gallery').scrollLeft < 2", timeout=5000)


def autoplay(browser, base):
    with Fixture(browser, base, motion="no-preference", fast=True) as page:
        stable(page, "Carousel advanced while outside the viewport")
        reveal(page)
        first = index(page)
        page.wait_for_function("initial => Number(document.querySelector('#gallery').dataset.activeIndex) !== initial",
                               arg=first, timeout=5000)
        page.locator("#gallery").hover()
        page.wait_for_timeout(300)
        stable(page, "Carousel advanced while hovered")
        idle(page)
        page.locator("#gallery").focus()
        stable(page, "Carousel advanced while keyboard focus was inside")
        page.locator("#gallery-toggle").click()
        idle(page)
        stable(page, "Explicit pause did not stop autoplay")
        old = index(page)
        page.locator("#gallery-next").click()
        wait_index(page, (old + 1) % page.locator("#gallery .gallery-card").count())
        idle(page)
        stable(page, "Manual navigation unexpectedly cleared explicit pause")
        page.locator("#gallery-toggle").click()
        idle(page)
        old = index(page)
        page.wait_for_function("initial => Number(document.querySelector('#gallery').dataset.activeIndex) !== initial",
                               arg=old, timeout=5000)
        page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
        page.wait_for_timeout(300)
        stable(page, "Carousel kept advancing after leaving the viewport")


def reduced_motion(browser, base):
    with Fixture(browser, base, fast=True) as page:
        reveal(page)
        stable(page, "Reduced-motion preference did not disable autoplay by default")
        require(page.locator("#gallery").evaluate("element => getComputedStyle(element).scrollBehavior !== 'smooth'"),
                "Reduced motion still uses smooth slide scrolling")
        page.locator("#gallery-toggle").click()
        idle(page)
        page.wait_for_function("Number(document.querySelector('#gallery').dataset.activeIndex) !== 0", timeout=5000)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--browsers", nargs="+", choices=("chromium", "webkit", "firefox"), default=["chromium"])
    args = parser.parse_args()
    results = []
    with sync_playwright() as playwright:
        for name in args.browsers:
            browser = getattr(playwright, name).launch(headless=True, **({"channel": "chrome"} if name == "chromium" else {}))
            try:
                for check in [content_and_navigation, safe_content, fallback_data, missing_image,
                              single_slide, smooth_navigation, autoplay, reduced_motion]:
                    result = {"browser": name, "check": check.__name__, "result": "PASS"}
                    try:
                        check(browser, args.base_url)
                    except (AssertionError, Error) as error:
                        result.update(result="FAIL", error=str(error))
                    results.append(result)
                    print(json.dumps(result), flush=True)
            finally:
                browser.close()
    failed = sum(result["result"] == "FAIL" for result in results)
    print(json.dumps({"result": "FAIL" if failed else "PASS", "passed": len(results) - failed, "failed": failed}))
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
