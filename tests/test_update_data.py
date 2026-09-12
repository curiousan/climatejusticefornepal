"""Offline checks for report interpretation and safe snapshot replacement."""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.update_data import REPORTS, ROOT, parse_report, refresh, validate_snapshot


# Small synthetic fixtures exercise the parser; they are not copied article bodies.
UN_REPORT = """
<html><head><meta property="article:published_time" content="2026-09-09T12:00:00Z">
<title>Flood-Ravaged Nepal Calls for Climate Justice</title></head><body><article>
Nepal: 26 August floods. 1,367 people confirmed dead.
5,132 people are still missing. 84,270 people affected.
</article></body></html>
"""
AP_REPORT = """
<html><head><meta property="article:published_time" content="2026-09-08T03:32:26Z">
<title>Nepal endured months of political upheaval</title></head><body><article>
Nepal: flash floods two weeks ago. About 7,500 homes were destroyed;
another 20,000 need rebuilding. The preliminary damage estimate of $2.56 billion.
</article></body></html>
"""


class ParsingTests(unittest.TestCase):
    def test_un_figures_are_distinct_from_people_affected(self):
        self.assertEqual(parse_report(UN_REPORT, REPORTS[0]), {"deaths": 1367, "missing": 5132})

    def test_usd_and_explicit_additional_homes(self):
        self.assertEqual(parse_report(AP_REPORT, REPORTS[1]), {"homes": 27500, "damage": 2560000000})

    def test_rejects_missing_or_conflicting_numbers(self):
        for html in (UN_REPORT.replace("5,132 people are still missing.", ""),
                     UN_REPORT.replace("</article>", "5,099 people are still missing.</article>")):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_report(html, REPORTS[0])

    def test_rejects_wrong_event_date_year_and_title(self):
        variants = [UN_REPORT.replace("26 August", "28 September"),
                    UN_REPORT.replace("26 August", "26 August 2024"),
                    UN_REPORT.replace("2026-09-09", "2025-09-09"),
                    UN_REPORT.replace("Flood-Ravaged Nepal Calls for Climate Justice", "Access denied")]
        for html in variants:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_report(html, REPORTS[0])

    def test_visible_publication_date_fallback(self):
        html = UN_REPORT.replace('<meta property="article:published_time" content="2026-09-09T12:00:00Z">', "")
        with self.assertRaises(ValueError):
            parse_report(html, REPORTS[0])
        self.assertEqual(parse_report(html.replace("<article>", "<article>09 September 2026"), REPORTS[0])["deaths"], 1367)

    def test_modified_timestamp_does_not_relabel_report(self):
        html = UN_REPORT.replace("<title>", '<meta property="article:modified_time" content="2026-09-12T10:00:00Z"><title>')
        self.assertEqual(parse_report(html, REPORTS[0])["missing"], 5132)

    def test_housing_categories_must_be_explicitly_separate(self):
        with self.assertRaises(ValueError):
            parse_report(AP_REPORT.replace("another 20,000", "20,000"), REPORTS[1])

    def test_relative_event_reference_is_tied_to_reviewed_report_date(self):
        with self.assertRaises(ValueError):
            parse_report(AP_REPORT.replace("2026-09-08", "2026-10-08"), REPORTS[1])
        with self.assertRaises(ValueError):
            parse_report(AP_REPORT.replace("two weeks ago", "last year"), REPORTS[1])

    def test_repeated_consistent_damage_estimate_is_accepted(self):
        html = AP_REPORT.replace("</article>", "Damage estimate so far of $2.56 billion.</article>")
        self.assertEqual(parse_report(html, REPORTS[1])["damage"], 2560000000)

    def test_excludes_script_and_navigation_numbers(self):
        html = UN_REPORT.replace("<article>", "<nav>8,000 people are still missing</nav><script>9,000 people confirmed dead</script><article>")
        self.assertEqual(parse_report(html, REPORTS[0])["missing"], 5132)


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "impact.json"
        self.original = (ROOT / "data" / "impact.json").read_bytes()
        self.path.write_bytes(self.original)
        self.addCleanup(patch.stopall)
        patch("sys.stdout", new=io.StringIO()).start()
        patch("sys.stderr", new=io.StringIO()).start()

    def fetch(self, url):
        return UN_REPORT if url == REPORTS[0].url else AP_REPORT

    def test_failed_network_leaves_file_bytes_and_dates_unchanged(self):
        def failing_fetch(url):
            raise OSError("HTTP 403")
        self.assertFalse(refresh(self.path, fetch=failing_fetch, today="2026-09-12"))
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_one_failed_report_prevents_partial_replacement(self):
        def mixed_fetch(url):
            return UN_REPORT.replace("1,367", "1,400") if url == REPORTS[0].url else "parser changed"
        self.assertFalse(refresh(self.path, fetch=mixed_fetch, today="2026-09-12"))
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_check_performs_no_write(self):
        self.assertTrue(refresh(self.path, check=True, fetch=self.fetch, today="2026-09-12"))
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_valid_refresh_preserves_source_dates(self):
        self.assertTrue(refresh(self.path, fetch=self.fetch, today="2026-09-12"))
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["verifiedAt"], "2026-09-12")
        self.assertEqual(saved["metrics"]["deaths"]["asOf"], "2026-09-09")
        self.assertEqual(saved["metrics"]["damage"]["asOf"], "2026-09-08")
        self.assertEqual(saved["metrics"]["damage"]["display"], "$2.56B")

    def test_newer_manually_reviewed_snapshot_is_not_downgraded(self):
        saved = json.loads(self.original)
        saved["metrics"]["deaths"]["asOf"] = "2026-09-10"
        self.path.write_text(json.dumps(saved))
        before = self.path.read_bytes()
        self.assertFalse(refresh(self.path, fetch=self.fetch, today="2026-09-12"))
        self.assertEqual(self.path.read_bytes(), before)

    def test_interrupted_atomic_replace_keeps_existing_snapshot(self):
        with patch("scripts.update_data.os.replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                refresh(self.path, fetch=self.fetch, today="2026-09-12")
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_snapshot_rejects_missing_metrics(self):
        saved = json.loads(self.original)
        del saved["metrics"]["missing"]
        with self.assertRaises(ValueError):
            validate_snapshot(saved)


if __name__ == "__main__":
    unittest.main()
