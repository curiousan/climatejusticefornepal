# Climate Justice for Nepal

A responsive, single-page awareness site built with HTML, CSS, and vanilla JavaScript. It runs on a static host without a build step, framework, API keys, or a database.

## Preview locally

From this folder, run:

```sh
python3 server.py
```

Open the local address printed by the server. If Node.js is installed, `npm run dev` starts the same preview. Serve the files over HTTP: opening `index.html` as a local file prevents the browser from loading the JSON snapshot.

For optional browser checks, install the Python `playwright` package and Google Chrome. With the preview server running, use a second terminal:

```sh
python3 -m pip install playwright
python3 tests/browser_check.py
python3 tests/counter_check.py
python3 tests/carousel_check.py
```

The hero presents the population and historical CO₂ figures in two aligned rows over the muted video, with oversized gold and coral percentages, smaller serif supporting text, and each source directly beneath its figure. Both hero counters animate together within 1 second, using four decimal places during the climb and returning to two at completion; their reserved widths keep the sentence steady. Every counter uses the same 800 ms elapsed-time animation, leaving room for the final browser paint within one second. Counting starts on first intersection; a separate completion timer finalizes the number if animation frames are delayed. Active counters finish immediately when the page is hidden, and completed counters never restart on scroll. Counters animate once on entry; reduced-motion users see the final numbers immediately. Font sizes follow browser text preferences, controls have at least 44-pixel touch targets, and the menu, gallery, and dialogs adapt to narrow screens and landscape orientation.

For the extended viewport, 200% text, font-fallback, rotation, and dialog checks:

```sh
python3 tests/responsive_check.py
python3 -m playwright install webkit firefox
python3 tests/responsive_check.py --browsers chromium firefox webkit
```

These checks cover widths from 280 to 2560 CSS pixels. Browser emulation complements testing on physical devices; the available WebKit build depends on the operating system running the tests.

On macOS 14, Playwright 1.62's frozen WebKit build rejected its driver's `PushAPIEnabled` setting before opening any page. For WebKit checks on that OS, use a separate environment with `playwright==1.55.0` and its matching browser (`python3 -m playwright install webkit`). Chrome and Firefox can use the newer driver.

## Personalize and publish

The footer contact links and production sharing URL are configured in `site.config.js`. The production address is `https://climatejusticefornepal.org/`. If the domain changes, update `publicUrl`, the canonical URL, social metadata, and JSON-LD in `index.html`, plus `robots.txt` and `sitemap.xml` together. Upload `index.html`, `robots.txt`, `sitemap.xml`, `styles.css`, `app.js`, `carousel.js`, `site.config.js`, `assets`, `images`, `videos/aerial-loop.mp4`, `data/impact.json`, and `data/emission-contribution.json` to the host's public root; no Python process is needed in production. The Python server and refresh script are local maintenance tools.

The original supplied footage remains at `videos/aerial-video1.mp4`. The hero uses `videos/aerial-loop.mp4`, a smaller, silent 13-second extract starting at 1 second, with Associated Press credit. The starter gallery images are frames extracted from that supplied footage, not independently dated photographs. Their captions credit the supplied video without inventing a photographer or recording date.

The hero calls on major polluters to help repay their climate debt by supporting Nepal’s recovery. “The climate debt owed to Nepal” explains the 26 August collapse, how warming increases the risk of such disasters, and the case for compensation and recovery funding. The wording presents climate debt as a demand for responsibility; it does not assert that a court has awarded compensation or that climate change was the sole cause of this particular collapse. Links accompany the explanation to AP, Our World in Data, the UN report, and Al Jazeera’s analysis.

## Search visibility and GitHub Pages setup

The HTML includes the page title and description, canonical HTTPS URL, an indexing directive, `WebSite` and `WebPage` JSON-LD, and Open Graph and X/Twitter preview metadata. These are present without JavaScript. Social previews reuse the existing Reuters photograph; its credit is retained on the page and in the structured data. `robots.txt` allows crawling and points to the sitemap. The sitemap contains the single homepage; sections such as `#impact` are not separate pages. It intentionally omits `lastmod` rather than implying the content is refreshed on every deployment.

These files prepare the site for discovery but do not submit it to Google or fix hosting settings. Missing robots or sitemap files alone do not prevent indexing. Complete the following after publishing the changes.

### GitHub Pages and domain settings

1. Open [the repository's Pages settings](https://github.com/curiousan/climatejusticefornepal/settings/pages). Confirm the publishing source includes the updated files and the custom domain is `climatejusticefornepal.org`. For branch publishing, preserve the `CNAME` file GitHub creates in the publishing branch. For an Actions deployment, include the SEO files in the uploaded site artifact.
2. At the DNS provider, configure the `www` subdomain as a `CNAME` pointing to `curiousan.github.io` (without the repository path). Keep the working apex-domain records. GitHub Pages can then redirect `www` to the configured apex domain and provision the appropriate HTTPS certificate. Follow [GitHub's custom-domain instructions](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site).
3. In Pages settings, enable **Enforce HTTPS** once the certificate is ready. DNS and certificate provisioning can take time. If the option remains unavailable or `www` reports a certificate error, follow [GitHub's HTTPS troubleshooting instructions](https://docs.github.com/en/pages/getting-started-with-github-pages/securing-your-github-pages-site-with-https).
4. Verify that `http://climatejusticefornepal.org/`, `http://www.climatejusticefornepal.org/`, and `https://www.climatejusticefornepal.org/` redirect to `https://climatejusticefornepal.org/` without certificate errors. The final homepage must return HTTP 200. HTML canonical tags do not create these redirects.
5. Confirm [robots.txt](https://climatejusticefornepal.org/robots.txt) and [sitemap.xml](https://climatejusticefornepal.org/sitemap.xml) return HTTP 200 with the expected text/XML, and [the social preview image](https://climatejusticefornepal.org/images/nepal_flood_reuters.jpg) loads. View the homepage's source and confirm it contains the new title, canonical URL, and JSON-LD.

### Verify ownership and request Google indexing

1. Open [Google Search Console](https://search.google.com/search-console/welcome) using the Google account that will manage the site. Add a **Domain** property for `climatejusticefornepal.org` (without `https://` or a path).
2. Copy Google's exact verification TXT record into the domain's DNS settings, then select **Verify**. Keep that record after verification and preserve the website's existing DNS records. The verification value is account-specific; it is not included in this repository. See [Google's ownership-verification instructions](https://support.google.com/webmasters/answer/9008080).
3. Under **Sitemaps**, submit `https://climatejusticefornepal.org/sitemap.xml` after the deployed file is reachable. Check that Google can read it successfully.
4. Inspect `https://climatejusticefornepal.org/` using **URL Inspection**, run **Test live URL**, and review crawl/indexing eligibility. If eligible, select **Request indexing**. If Google reports a fetch, robots, or indexing problem, resolve that specific issue first.
5. Monitor **Page indexing** and **Performance**. URL Inspection can reveal whether Google knows the URL, when it last crawled it, and which canonical URL it selected. Search Console supplies the actual indexing diagnosis; a search for the domain alone does not.

Google can discover a site without Search Console, but verification provides diagnostics and access to indexing requests. Crawling can take days to weeks, and requests do not guarantee indexing or a particular ranking. See [Google's recrawl guidance](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl). The site-name JSON-LD follows [Google's site-name guidance](https://developers.google.com/search/docs/appearance/site-names), and sharing metadata follows the [Open Graph protocol](https://ogp.me/).

## Add carousel photographs

Put your pictures in `assets/images/carousel/`, then edit `data/emission-contribution.json`. Use a JSON array with one object per picture, in the order you want them to appear:

```json
[
  {
    "overlay_text": "The water recedes. The need for support doesn’t.",
    "source": "UNICEF · Nepal flood response",
    "source link": "https://www.unicef.org/emergencies/nepal-flood",
    "image": "your-photo.jpg",
    "image_caption": "Add the location, date, context, and exact photographer credit here."
  }
]
```

`overlay_text` appears in large, bold type over the picture. Keep it to a short, impactful message and link factual claims to evidence using `source` and the exact key `source link` (with a space). `image_caption` appears in small type below the photograph and in its expanded view; include the actual photographer credit and context supplied with that image. Text is displayed literally, so no HTML is needed.

`image` can be a filename relative to `assets/images/carousel/`, a path beginning `assets/images/carousel/` or `images/carousel/`, or an HTTPS image URL. JPG, PNG, WebP, and AVIF images work in current browsers. Text fields can be empty, but each entry needs an image. A single object is also accepted for a one-photo carousel. The entries in `data/emission-contribution.json` can be replaced or extended; no JavaScript changes are needed. Image filenames resolve against `assets/images/carousel/` even though the JSON lives in `data/`. The list reloads on a page refresh.

The five current overlays compare Nepal with U.S. and German national averages, China’s annual emissions rate, a typical U.S. petrol car, and global historical emissions. Each source label identifies the comparison period and measure. The Sources & transparency dialog records the calculations: Nepal 0.63 tonnes/person/year; U.S. 14.2 (about 16 days for Nepal’s annual average); Germany 6.77 (about 11 times Nepal); China 12.3 billion tonnes/year versus Nepal’s 232 million tonnes cumulatively (about 6.9 days at China’s 2024 rate); and EPA’s 4.6 tonnes/year of vehicle tailpipe CO₂ (about 7.3 times Nepal’s per-person average). These are calculations from rounded 2024 figures, with historical totals through 2024. Country data cover territorial fossil-fuel and industry CO₂, not all greenhouse gases or the measured footprints of people in the photographs. The three HTML fallback slides use the approved historical, U.S., and China comparisons with their original credited photographs.

The carousel shows one card at a time and advances every seven seconds while visible. Visitors can use arrows, dots, swipes, or keyboard arrows, and pause or resume the slideshow. Automatic movement pauses while reading with the mouse or keyboard, when offscreen, and in a background tab. Reduced-motion visitors start with autoplay paused and can opt in using Play. Set `carousel.intervalMs` in `site.config.js` to change the timing, `carousel.dataUrl` to use a different JSON filename, or `carousel.imageBaseUrl` to change the image folder. One-photo lists have autoplay and navigation disabled; longer lists use a dynamic count, with dots shown for up to eight photographs.

A missing or invalid JSON file retains the credited starter slides from `index.html`. If JavaScript is disabled, those same slides remain available by scrolling. Keep their three image files in `images/carousel/` if you want that fallback; update the fallback markup alongside the JSON when replacing it completely. Missing individual images show a neutral background while preserving the overlay, source, and supplied credit.

## Sources and dates

`data/impact.json` is the saved, reviewed impact snapshot. Each metric includes its own source link, report date (`asOf`), display label, and qualification. `verifiedAt` records verification of the complete snapshot, not the disaster's current status. The website must retain the individual report dates when it loads or caches the file.

The initial snapshot uses [UN News / UNSDG, 9 September 2026](https://unsdg.un.org/latest/stories/flood-ravaged-nepal-calls-climate-justice) for confirmed deaths and missing people, and [Associated Press, 8 September 2026](https://apnews.com/article/54356ff1125e24493c003916e2280e03) for homes and preliminary damage. The housing total is approximate and combines destroyed homes with the separately reported additional homes needing rebuilding. These reports concern the 26 August 2026 floods; they are not a live incident feed.

The site compares the preliminary **$2.56 billion** damage estimate with the World Bank's **$42.91 billion** figure for Nepal's 2024 GDP: 2.56 ÷ 42.914 × 100 = **5.97%**, displayed as approximately **6.0%**. This communicates scale; it is not a claim that 6% of the economy was destroyed. The event explanation follows Associated Press reporting that researchers identified a high-altitude collapse involving bedrock and glacier ice as the trigger. It explains how warming-related ice melt and permafrost thaw destabilize steep mountain slopes and make destructive collapses more likely.

The photograph behind “A stark example of climate injustice” is `images/nepal_flood_reuters.jpg` and is credited on the page to REUTERS/Navesh Chitrakar.

The population comparison is **0.37%**, calculated from the [Our World in Data population dataset](https://ourworldindata.org/grapher/population): Nepal 29,694,614 / world 8,091,734,933 × 100, both for 2023. This replaces the draft's 0.35% with a reproducible, dated figure. The **0.01%** figure refers to Nepal's share of cumulative fossil fuel and industry CO₂ emissions since 1751 through 2024, from the [Our World in Data Nepal CO₂ profile](https://ourworldindata.org/profile/co2/nepal). It is not a claim about all greenhouse gases or land-use emissions.

## Refresh the impact snapshot

Python 3.9 or later is sufficient; no packages are required:

```sh
python3 scripts/update_data.py --check
python3 scripts/update_data.py
python3 -m unittest discover -s tests -v
```

`--check` downloads and validates the configured reports without writing. The default command replaces `data/impact.json` atomically only after **both** reports validate. An HTTP error, missing metric, ambiguous number, changed publication date, different event, or unexpected report content leaves the entire saved snapshot and its dates untouched and returns a nonzero exit code. A successful retrieval never promotes the report's `asOf` date to today's date. An explicit `dateModified` timestamp is also ignored because a page edit does not necessarily update its statistics.

The UN page returned HTTP 403 during implementation, and direct AP retrieval was also unavailable. Search-indexed report content supported the initial manual verification. Automatic refresh against those sites could not be verified in this environment; the saved snapshot remains usable when they block a request. The parser is intentionally conservative, with synthetic offline tests for its accepted wording and failure behavior. Run `--check` from your deployment environment before relying on scheduled refreshes.

The browser caches the delivered JSON for 15 minutes; that interval does **not** mean the underlying reports update every 15 minutes. The updater fetches only the two reviewed URLs in `scripts/update_data.py`. It does not discover new reports. For newer reporting, review the event, figures, date, and definitions first, then update the report configuration/parser and `data/impact.json` together. Alternatively, edit the JSON snapshot directly after manual source review, including all per-metric source dates and notes; the updater refuses to overwrite newer or differently sourced metrics until its configuration is updated too. Keep a copy of the previous reviewed snapshot in version control.

Deploy the revised `data/impact.json` after a successful refresh. For useful cache behavior on your host, configure that file with `Cache-Control: no-cache`; the browser's local 15-minute cache still limits repeat loads. Scheduling the Python command is optional and belongs in the host or CI configuration, not the visitor's browser.
