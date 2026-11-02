import unittest
from match_official_notices import match_sbi, find_official_pdf
from unittest.mock import patch

class MatchTests(unittest.TestCase):
    def test_exact_advert_number_from_official_page(self):
        rows = [{"recruitmentBoard": "SBI", "advtNo": "CRPD/SCO/2026-27/30",
                 "postName": "AI officers", "lastDate": "09-11-2026",
                 "detailUrl": "https://www.freejobalert.com/notice"}]
        html = "<p>ADVERTISEMENT NO: CRPD/SCO/2026-27/30</p>"
        result = match_sbi(rows, html)
        self.assertEqual(result[0]["verification_status"], "OFFICIAL_ADVERTISEMENT_NUMBER_MATCH_ONLY")
        self.assertFalse(result[0]["publishable"])

    def test_partial_advert_number_rejected(self):
        row = {"recruitmentBoard": "SBI", "advtNo": "30", "postName": "AI"}
        self.assertEqual(match_sbi([row], "<p>CRPD/SCO/2026-27/30</p>")[0]["verification_status"],
                         "NOT_CONFIRMED_ON_OFFICIAL_PAGE")

    def test_no_false_suffix_match(self):
        row = {"recruitmentBoard": "SBI", "advtNo": "CRPD/SCO/2026-27/3", "postName": "AI"}
        result = match_sbi([row], "<p>CRPD/SCO/2026-27/30</p>")
        self.assertEqual(result[0]["official_listing_url"], "")

    def test_official_pdf_link_matches_exact_advert_number(self):
        html = ('<a href="https://sbi.bank.in/documents/adv_SCO_2026-27_30.pdf">English</a>'
                '<p>CRPD/SCO/2026-27/30</p>')
        self.assertEqual(find_official_pdf(html, "CRPD/SCO/2026-27/30",
                                           "https://sbi.bank.in/web/careers/Current-openings"),
                         "https://sbi.bank.in/documents/adv_SCO_2026-27_30.pdf")
        self.assertEqual(find_official_pdf(html, "CRPD/SCO/2026-27/3",
                                           "https://sbi.bank.in/web/careers/Current-openings"), "")

    @patch("match_official_notices.pdf_reachable", return_value=True)
    def test_document_match_is_still_not_publishable(self, checker):
        row = {"recruitmentBoard": "SBI", "advtNo": "CRPD/SCO/2026-27/30", "postName": "AI"}
        html = ('<p>CRPD/SCO/2026-27/30</p>'
                '<a href="https://sbi.bank.in/documents/adv_SCO_2026-27_30.pdf">English</a>')
        match = match_sbi([row], html)[0]
        self.assertTrue(match["official_document_reachable"])
        self.assertFalse(match["publishable"])

    def test_other_banks_not_matched(self):
        self.assertEqual(match_sbi([{"recruitmentBoard": "UCO Bank", "advtNo": "CRPD/SCO/2026-27/30"}],
                                   "CRPD/SCO/2026-27/30"), [])

if __name__ == "__main__":
    unittest.main()
