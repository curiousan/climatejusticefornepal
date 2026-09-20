"""Offline checks for report interpretation and safe snapshot replacement."""

import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.update_data import REPORTS, ROOT, parse_report, refresh, validate_snapshot


# Synthetic fixtures cover source definitions without copying full articles.
RESCUE_REPORT = """
<html><body>Nepal floods · 26 Aug 2026. Portal updated 20 Sep 2026.
NDRRMA – Rasuwa Flood: Search, Rescue and Relief Update · Ashwin 3, 2083 · 19 Sep 2026
NDRRMA Rescued 13,784 Helicopter flights: 2,012
Casualties 1,411 Managed: 110 · including various unidentified human remains
Missing 5,875 Rasuwa 3,513 · Nuwakot 1,836 · Foreign nationals 636
Injured in treatment 10,059 Currently in hospital 18 · Treated by the security agencies 10,041
Nepal Police – 9 Sep 2026. Missing 4,077 Rasuwa. Casualties 1,367
</body></html>
"""
HOUSING_REPORT = """
<html><body>Nepal: 26 August floods.
Rasuwa Flood Situation Update 8 (13 September 2026)
A total of 7,570 private buildings has been damaged, affecting 8,317 households.
</body></html>
"""
DAMAGE_REPORT = """
<html><body>The Ministry's regular Press Briefing- 11 September 2026
Nepal floods on 26 August 2026.
The total damage caused by the disaster is estimated at approximately USD 1.8 billion,
while the estimated loss is approximately USD 883 million.
The total estimated requirement for reconstruction is approximately USD 4.78 billion.
</body></html>
"""
FIXTURES = dict(zip((report.url for report in REPORTS), (RESCUE_REPORT, HOUSING_REPORT, DAMAGE_REPORT)))


class ParsingTests(unittest.TestCase):
    def test_latest_rescue_figures_exclude_older_police_report(self):
        self.assertEqual(parse_report(RESCUE_REPORT, REPORTS[0]),
                         {"deaths": 1411, "missing": 5875, "injured": 10041, "rescued": 13784})

    def test_injured_are_not_summed_with_current_hospital_patients(self):
        html = RESCUE_REPORT.replace("Currently in hospital 18", "Currently in hospital 99")
        self.assertEqual(parse_report(html, REPORTS[0])["injured"], 10041)

    def test_housing_does_not_count_households_as_buildings(self):
        self.assertEqual(parse_report(HOUSING_REPORT, REPORTS[1]), {"homes": 7570})

    def test_financial_categories_and_units_are_distinct(self):
        self.assertEqual(parse_report(DAMAGE_REPORT, REPORTS[2]),
                         {"damage": 1800000000, "losses": 883000000, "recovery": 4780000000})

    def test_rejects_missing_or_conflicting_numbers(self):
        for html in (RESCUE_REPORT.replace("Missing 5,875", "Not available"),
                     RESCUE_REPORT.replace("Missing 5,875", "Missing 5,000 Rasuwa. Missing 5,875")):
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_report(html, REPORTS[0])

    def test_rejects_wrong_event_year_title_and_report_date(self):
        variants = [RESCUE_REPORT.replace("26 Aug", "28 Sep"),
                    RESCUE_REPORT.replace("26 Aug 2026", "26 Aug 2024"),
                    RESCUE_REPORT.replace("19 Sep 2026", "20 Sep 2026"),
                    RESCUE_REPORT.replace(REPORTS[0].title, "Access denied")]
        for html in variants:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_report(html, REPORTS[0])

    def test_portal_date_does_not_relabel_selected_report(self):
        # A recent site-wide date cannot validate the wrong selected report.
        html = RESCUE_REPORT.replace("Portal updated 20 Sep 2026", "Portal updated 19 Sep 2026")
        html = html.replace("Ashwin 3, 2083 · 19 Sep 2026", "Ashwin 1, 2083 · 17 Sep 2026")
        with self.assertRaises(ValueError):
            parse_report(html, REPORTS[0])

    def test_housing_requires_dated_section(self):
        with self.assertRaises(ValueError):
            parse_report(HOUSING_REPORT.replace("13 September", "14 September"), REPORTS[1])

    def test_changed_financial_publication_requires_review(self):
        html = DAMAGE_REPORT.replace("<body>", '<meta property="article:published_time" content="2026-09-20"><body>')
        with self.assertRaises(ValueError):
            parse_report(html, REPORTS[2])

    def test_rejects_ambiguous_loss_estimate(self):
        html = DAMAGE_REPORT.replace("</body>", "estimated loss is approximately USD 900 million.</body>")
        with self.assertRaises(ValueError):
            parse_report(html, REPORTS[2])

    def test_excludes_script_and_navigation_numbers(self):
        html = RESCUE_REPORT.replace("<body>", "<body><nav>Casualties 9,000</nav><script>Casualties 8,000</script>")
        self.assertEqual(parse_report(html, REPORTS[0])["deaths"], 1411)


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
        return FIXTURES[url]

    def test_failed_network_leaves_file_bytes_and_dates_unchanged(self):
        def failing_fetch(url):
            raise OSError("HTTP 403")
        self.assertFalse(refresh(self.path, fetch=failing_fetch, today="2026-09-20"))
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_one_failed_report_prevents_partial_replacement(self):
        def mixed_fetch(url):
            return RESCUE_REPORT.replace("1,411", "1,420") if url == REPORTS[0].url else "parser changed"
        self.assertFalse(refresh(self.path, fetch=mixed_fetch, today="2026-09-20"))
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_check_performs_no_write(self):
        self.assertTrue(refresh(self.path, check=True, fetch=self.fetch, today="2026-09-20"))
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_valid_refresh_preserves_source_dates(self):
        self.assertTrue(refresh(self.path, fetch=self.fetch, today="2026-09-20"))
        saved = json.loads(self.path.read_text())
        self.assertEqual(saved["verifiedAt"], "2026-09-20")
        self.assertEqual(saved["metrics"]["deaths"]["asOf"], "2026-09-19")
        self.assertEqual(saved["metrics"]["damage"]["asOf"], "2026-09-11")
        self.assertEqual(saved["metrics"]["damage"]["display"], "$1.80B")

    def test_newer_manually_reviewed_snapshot_is_not_downgraded(self):
        saved = json.loads(self.original)
        saved["metrics"]["deaths"]["asOf"] = "2026-09-20"
        self.path.write_text(json.dumps(saved))
        before = self.path.read_bytes()
        self.assertFalse(refresh(self.path, fetch=self.fetch, today="2026-09-20"))
        self.assertEqual(self.path.read_bytes(), before)

    def test_interrupted_atomic_replace_keeps_existing_snapshot(self):
        with patch("scripts.update_data.os.replace", side_effect=OSError("disk error")):
            with self.assertRaises(OSError):
                refresh(self.path, fetch=self.fetch, today="2026-09-21")
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_snapshot_rejects_missing_metrics(self):
        saved = json.loads(self.original)
        del saved["metrics"]["missing"]
        with self.assertRaises(ValueError):
            validate_snapshot(saved)


if __name__ == "__main__":
    unittest.main()
