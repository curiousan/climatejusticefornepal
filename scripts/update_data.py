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
    Report("UN News / UNSDG",
           "https://unsdg.un.org/latest/stories/flood-ravaged-nepal-calls-climate-justice",
           "Flood-Ravaged Nepal Calls for Climate Justice", "2026-09-09",
           ("deaths", "missing")),
    Report("Associated Press",
           "https://apnews.com/article/54356ff1125e24493c003916e2280e03",
           "Nepal endured months of political upheaval", "2026-09-08",
           ("homes", "damage")),
)


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
        r"(?:26\s+August|August\s+26|Aug\.?\s+26)(?:,?\s+(20\d{2}))?", text, re.I)
    # This particular AP report uses a relative event reference. It is accepted
    # only alongside its configured title and exact publication date below.
    reviewed_relative_reference = (report.metrics == ("homes", "damage") and
                                  "flash floods two weeks ago" in text.casefold())
    if (not event_dates and not reviewed_relative_reference) or any(
            year and year != "2026" for year in event_dates):
        raise ValueError("The report does not match the 26 August 2026 event")
    # A page retrieval or dateModified timestamp is not a new statistical as-of date.
    if document.dates:
        if set(document.dates) != {report.published}:
            raise ValueError("Publication date changed; manual review required")
    else:
        expected = date.fromisoformat(report.published)
        date_pattern = rf"\b0?{expected.day}\s+{expected.strftime('%B')}\s+{expected.year}\b"
        if not re.search(date_pattern, text, re.I):
            raise ValueError("The reviewed publication date was not found")

    if report.metrics == ("deaths", "missing"):
        return {
            "deaths": unique_number(NUMBER + r"\s+people\s+(?:are\s+)?confirmed\s+dead\b", text),
            "missing": unique_number(NUMBER + r"\s+people\s+are\s+(?:still\s+)?missing\b", text),
        }

    # Require explicit additional homes; never sum potentially overlapping categories.
    homes_pattern = (NUMBER + r"\s+(?:homes|houses)\s+(?:were\s+|have\s+been\s+|are\s+)?"
                     r"(?:confirmed\s+)?destroyed.{0,180}?"
                     r"(?:another|an\s+additional)\s+(?:roughly\s+|about\s+)?" + NUMBER +
                     r"\s+(?:(?:homes|houses)\s+)?(?:need|require|requiring|needing)"
                     r".{0,45}?(?:rebuild|rebuilt|reconstruct)")
    home_matches = re.findall(homes_pattern, text, re.I)
    if len(home_matches) != 1:
        raise ValueError("Missing or ambiguous separate housing categories")
    homes = sum(int(value.replace(",", "")) for value in home_matches[0])
    if not 1 <= homes <= 1_000_000:
        raise ValueError("Housing total is outside the permitted range")
    damage_matches = set(re.findall(
        r"damage\s+estimate\s+(?:so\s+far\s+)?(?:of\s+)?\$([0-9]+(?:\.[0-9]+)?)\s+billion", text, re.I))
    if len(damage_matches) != 1:
        raise ValueError("Missing or ambiguous USD damage estimate")
    damage = int(Decimal(damage_matches.pop()) * 1_000_000_000)
    if not 1 <= damage <= 100_000_000_000:
        raise ValueError("Damage estimate is outside the permitted range")
    return {"homes": homes, "damage": damage}


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
    if set(snapshot["metrics"]) != {"deaths", "missing", "homes", "damage"}:
        raise ValueError("Snapshot must contain exactly the four displayed metrics")
    for metric in snapshot["metrics"].values():
        if type(metric["value"]) is not int or metric["value"] < 0:
            raise ValueError("Metric values must be nonnegative integers")
        for key in ("display", "label", "source", "note"):
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
    for report in REPORTS:
        try:
            values = parse_report(fetch(report.url), report)
            for key, value in values.items():
                metric = candidate["metrics"][key]
                if metric["url"] != report.url or metric["asOf"] != report.published:
                    raise ValueError("Snapshot uses a newer/different reviewed source; update the parser first")
                metric["value"] = value
                metric["display"] = (f"${value / 1_000_000_000:g}B" if key == "damage"
                                     else ("~" if key == "homes" else "") + f"{value:,}")
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
