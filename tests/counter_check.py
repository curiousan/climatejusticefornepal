"""Check the one-second visible counter deadline in Chrome, including slow frames.

Start python3 server.py, then run python3 tests/counter_check.py.
Requires Playwright and installed Google Chrome.
"""
import argparse
import json

from playwright.sync_api import sync_playwright


TRACE = """(() => {
    const frame = requestAnimationFrame.bind(window);
    window.counterTrace = {};
    function sample() {
        // Ignore the unstyled document while the stylesheet is still loading.
        if (!getComputedStyle(document.documentElement).getPropertyValue('--sans')) return;
        document.querySelectorAll('[data-count]').forEach(el => {
            const key = el.dataset.metric || el.dataset.count;
            const expected = `${el.dataset.prefix || ''}${Number(el.dataset.count).toLocaleString('en-US', {
                minimumFractionDigits: Number(el.dataset.decimals || 0),
                maximumFractionDigits: Number(el.dataset.decimals || 0)
            })}${el.dataset.suffix || ''}`;
            const trace = window.counterTrace[key] ||= {expected, visible: null, changes: []};
            const rect = el.getBoundingClientRect();
            const now = performance.now();
            if (trace.visible === null && rect.width && rect.height && rect.top < innerHeight && rect.bottom > 0)
                trace.visible = now;
            if (trace.changes.at(-1)?.text !== el.textContent)
                trace.changes.push({time: now, text: el.textContent});
        });
    }
    new MutationObserver(sample).observe(document, {subtree: true, childList: true, characterData: true});
    function watch() { sample(); frame(watch); }
    frame(watch);
})();"""

DELAY_FRAMES = """(() => {
    const frame = requestAnimationFrame.bind(window);
    window.requestAnimationFrame = callback => frame(time => {
        if (callback.name === 'tick') setTimeout(() => callback(performance.now()), 1400);
        else callback(time);
    });
})();"""


def wait_for_counter(page, key):
    page.wait_for_function("""key => {
        const trace = window.counterTrace[key];
        return trace?.changes.some(item => item.text !== trace.expected) &&
            trace.changes.at(-1).text === trace.expected;
    }""", arg=key, timeout=5000)


def check_case(browser, base, name, width, slowdown=1, delayed_frames=False):
    context = browser.new_context(viewport={"width": width, "height": 900})
    page = context.new_page()
    page.add_init_script(TRACE)
    if delayed_frames:
        page.add_init_script(DELAY_FRAMES)
    if slowdown != 1:
        context.new_cdp_session(page).send("Emulation.setCPUThrottlingRate", {"rate": slowdown})
    page.goto(base, wait_until="domcontentloaded")
    for key in ["0.37", "0.01"]:
        wait_for_counter(page, key)
    for key in ["deaths", "missing", "homes", "damage"]:
        page.locator(f'[data-metric="{key}"]').scroll_into_view_if_needed()
        wait_for_counter(page, key)
    traces = page.evaluate("window.counterTrace")
    timings = {}
    for key, trace in traces.items():
        start = next(i for i, change in enumerate(trace["changes"]) if change["text"] != trace["expected"])
        finish = next(change for change in trace["changes"][start + 1:] if change["text"] == trace["expected"])
        # Count from first visibility, or from animation start if it began offscreen.
        beginning = min(trace["visible"], trace["changes"][start]["time"])
        elapsed = finish["time"] - beginning
        assert 0 < elapsed <= 1000, f"{name}: {key} took {elapsed:.0f} ms from first visibility"
        timings[key] = round(elapsed)
    assert len(timings) == 6, f"{name}: did not exercise every counter"
    before = {key: len(trace["changes"]) for key, trace in traces.items()}
    page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    page.locator('.impact-grid').scroll_into_view_if_needed()
    page.wait_for_timeout(1500 if delayed_frames else 900)
    after = page.evaluate("Object.fromEntries(Object.entries(window.counterTrace).map(([key, trace]) => [key, trace.changes.length]))")
    assert before == after, f"{name}: a completed counter restarted"
    context.close()
    return {"case": name, "visible_to_final_ms": timings, "result": "PASS"}


def check_reduced_motion(browser, base):
    context = browser.new_context(reduced_motion="reduce")
    page = context.new_page()
    page.add_init_script(TRACE)
    page.goto(base, wait_until="networkidle")
    page.locator('.impact-grid').scroll_into_view_if_needed()
    traces = page.evaluate("window.counterTrace")
    assert len(traces) == 6
    assert all(change["text"] == trace["expected"] for trace in traces.values() for change in trace["changes"])
    context.close()
    return {"case": "reduced-motion", "result": "PASS"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:5173')
    args = parser.parse_args()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel='chrome', headless=True)
        try:
            for name, width, slowdown, delayed in [
                ('desktop', 1440, 1, False),
                ('mobile', 390, 1, False),
                ('desktop-slow-cpu', 1440, 4, False),
                ('mobile-slow-cpu', 390, 4, False),
                ('delayed-animation-frames', 390, 1, True),
            ]:
                print(json.dumps(check_case(browser, args.base_url, name, width, slowdown, delayed)), flush=True)
            print(json.dumps(check_reduced_motion(browser, args.base_url)), flush=True)
        finally:
            browser.close()


if __name__ == '__main__':
    main()
