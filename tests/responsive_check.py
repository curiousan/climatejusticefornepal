"""Responsive browser regression audit for the local static site.

Start ``python3 server.py`` separately, then run:
    python3 tests/responsive_check.py
    python3 tests/responsive_check.py --browsers chromium webkit firefox

Requires the Playwright Python package. Chromium uses installed Google Chrome;
optional WebKit and Firefox use their Playwright browser installations. The audit
does not install browsers or contact donation/social sites. Screenshots and a JSON
report are written to /tmp/nepal-responsive-checks by default.
"""

import argparse
import json
from pathlib import Path

from playwright.sync_api import Error, sync_playwright


PROFILES = [
    ("phone-280", 280, 653),
    ("phone-320", 320, 568),
    ("phone-360", 360, 640),
    ("phone-390", 390, 844),
    ("phone-430", 430, 932),
    ("landscape-568", 568, 320),
    ("landscape-844", 844, 390),
    ("tablet-600", 600, 960),
    ("tablet-768", 768, 1024),
    ("tablet-820", 820, 1180),
    ("tablet-1024", 1024, 768),
    ("breakpoint-539", 539, 900),
    ("breakpoint-541", 541, 900),
    ("breakpoint-799", 799, 1000),
    ("breakpoint-801", 801, 1000),
    ("desktop-1280", 1280, 720),
    ("desktop-1440", 1440, 900),
    ("desktop-1920", 1920, 1080),
    ("ultrawide-2560", 2560, 1080),
]
SCREENSHOT_PROFILES = {
    "phone-320", "phone-390", "landscape-568", "tablet-768",
    "desktop-1440", "ultrawide-2560",
}
ZOOM_PROFILES = [(320, 568), (390, 844), (768, 1024), (1280, 720)]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def settle(page):
    """Wait for layout frames, avoiding arbitrary screenshot timing sleeps."""
    page.evaluate("""() => new Promise(resolve => {
        setTimeout(resolve, 150);
        requestAnimationFrame(() => requestAnimationFrame(resolve));
    })""")


def top(page):
    page.evaluate("window.scrollTo({top: 0, left: 0, behavior: 'instant'})")
    settle(page)


def load(page, base):
    page.goto(base, wait_until="networkidle")
    page.evaluate("Promise.race([document.fonts.ready, new Promise(resolve => setTimeout(resolve, 3000))])")
    page.wait_for_function("document.querySelector('#data-status').textContent.length > 0")
    page.wait_for_function("document.querySelector('#gallery').dataset.activeIndex !== undefined")
    settle(page)


def geometry(page):
    """Allow the intentional carousel scroll area, but not page overflow."""
    top(page)
    issues = page.evaluate("""() => {
        const problems = [];
        const tolerance = 1.5;
        const width = document.documentElement.clientWidth;
        const visible = element => !!element.getClientRects().length &&
            getComputedStyle(element).visibility !== 'hidden';
        const label = element => element.id ? '#' + element.id :
            element.tagName.toLowerCase() + '.' + [...element.classList].join('.');
        if (document.documentElement.scrollWidth > width + tolerance ||
            document.body.scrollWidth > width + tolerance) {
            problems.push(`page overflow: viewport=${width}, html=${document.documentElement.scrollWidth}, body=${document.body.scrollWidth}`);
        }
        for (const element of document.querySelectorAll('body *')) {
            if (!visible(element) || element.closest('svg, [aria-hidden="true"], dialog, .hero-media, .hero-shade') ||
                element.classList.contains('skip-link') ||
                (element.id !== 'gallery' && element.closest('#gallery'))) continue;
            const rect = element.getBoundingClientRect();
            if (rect.width && (rect.left < -tolerance || rect.right > width + tolerance)) {
                problems.push(`${label(element)} outside page: ${rect.left.toFixed(1)}..${rect.right.toFixed(1)}`);
            }
        }
        // Check text ink as well as element boxes: a fixed-width heading can clip
        // even when its own box fits. Gallery text is checked against its card.
        for (const element of document.querySelectorAll('h1, h2, h3, .big-number, .impact-value, .donate-link')) {
            if (!visible(element)) continue;
            const bounds = element.closest('.gallery-card')?.getBoundingClientRect() || {left: 0, right: width};
            const textNodes = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
            while (textNodes.nextNode()) {
                const node = textNodes.currentNode;
                // Ranges ignore clipping, so exclude the deliberately clipped
                // stable screen-reader equivalents of animated numbers.
                if (!node.textContent.trim() || node.parentElement.closest('.visually-hidden')) continue;
                const range = document.createRange();
                range.selectNodeContents(node);
                const ink = range.getBoundingClientRect();
                if (ink.left < bounds.left - tolerance || ink.right > bounds.right + tolerance) {
                    problems.push(`${label(element)} text exceeds its available width`);
                    break;
                }
            }
        }
        const header = document.querySelector('.site-header').getBoundingClientRect();
        const brand = document.querySelector('.site-header .brand').getBoundingClientRect();
        const actions = document.querySelector('.header-actions').getBoundingClientRect();
        const horizontalOverlap = Math.min(brand.right, actions.right) - Math.max(brand.left, actions.left);
        const verticalOverlap = Math.min(brand.bottom, actions.bottom) - Math.max(brand.top, actions.top);
        if (horizontalOverlap > tolerance && verticalOverlap > tolerance) problems.push('header brand overlaps actions');
        const hero = document.querySelector('.hero').getBoundingClientRect();
        const heroTitle = document.querySelector('.hero h1');
        const heroMessage = document.querySelector('.hero .hero-message');
        const heroNumbers = [...document.querySelectorAll('#hero-title .hero-number')];
        if (!heroTitle || document.querySelectorAll('h1').length !== 1) problems.push('hero must contain the page heading');
        if (!heroMessage || heroNumbers.length !== 2) {
            problems.push('hero heading must contain both climate metrics in one message');
        }
        for (const element of [heroTitle, heroMessage, ...heroNumbers].filter(Boolean)) {
            const rect = element.getBoundingClientRect();
            if (rect.left < hero.left - tolerance || rect.right > hero.right + tolerance ||
                rect.top < hero.top - tolerance || rect.bottom > hero.bottom + tolerance) {
                problems.push(`${label(element)} extends outside hero`);
            }
        }
        const message = heroMessage.getBoundingClientRect();
        const heroActions = document.querySelector('.hero-actions').getBoundingClientRect();
        const footer = document.querySelector('.hero-footer').getBoundingClientRect();
        if (message.top < header.bottom - tolerance) problems.push('hero text overlaps header');
        if (heroActions.bottom > footer.top + tolerance) problems.push('hero actions overlap hero footer');
        if (message.top < hero.top - tolerance || footer.bottom > hero.bottom + tolerance) {
            problems.push('hero content clipped by hero boundary');
        }
        const gallery = document.querySelector('#gallery');
        for (const card of gallery.querySelectorAll('.gallery-card')) {
            const cardRect = card.getBoundingClientRect();
            if (Math.abs(cardRect.width - gallery.clientWidth) > tolerance) {
                problems.push('gallery must show one full-width photograph at a time');
            }
            const image = card.querySelector('.gallery-image').getBoundingClientRect();
            const caption = card.querySelector('figcaption').getBoundingClientRect();
            if (caption.top < image.bottom - tolerance) problems.push('photo credit overlaps the photograph');
            for (const text of card.querySelectorAll('h3, .gallery-source')) {
                const rect = text.getBoundingClientRect();
                if (rect.left < image.left - tolerance || rect.right > image.right + tolerance ||
                    rect.top < image.top - tolerance || rect.bottom > image.bottom + tolerance) {
                    problems.push('gallery message or source is clipped by the photograph');
                }
            }
        }
        return [...new Set(problems)].slice(0, 18);
    }""")
    require(not issues, "; ".join(issues))


def touch_targets(page, scope="body"):
    issues = page.locator(scope).evaluate("""root => {
        const selectors = '.button, .menu-toggle, .video-toggle, .round-button, .social-links a, .hero-scroll, #copy-link, #mobile-nav a';
        return [...root.querySelectorAll(selectors)].filter(element =>
            element.getClientRects().length && getComputedStyle(element).visibility !== 'hidden'
        ).flatMap(element => {
            const rect = element.getBoundingClientRect();
            return rect.width < 43.5 || rect.height < 43.5 ?
                [`${element.id || element.className || element.textContent}: ${rect.width.toFixed(1)}×${rect.height.toFixed(1)}`] : [];
        });
    }""")
    require(not issues, "Controls smaller than 44×44 CSS pixels: " + "; ".join(issues))


def reachable(locator):
    """An actual hit test catches overlays and scroll clipping."""
    return locator.evaluate("""element => {
        const rect = element.getBoundingClientRect();
        const x = (rect.left + rect.right) / 2;
        const y = (rect.top + rect.bottom) / 2;
        const hit = document.elementFromPoint(x, y);
        return rect.left >= -1 && rect.top >= -1 &&
            rect.right <= innerWidth + 1 && rect.bottom <= innerHeight + 1 &&
            !!hit && (hit === element || element.contains(hit));
    }""")


def mobile_navigation(page):
    toggle = page.locator(".menu-toggle")
    if not toggle.is_visible():
        require(not page.locator("#mobile-nav").is_visible(), "Mobile menu visible in desktop navigation")
        return
    top(page)
    toggle.click()
    nav = page.locator("#mobile-nav")
    require(nav.is_visible(), "Menu did not open")
    require(toggle.get_attribute("aria-expanded") == "true", "Menu expanded state not announced")
    bounds = nav.bounding_box()
    require(bounds and bounds["y"] >= 0 and bounds["y"] + bounds["height"] <= page.viewport_size["height"] + 1,
            "Navigation extends below viewport instead of scrolling")
    touch_targets(page, ".site-header")
    for link in nav.locator("a").all():
        link.scroll_into_view_if_needed()
        require(reachable(link), f"Menu item clipped or obscured: {link.inner_text()}")
    page.keyboard.press("Escape")
    require(not nav.is_visible(), "Escape did not close mobile navigation")
    top(page)
    toggle.click()
    nav.locator('a[href="#help"]').click()
    require(not nav.is_visible(), "Following mobile navigation did not close it")
    require(page.url.endswith("#help"), "Mobile navigation did not reach help anchor")
    top(page)


def dialog_check(page, trigger, selector):
    page.locator(trigger).click()
    dialog = page.locator(selector)
    require(dialog.is_visible(), f"{selector} did not open")
    settle(page)
    result = dialog.evaluate("""element => {
        const rect = element.getBoundingClientRect();
        return {left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom,
            width: innerWidth, height: innerHeight, scrollWidth: element.scrollWidth,
            clientWidth: element.clientWidth, scrollHeight: element.scrollHeight,
            clientHeight: element.clientHeight};
    }""")
    require(result["left"] >= -1 and result["right"] <= result["width"] + 1 and
            result["top"] >= -1 and result["bottom"] <= result["height"] + 1,
            f"{selector} extends outside viewport: {result}")
    require(result["scrollWidth"] <= result["clientWidth"] + 1,
            f"{selector} content requires horizontal scrolling")
    close = dialog.locator("[data-close]")
    require(reachable(close), f"{selector} close control clipped or obscured on opening")
    touch_targets(page, selector)
    if result["scrollHeight"] > result["clientHeight"] + 2:
        dialog.evaluate("element => element.scrollTo({top: element.scrollHeight, behavior: 'instant'})")
        settle(page)
        require(dialog.evaluate("element => element.scrollTop > 0 && element.scrollTop + element.clientHeight >= element.scrollHeight - 2"),
                f"{selector} cannot scroll to its end")
    # Every control/content region can be brought back into view, including close.
    last = dialog.locator(".dialog-note, .share-options, .lightbox-caption").last
    last.scroll_into_view_if_needed()
    require(last.evaluate("""element => {
        const rect = element.getBoundingClientRect();
        const dialog = element.closest('dialog').getBoundingClientRect();
        return rect.bottom <= dialog.bottom + 1 && rect.bottom > dialog.top;
    }"""), f"{selector} final content remains clipped after scrolling")
    close.scroll_into_view_if_needed()
    require(reachable(close), f"{selector} close control cannot be reached after scrolling")
    close.click()
    require(not dialog.is_visible(), f"{selector} close button failed")
    # Native close() hides the dialog synchronously, then queues its close event;
    # the event handler restores page scrolling on that following browser task.
    page.wait_for_function("!document.body.classList.contains('modal-open')", timeout=1000)


def count_is_valid(page):
    value = page.locator("#gallery-count").inner_text().strip()
    parts = value.split("/")
    require(len(parts) == 2 and all(part.strip().isdigit() for part in parts),
            f"Invalid gallery counter: {value!r}")
    current, total = map(int, parts)
    require(total == page.locator(".gallery-card").count() and 1 <= current <= total,
            f"Gallery counter outside photo range: {value!r}")
    require(page.locator("#gallery-progress-bar").evaluate("element => !element.style.transform.includes('NaN')"),
            "Gallery progress contains NaN")


def scroll_gallery(page, end=False):
    gallery = page.locator("#gallery")
    expected = gallery.evaluate("""(element, end) => {
        const cards = [...element.querySelectorAll('.gallery-card')];
        const stride = cards[1].offsetLeft - cards[0].offsetLeft;
        const max = Math.max(0, element.scrollWidth - element.clientWidth);
        const target = end ? max : Math.min(stride, max);
        element.scrollTo({left: target, behavior: 'instant'});
        return {target, index: Math.round(target / stride) + 1};
    }""", end)
    # Native scrolling is the same event path used by a finger swipe. Do not
    # synthesize scrollend: a browser compatibility regression should fail here.
    page.wait_for_function("""expected => {
        const gallery = document.querySelector('#gallery');
        const count = Number(document.querySelector('#gallery-count').textContent.split('/')[0]);
        return Math.abs(gallery.scrollLeft - expected.target) < 2 && count === expected.index;
    }""", arg=expected, timeout=4000)
    count_is_valid(page)


def orientation_and_gallery(page):
    for width, height in [(390, 844), (844, 390), (768, 1024), (1440, 900), (280, 653), (390, 844)]:
        page.set_viewport_size({"width": width, "height": height})
        settle(page)
        gallery = page.locator("#gallery")
        gallery.scroll_into_view_if_needed()
        count_is_valid(page)
        page.locator("#gallery-next").click()
        settle(page)
        count_is_valid(page)
        # Reset with the native scroll path before checking next-slide and end.
        gallery.evaluate("element => element.scrollTo({left: 0, behavior: 'instant'})")
        page.wait_for_function("Number(document.querySelector('#gallery-count').textContent.split('/')[0]) === 1")
        scroll_gallery(page)
        scroll_gallery(page, end=True)
        gallery.focus()
        page.keyboard.press("ArrowLeft")
        settle(page)
        count_is_valid(page)
        geometry(page)


class Audit:
    def __init__(self, output, browser_name):
        self.output = output / browser_name
        self.output.mkdir(parents=True, exist_ok=True)
        self.results = []

    def check(self, name, callback, page=None):
        try:
            callback()
            self.results.append({"check": name, "result": "PASS"})
        except (AssertionError, Error) as error:
            self.results.append({"check": name, "result": "FAIL", "error": str(error)})
            print(f"FAIL {self.output.name}/{name}: {error}", flush=True)
            if page and not page.is_closed():
                try:
                    page.screenshot(path=str(self.output / (name.replace("/", "-") + "-failure.png")))
                    page.evaluate("document.querySelectorAll('dialog[open]').forEach(dialog => dialog.close())")
                    page.keyboard.press("Escape")
                except Error:
                    pass

    def screenshot(self, page, name, full_page=False):
        top(page)
        page.screenshot(path=str(self.output / f"{name}.png"), full_page=full_page)


def context_for(browser, browser_name, width, height, **overrides):
    options = dict(viewport={"width": width, "height": height}, device_scale_factor=1,
                   has_touch=width <= 1024, reduced_motion="reduce")
    # Firefox has touch support but Playwright does not implement is_mobile.
    if browser_name != "firefox":
        options["is_mobile"] = width <= 1024
    options.update(overrides)
    return browser.new_context(**options)


def browser_suite(browser, browser_name, base, output, text_only=False):
    audit = Audit(output, browser_name)
    script_errors = []
    video_requests = []
    for name, width, height in ([] if text_only else PROFILES):
        context = context_for(browser, browser_name, width, height)
        page = context.new_page()
        page.on("pageerror", lambda error, profile=name: script_errors.append(f"{profile}: {error}"))
        page.on("request", lambda request: video_requests.append(request.url)
                if request.resource_type == "media" or ".mp4" in request.url else None)
        try:
            load(page, base)
            audit.check(f"{name}/layout", lambda: geometry(page), page)
            audit.check(f"{name}/targets", lambda: touch_targets(page), page)
            audit.check(f"{name}/navigation", lambda: mobile_navigation(page), page)
            for trigger, selector in [("#sources-open", "#sources-dialog"),
                                      ("#share-open", "#share-dialog"),
                                      ('[data-slide="0"]', "#lightbox")]:
                audit.check(f"{name}/{selector[1:]}",
                            lambda t=trigger, s=selector: dialog_check(page, t, s), page)
            if name in SCREENSHOT_PROFILES:
                audit.screenshot(page, name)
            if name == "phone-390":
                page.evaluate("document.querySelectorAll('img').forEach(image => image.loading = 'eager')")
                page.wait_for_function("Array.from(document.images).filter(image => image.getAttribute('src')).every(image => image.complete && image.naturalWidth > 0)")
                audit.screenshot(page, name + "-full", full_page=True)
        except (AssertionError, Error) as error:
            audit.check(f"{name}/setup", lambda error=error: require(False, str(error)), page)
        finally:
            context.close()
        print(f"Checked {browser_name}: {name} ({width}×{height})", flush=True)

    for width, height in ZOOM_PROFILES:
        context = context_for(browser, browser_name, width, height)
        page = context.new_page()
        page.on("pageerror", lambda error: script_errors.append(f"text zoom: {error}"))
        try:
            load(page, base)
            page.locator('.context-copy p').first.scroll_into_view_if_needed()
            original_text_size = page.locator(".context-copy p").first.evaluate("element => parseFloat(getComputedStyle(element).fontSize)")
            page.evaluate("document.documentElement.style.fontSize = '32px'")
            # WebKit can report pre-frame computed styles immediately after a
            # root font change. Measure the paragraph once it is in view.
            page.locator('.context-copy p').first.scroll_into_view_if_needed()
            page.wait_for_function("getComputedStyle(document.documentElement).fontSize === '32px'")
            settle(page)
            name = f"text-200-percent-{width}"
            enlarged_text_size = page.locator(".context-copy p").first.evaluate("element => parseFloat(getComputedStyle(element).fontSize)")
            audit.check(f"{name}/text-scales", lambda: require(enlarged_text_size >= original_text_size * 1.9,
                        f"Body text did not scale with the user's font setting: {original_text_size}px → {enlarged_text_size}px"), page)
            audit.check(f"{name}/layout", lambda: geometry(page), page)
            audit.check(f"{name}/navigation", lambda: mobile_navigation(page), page)
            for trigger, selector in [("#sources-open", "#sources-dialog"),
                                      ("#share-open", "#share-dialog"),
                                      ('[data-slide="0"]', "#lightbox")]:
                audit.check(f"{name}/{selector[1:]}",
                            lambda t=trigger, s=selector: dialog_check(page, t, s), page)
            if width == 390:
                audit.screenshot(page, name)
        finally:
            context.close()

    if text_only:
        audit.check("javascript/no-errors", lambda: require(not script_errors, "; ".join(script_errors)))
        return audit.results

    context = context_for(browser, browser_name, 390, 844)
    page = context.new_page()
    page.on("pageerror", lambda error: script_errors.append(f"orientation: {error}"))
    try:
        load(page, base)
        audit.check("orientation-and-native-gallery-scroll", lambda: orientation_and_gallery(page), page)
    finally:
        context.close()

    context = context_for(browser, browser_name, 320, 568)
    page = context.new_page()
    blocked_fonts = []

    def block_font(route):
        blocked_fonts.append(route.request.url)
        route.abort()

    page.route("**/assets/fonts/**", block_font)
    page.on("pageerror", lambda error: script_errors.append(f"font fallback: {error}"))
    try:
        load(page, base)
        audit.check("font-fallback/request-blocked", lambda: require(blocked_fonts, "Font fallback route was not exercised"), page)
        audit.check("font-fallback/layout", lambda: geometry(page), page)
        audit.check("font-fallback/navigation", lambda: mobile_navigation(page), page)
        audit.check("font-fallback/sharing", lambda: dialog_check(page, "#share-open", "#share-dialog"), page)
        audit.screenshot(page, "font-fallback-320")
    finally:
        context.close()

    audit.check("reduced-motion/no-video-download", lambda: require(not video_requests, f"Video fetched with reduced motion: {video_requests}"))
    audit.check("javascript/no-errors", lambda: require(not script_errors, "; ".join(script_errors)))
    return audit.results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default="http://127.0.0.1:5173")
    parser.add_argument("--browsers", nargs="+", choices=("chromium", "webkit", "firefox"), default=["chromium"])
    parser.add_argument("--output", type=Path, default=Path("/tmp/nepal-responsive-checks"))
    parser.add_argument("--text-only", action="store_true", help="rerun only the 200-percent text cases")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    profiles = [(f"text-200-percent-{w}", w, h) for w, h in ZOOM_PROFILES] if args.text_only else PROFILES
    report = {"base_url": args.base_url, "viewports": [{"name": n, "width": w, "height": h} for n, w, h in profiles],
              "browsers": {}}
    with sync_playwright() as playwright:
        for browser_name in dict.fromkeys(args.browsers):
            browser = None
            try:
                browser_type = getattr(playwright, browser_name)
                browser = browser_type.launch(headless=True, timeout=20000, **({"channel": "chrome"} if browser_name == "chromium" else {}))
                report["browsers"][browser_name] = browser_suite(browser, browser_name, args.base_url, args.output, args.text_only)
            except (AssertionError, Error) as error:
                report["browsers"].setdefault(browser_name, []).append({"check": "browser-suite", "result": "FAIL", "error": str(error)})
                print(f"FAIL {browser_name}: {error}", flush=True)
            finally:
                if browser:
                    browser.close()
    results = [item for checks in report["browsers"].values() for item in checks]
    report["passed"] = sum(item["result"] == "PASS" for item in results)
    report["failed"] = sum(item["result"] == "FAIL" for item in results)
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"result": "FAIL" if report["failed"] else "PASS", "passed": report["passed"],
                      "failed": report["failed"], "artifacts": str(args.output)}))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
