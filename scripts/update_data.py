#!/usr/bin/env python3
"""Refresh the reviewed reports only; leave the snapshot untouched on failure."""

import argparse
import copy
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
EVENT = "Nepal floods · 26 August 2026"
NUMBER = r"(\d{1,3}(?:,\d{3})+|\d+)"


@dataclass(frozen=True)
class Report:
    name: str
    url: str
    title: str
    published: str
    metrics: tuple


REPORTS = (
    Report("NDRRMA / Ministry of Finance",
           "https://mofnepal.github.io/rasuwa-flood-update/en/rescue/",
           "NDRRMA – Rasuwa Flood: Search, Rescue and Relief Update", "2026-09-19",
           ("deaths", "missing", "injured", "rescued")),
    Report("Nepal Red Cross / RDNA", "https://nrcs.org/highlight/9/",
           "Rasuwa Flood Situation Update 8", "2026-09-13", ("homes",)),
    Report("Government of Nepal / MoFA",
           "https://mofa.gov.np/content/1884/the-ministry-s-regular-press-briefing--11-september/",
           "The Ministry's regular Press Briefing- 11 September 2026", "2026-09-11",
           ("damage", "losses", "recovery")),
)
METRICS = {key for report in REPORTS for key in report.metrics}



class ReportHTML(HTMLParser):
    """Keep visible text and publication metadata, excluding scripts and navigation."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.dates = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "meta":
            key = attrs.get("property", attrs.get("name", "")).lower()
            if key in {"article:published_time", "datepublished", "pubdate", "date"}:
                self.dates.append(attrs.get("content", "")[:10])
        if tag in {"script", "style", "nav", "footer"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "footer"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def unique_number(pattern, text, minimum=1, maximum=1_000_000):
    matches = {int(value.replace(",", ""))
               for value in re.findall(pattern, text, re.I)}
    if len(matches) != 1:
        raise ValueError("Missing or ambiguous metric in reviewed report")
    value = matches.pop()
    if not minimum <= value <= maximum:
        raise ValueError("Metric is outside the permitted range; manual review required")
    return value


def parse_report(html, report):
    document = ReportHTML()
    document.feed(html)
    text = re.sub(r"\s+", " ", " ".join(document.parts))
    if report.title.casefold() not in text.casefold():
        raise ValueError("The expected report title was not found")
    if not re.search(r"\bNepal\b", text, re.I) or not re.search(r"\bfloods?\b", text, re.I):
        raise ValueError("The report is not about the Nepal floods")
    event_dates = re.findall(
        r"(?:26\s+Aug(?:ust)?|August\s+26|Aug\.?\s+26)(?:,?\s+(20\d{2}))?", text, re.I)
    if not event_dates or any(year and year != "2026" for year in event_dates):
        raise ValueError("The report does not match the 26 August 2026 event")

    expected = date.fromisoformat(report.published)
    if report.metrics == ("deaths", "missing", "injured", "rescued"):
        # The portal header's update time is not the selected situation report's date.
        heading = re.escape(report.title) + r"\s+·\s+[^·]+·\s+(\d{1,2} [A-Za-z]+ \d{4})"
        dates = set(re.findall(heading, text))
        if dates != {f"{expected.day} {expected.strftime('%b')} {expected.year}"}:
            raise ValueError("Rescue report date changed; manual review required")
        text = text.split(report.title, 1)[1].split("Nepal Police –", 1)[0]
        # Keep treatment categories separate; the portal sum is not a unique injury toll.
        return {
            "deaths": unique_number(r"\bCasualties\s+" + NUMBER, text),
            "missing": unique_number(r"\bMissing\s+" + NUMBER + r"\s+Rasuwa", text),
            "injured": unique_number(r"Treated by the security agencies\s+" + NUMBER, text),
            "rescued": unique_number(r"\bRescued\s+" + NUMBER + r"\s+Helicopter", text),
        }

    if report.metrics == ("homes",):
        heading = f"{report.title} ({expected.day} {expected.strftime('%B')} {expected.year})"
        if heading not in text:
            raise ValueError("The reviewed housing report date was not found")
        text = text.rsplit(heading, 1)[1].split("Rasuwa Flood Response 2026", 1)[0]
        return {"homes": unique_number(NUMBER + r"\s+private buildings has been damaged", text)}

    if document.dates and set(document.dates) != {report.published}:
        raise ValueError("Publication date changed; manual review required")
    if not re.search(rf"\b{expected.day}\s+{expected.strftime('%B')}\s+{expected.year}\b", text):
        raise ValueError("The reviewed publication date was not found")
    values = {}
    patterns = {
        "damage": (r"total damage caused by the disaster is estimated at approximately USD ([0-9.]+) billion", 1_000_000_000),
        "losses": (r"estimated loss is approximately USD ([0-9.]+) million", 1_000_000),
        "recovery": (r"total estimated requirement for reconstruction is approximately USD ([0-9.]+) billion", 1_000_000_000),
    }
    for key, (pattern, multiplier) in patterns.items():
        matches = set(re.findall(pattern, text, re.I))
        if len(matches) != 1:
            raise ValueError(f"Missing or ambiguous {key} estimate")
        amount = Decimal(matches.pop()) * multiplier
        if amount != amount.to_integral_value() or not 1 <= amount <= 100_000_000_000:
            raise ValueError("USD estimate is outside the permitted range")
        values[key] = int(amount)
    return values


def fetch_report(url):
    request = Request(url, headers={
        "User-Agent": "ClimateJusticeForNepal/1.0 (public report verification)",
        "Accept": "text/html",
    })
    with urlopen(request, timeout=20) as response:
        if response.headers.get_content_type() != "text/html":
            raise ValueError("Expected an HTML report")
        body = response.read(4_000_001)
        if len(body) > 4_000_000:
            raise ValueError("Report exceeds the download limit")
        return body.decode(response.headers.get_content_charset() or "utf-8")


def validate_snapshot(snapshot):
    if snapshot.get("event") != EVENT:
        raise ValueError("Snapshot event does not match")
    date.fromisoformat(snapshot["verifiedAt"])
    if set(snapshot["metrics"]) != METRICS:
        raise ValueError("Snapshot must contain exactly the eight displayed metrics")
    gdp = snapshot["gdp"]
    if type(gdp["value"]) is not int or gdp["value"] <= 0 or type(gdp["year"]) is not int:
        raise ValueError("Invalid GDP comparison baseline")
    if not gdp["url"].startswith("https://"):
        raise ValueError("GDP needs an HTTPS source URL")
    for metric in snapshot["metrics"].values():
        if metric["unit"] not in {"count", "USD"}:
            raise ValueError("Unknown metric unit")
        if type(metric["value"]) is not int or metric["value"] < 0:
            raise ValueError("Metric values must be nonnegative integers")
        for key in ("display", "label", "summary", "source", "note"):
            if not isinstance(metric[key], str) or not metric[key].strip():
                raise ValueError(f"Missing metric field: {key}")
        if not metric["url"].startswith("https://"):
            raise ValueError("Each metric needs an HTTPS source URL")
        if not "2026-08-26" <= metric["asOf"] <= snapshot["verifiedAt"]:
            raise ValueError("Invalid report date relative to event or verification")
        date.fromisoformat(metric["asOf"])


def atomic_write(path, snapshot):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, encoding="utf-8",
                                         suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            json.dump(snapshot, output, indent=2, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def refresh(path, check=False, fetch=fetch_report, today=None):
    """All reports must validate before any file is replaced. Returns success."""
    original = json.loads(path.read_text(encoding="utf-8"))
    validate_snapshot(original)
    candidate = copy.deepcopy(original)
    failures = []
    # Check source compatibility before accessing the network, so old parsers cannot
    # overwrite a newer manual review or silently leave new metrics unverified.
    for report in REPORTS:
        for key in report.metrics:
            metric = original["metrics"][key]
            if metric["url"] != report.url or metric["asOf"] != report.published:
                print("Snapshot uses a newer/different reviewed source; update the parser first", file=sys.stderr)
                return False
    for report in REPORTS:
        try:
            values = parse_report(fetch(report.url), report)
            for key, value in values.items():
                metric = candidate["metrics"][key]
                if metric["url"] != report.url or metric["asOf"] != report.published:
                    raise ValueError("Snapshot uses a newer/different reviewed source; update the parser first")
                metric["value"] = value
                metric["display"] = (f"${value / 1_000_000_000:.2f}B" if value >= 1_000_000_000
                                     else f"${value / 1_000_000:g}M") if metric["unit"] == "USD" else f"{value:,}"
            print(f"Verified {report.name}: report dated {report.published}")
        except (OSError, ValueError, UnicodeError) as error:
            failures.append(report.name)
            print(f"Could not verify {report.name}: {error}", file=sys.stderr)
    if failures:
        print("Saved snapshot and all dates preserved; refresh incomplete.", file=sys.stderr)
        return False
    candidate["verifiedAt"] = today or datetime.now(timezone.utc).date().isoformat()
    validate_snapshot(candidate)
    if check:
        print("Check complete; no files changed.")
    elif candidate != original:
        atomic_write(path, candidate)
        print(f"Updated {path}; individual report dates are unchanged.")
    else:
        print("Snapshot already matches the reviewed reports.")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify without writing any files")
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "impact.json")
    args = parser.parse_args()
    try:
        return 0 if refresh(args.data, check=args.check) else 1
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Snapshot not changed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
