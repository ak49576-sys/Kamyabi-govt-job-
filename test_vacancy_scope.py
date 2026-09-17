import unittest

from vacancy_scope import ALLOWED_CATEGORIES, classify_vacancy, filter_allowed


class VacancyScopeTests(unittest.TestCase):
    def test_each_permitted_category(self):
        cases = {
            "central_government": {"isGovernmentJob": True, "employer": "Ministry of Finance"},
            "state_government": {"isGovernmentJob": True, "employer": "Government of Rajasthan"},
            "railways": {"isGovernmentJob": True, "employer": "Railway Recruitment Board"},
            "public_sector_banking": {"isGovernmentJob": True, "employer": "State Bank of India"},
            "armed_forces": {"isGovernmentJob": True, "employer": "Indian Army"},
            "psu": {"isGovernmentJob": True, "employer": "NTPC Limited"},
        }
        self.assertEqual(set(cases), set(ALLOWED_CATEGORIES))
        for expected, record in cases.items():
            with self.subTest(expected):
                self.assertEqual(classify_vacancy(record), expected)

    def test_private_bank_is_rejected_even_if_mislabeled_government(self):
        self.assertIsNone(classify_vacancy({
            "isGovernmentJob": True,
            "employer": "HDFC Bank Private Limited",
        }))

    def test_missing_government_flag_is_rejected(self):
        self.assertIsNone(classify_vacancy({"employer": "Indian Railways"}))

    def test_generic_and_unclassified_listings_are_rejected(self):
        self.assertIsNone(classify_vacancy({
            "isGovernmentJob": True,
            "employer": "Generic Employer",
            "title": "Sales Executive",
        }))

    def test_filter_reports_rejections(self):
        allowed, rejected = filter_allowed([
            {"isGovernmentJob": True, "employer": "IBPS"},
            {"isGovernmentJob": False, "employer": "Private Company"},
        ])
        self.assertEqual(len(allowed), 1)
        self.assertEqual(allowed[0]["scope_category"], "public_sector_banking")
        self.assertEqual(len(rejected), 1)


if __name__ == "__main__":
    unittest.main()
