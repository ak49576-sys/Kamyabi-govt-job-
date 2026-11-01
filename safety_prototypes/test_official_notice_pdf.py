import unittest
from datetime import date
from hashlib import sha256
from io import BytesIO

from reportlab.pdfgen import canvas

from official_notice_pdf import extract_pdf_text, extract_labeled_application_dates


def sample_pdf(*lines):
    out = BytesIO()
    pdf = canvas.Canvas(out)
    for number, line in enumerate(lines):
        pdf.drawString(50, 780 - number * 20, line)
    pdf.showPage()
    pdf.save()
    return out.getvalue()


class PdfNoticeExtractionTests(unittest.TestCase):
    def test_reads_valid_notice(self):
        data = sample_pdf("Staff Selection Commission Recruitment 2026",
                          "Advertisement 12/2026 Junior Engineer",
                          "Application start date: 2026-10-01",
                          "Application last date: 2026-11-30")
        result = extract_pdf_text(data)
        self.assertTrue(result.complete)
        self.assertIn("Junior Engineer", result.text)
        self.assertEqual(result.sha256_hex, sha256(data).hexdigest())

    def test_not_pdf(self):
        self.assertEqual(extract_pdf_text(b"not a PDF").reason, "not_pdf")

    def test_empty(self):
        self.assertEqual(extract_pdf_text(b"").reason, "size_invalid")

    def test_size_limit(self):
        self.assertEqual(extract_pdf_text(b"x" * 101, max_bytes=100).reason, "size_invalid")

    def test_corrupt_pdf(self):
        self.assertEqual(extract_pdf_text(b"%PDF-corrupted").reason, "parse_error")

    def test_scanned_or_blank_pdf(self):
        self.assertEqual(extract_pdf_text(sample_pdf()).reason, "unreadable_or_scanned")

    def test_page_limit(self):
        self.assertEqual(extract_pdf_text(sample_pdf("Document"), max_pages=0).reason,
                         "page_count_invalid")

    def test_dated_iso_fields(self):
        self.assertEqual(extract_labeled_application_dates(
            "Application start date: 2026-10-01\nApplication last date: 2026-11-30"),
            (date(2026, 10, 1), date(2026, 11, 30)))

    def test_dated_indian_format(self):
        self.assertEqual(extract_labeled_application_dates(
            "Applications open on 01/10/2026\nApplications close on 30/11/2026"),
            (date(2026, 10, 1), date(2026, 11, 30)))

    def test_missing_label_is_not_guessed(self):
        self.assertIsNone(extract_labeled_application_dates("2026-10-01 to 2026-11-30"))

    def test_conflicting_corrigendum_dates_are_ambiguous(self):
        self.assertIsNone(extract_labeled_application_dates(
            "Application start date 2026-10-01. Application last date 2026-11-30. "
            "Application last date 2026-12-15."))

    def test_nonsensical_date(self):
        self.assertIsNone(extract_labeled_application_dates(
            "Application start date: 2026-02-30\nApplication last date: 2026-11-30"))

    def test_reversed_dates(self):
        self.assertIsNone(extract_labeled_application_dates(
            "Application start date: 2026-12-01\nApplication last date: 2026-11-30"))

    def test_short_year_is_not_accepted(self):
        self.assertIsNone(extract_labeled_application_dates(
            "Application start date: 01/10/26\nApplication last date: 30/11/26"))


if __name__ == "__main__":
    unittest.main()
