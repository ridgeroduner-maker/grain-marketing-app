import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from ingest import parse_pdf


class ReportDate(unittest.TestCase):
    def test_no_leading_zeros(self):
        # USDA started printing dates like 11/2/2026 (seen 2026-11-02).
        out = parse_pdf.parse_report("Grain Report for 11/2/2026 - Final\n", 3225, "t", "NE")
        self.assertEqual(out["report_date"], "2026-11-02")
        self.assertEqual(out["status"], "Final")

    def test_padded_still_works(self):
        out = parse_pdf.parse_report("Grain Report for 10/26/2026\n", 3186, "t", "SD")
        self.assertEqual(out["report_date"], "2026-10-26")
        self.assertEqual(out["status"], "Preliminary")


if __name__ == "__main__":
    unittest.main()
