"""Optional browser smoke checks: pip install playwright; uses installed Chrome."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = 'http://127.0.0.1:5173'
OUTPUT = Path('/tmp/nepal-site-checks')
OUTPUT.mkdir(exist_ok=True)


def track_hero_counters(page):
    """Observe the real animation from startup, including its final precision change."""
    page.add_init_script("""(() => {
        window.heroCounterTrace = [];
        let previous = '';
        new MutationObserver(() => {
            const counters = [...document.querySelectorAll('.hero-number [data-count]')];
            if (counters.length !== 2) return;
            const text = counters.map(element => element.textContent);
            if (text.join('|') === previous) return;
            previous = text.join('|');
            window.heroCounterTrace.push({time: performance.now(), text,
                widths: counters.map(element => element.closest('.hero-number').getBoundingClientRect().width),
                overflow: counters.map(element => element.getBoundingClientRect().width -
                    element.closest('.hero-counter-value').getBoundingClientRect().width)});
        }).observe(document, {subtree: true, childList: true, characterData: true});
    })();""")


def check_hero_counters(page):
    page.wait_for_function("""() => {
        const trace = window.heroCounterTrace;
        return trace.some(sample => sample.text.some(text => /^0\\.\\d{4}$/.test(text))) &&
            trace.at(-1)?.text.join('|') === '0.37|0.01';
    }""", timeout=8000)
    trace = page.evaluate('window.heroCounterTrace')
    start = next(index for index, sample in enumerate(trace)
                 if any(len(value.partition('.')[2]) == 4 for value in sample['text']))
    animation = trace[start:]
    duration = animation[-1]['time'] - animation[0]['time']
    assert 850 <= duration <= 1250, f'Hero counters should finish in about 1 second, took {duration:.0f}ms'
    finish_times = []
    for index, final_value in enumerate([0.37, 0.01]):
        values = [float(sample['text'][index]) for sample in animation]
        assert all(before <= after for before, after in zip(values, values[1:])), 'Hero counter runs backward'
        assert values[-1] == final_value
        assert len(set(values)) >= 8, 'Hero counter needs visible intermediate steps'
        finish = next(sample['time'] for sample in animation if float(sample['text'][index]) == final_value)
        assert finish - animation[0]['time'] >= 850, 'Hero counter reaches its final value early'
        finish_times.append(finish)
        widths = [sample['widths'][index] for sample in animation]
        assert max(widths) - min(widths) <= 1, 'Hero number width changes during counting'
        assert all(sample['overflow'][index] <= 1 for sample in animation), 'Intermediate digits exceed their reserved width'
    assert all(len(value.partition('.')[2]) == 2 for value in animation[-1]['text']), 'Final figures need two decimal places'
    assert max(finish_times) - min(finish_times) <= 50, 'Hero counters finish on different animation frames'


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(channel='chrome', headless=True)
    failures = []
    desktop = browser.new_context(viewport={'width': 1440, 'height': 1000}, device_scale_factor=1)
    page = desktop.new_page()
    page.on('pageerror', lambda error: failures.append(str(error)))
    track_hero_counters(page)
    page.goto(BASE, wait_until='networkidle')
    check_hero_counters(page)
    page.wait_for_function('document.querySelector("#gallery").dataset.activeIndex !== undefined')
    page.evaluate('document.fonts.ready')
    page.evaluate('document.querySelectorAll("img").forEach(image => image.loading = "eager")')
    page.wait_for_function('Array.from(document.images).filter(image => image.getAttribute("src")).every(image => image.complete && image.naturalWidth > 0)')
    page.wait_for_timeout(1600)
    assert page.title().startswith('Climate Justice for Nepal')
    assert page.locator('h1').count() == 1
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Desktop horizontal overflow'
    assert page.locator('[data-metric="deaths"]').inner_text() == '1,367'
    assert page.locator('#hero-title .hero-number [data-count]').count() == 2
    assert page.locator('#hero-title').get_attribute('aria-label') or 'Did you know' in page.locator('#hero-title').inner_text()
    assert page.locator('.hero + #impact').count() == 1
    page.locator('[data-metric="deaths"]').scroll_into_view_if_needed()
    page.wait_for_function('document.querySelector("[data-metric=deaths]").textContent !== "1,367"')
    page.wait_for_function('document.querySelector("[data-metric=deaths]").textContent === "1,367"')
    page.wait_for_function('document.querySelector("[data-metric=damage]").textContent === "$2.56B"')
    assert '6.0% of Nepal’s 2024 GDP' in page.locator('[data-metric="damage"]').locator('xpath=..').inner_text()
    page.evaluate('window.scrollTo({top: 0, behavior: "instant"})')
    assert page.locator('a.donate-link').count() == 4
    assert page.locator('a.donate-link[href="https://rescue.opmcm.gov.np/offer-help"]').count() == 1
    assert page.evaluate('Array.from(document.images).filter(image => image.getAttribute("src")).every(image => image.complete && image.naturalWidth > 0)')
    page.screenshot(path=str(OUTPUT / 'desktop.png'), full_page=True)
    page.locator('#sources-open').click()
    assert page.locator('#sources-dialog').is_visible()
    page.keyboard.press('Escape')
    assert not page.locator('#sources-dialog').is_visible()
    page.locator('#gallery-next').click()
    page.wait_for_timeout(700)
    assert page.locator('#gallery').evaluate('(element) => element.scrollLeft > 0')
    page.locator('[data-slide="1"]').click()
    first_photo = page.locator('#lightbox-image').get_attribute('src')
    page.keyboard.press('ArrowRight')
    assert page.locator('#lightbox-image').get_attribute('src') != first_photo
    page.keyboard.press('Escape')
    page.locator('#share-open').click()
    assert page.locator('#share-dialog').is_visible()
    page.evaluate("Object.defineProperty(navigator, 'clipboard', {value: {writeText: async (text) => window.copiedText = text}, configurable: true})")
    page.locator('#copy-link').click()
    assert page.evaluate('window.copiedText') == BASE + '/'
    page.locator('#copy-message').click()
    assert '0.01%' in page.evaluate('window.copiedText')
    page.keyboard.press('Escape')
    contact_links = page.locator('[data-contact]')
    assert contact_links.evaluate_all('(links) => links.map(link => link.dataset.contact)') == ['instagram', 'linkedin', 'email', 'facebook']
    assert contact_links.evaluate_all('(links) => links.map(link => link.getAttribute("href"))') == [
        'https://www.instagram.com/curiousanx/',
        'https://www.linkedin.com/in/curiousan/',
        'mailto:curious.sandesh@gmail.com',
        'https://www.facebook.com/profile.php?id=100053470772404',
    ]
    assert page.locator('[data-contact][aria-disabled="true"]').count() == 0
    assert page.locator('.event-narrative').get_by_text('Wednesday, 26 August 2026', exact=False).count() == 1
    assert page.locator('.context-statement img').get_attribute('src') == 'images/nepal_flood_reuters.jpg'
    assert 'REUTERS/Navesh Chitrakar' in page.locator('.context-statement figcaption').inner_text()
    page.locator('#video-toggle').scroll_into_view_if_needed()
    page.wait_for_function('!document.querySelector("#hero-video").paused')
    page.locator('#video-toggle').click()
    page.wait_for_timeout(100)
    assert page.locator('#hero-video').evaluate('(video) => video.paused')

    mobile = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=1, is_mobile=True, has_touch=True, reduced_motion='reduce')
    phone = mobile.new_page()
    phone.on('pageerror', lambda error: failures.append(str(error)))
    track_hero_counters(phone)
    phone.goto(BASE, wait_until='networkidle')
    phone.wait_for_function('document.querySelector("#gallery").dataset.activeIndex !== undefined')
    phone.evaluate('document.querySelectorAll("img").forEach(image => image.loading = "eager")')
    phone.wait_for_function('Array.from(document.images).filter(image => image.getAttribute("src")).every(image => image.complete && image.naturalWidth > 0)')
    assert phone.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile horizontal overflow'
    assert phone.locator('#hero-video').evaluate('(video) => video.paused && !video.getAttribute("src")')
    assert phone.locator('.hero-number [data-count]').all_text_contents() == ['0.37', '0.01']
    assert all(sample['text'] == ['0.37', '0.01'] for sample in phone.evaluate('window.heroCounterTrace')), 'Reduced motion animates the hero numbers'
    phone.screenshot(path=str(OUTPUT / 'mobile.png'), full_page=True)
    phone.locator('.menu-toggle').click()
    assert phone.locator('#mobile-nav').is_visible()
    phone.locator('#mobile-nav a[href="#help"]').click()
    assert not phone.locator('#mobile-nav').is_visible()
    assert phone.url.endswith('#help')
    phone.locator('#gallery-next').click()
    assert phone.locator('#gallery').evaluate('(element) => element.scrollLeft > 0')
    for width in [320, 375, 768, 1024, 1920]:
        phone.set_viewport_size({'width': width, 'height': 900})
        assert phone.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Overflow at {width}px'

    offline = browser.new_context(reduced_motion='reduce')
    fallback = offline.new_page()
    fallback.route('**/data/impact.json', lambda route: route.abort())
    fallback.goto(BASE, wait_until='networkidle')
    assert fallback.locator('[data-metric="deaths"]').inner_text() == '1,367'
    assert 'temporarily unavailable' in fallback.locator('#data-status').inner_text()
    malformed = browser.new_context(reduced_motion='reduce')
    invalid = malformed.new_page()
    snapshot = json.loads(Path('data/impact.json').read_text())
    snapshot['metrics']['deaths']['asOf'] = '2026-02-31'
    invalid.route('**/data/impact.json', lambda route: route.fulfill(json=snapshot))
    invalid.goto(BASE, wait_until='networkidle')
    assert invalid.locator('[data-metric="deaths"]').inner_text() == '1,367'
    assert 'temporarily unavailable' in invalid.locator('#data-status').inner_text()
    nojs = browser.new_context(java_script_enabled=False)
    static = nojs.new_page()
    static.goto(BASE)
    assert static.locator('[data-metric="missing"]').inner_text() == '5,132'
    assert static.locator('a.donate-link').count() == 4
    assert static.locator('#gallery .gallery-card').count() == 3
    assert static.locator('#gallery .gallery-card h3').first.inner_text().strip()
    assert not failures, failures
    print(json.dumps({'result': 'PASS', 'screenshots': str(OUTPUT), 'browser_errors': failures, 'viewports': [320, 375, 390, 768, 1024, 1440, 1920]}))
    browser.close()
