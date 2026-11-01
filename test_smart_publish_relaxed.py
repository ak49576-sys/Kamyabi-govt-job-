import unittest
from datetime import date

from smart_publish_gate import assess, assess_batch

TODAY = date(2026, 11, 1)
JOB = {
    "job_id": "ibps-assistant-2026", "title": "Assistant", "recruiting_body": "IBPS",
    "advt_no": "IBPS/2026-27/06", "last_date": "2026-11-12",
    "official_notification_url": "https://www.ibps.in/recruitment/assistant",
    "scope_category": "public_sector_banking", "vacancy_count": 3,
    "qualification": "Graduate",
}
EVIDENCE = {
    "source_type": "official_page", "url": JOB["official_notification_url"],
    "retrieval_succeeded": True, "official_content_verified": True,
    "checked_on": "2026-11-01", "official_title": "Assistant",
    "official_recruiting_body": "IBPS", "official_advt_no": "IBPS/2026-27/06",
    "official_last_date": "2026-11-12", "verified_scope_category": "public_sector_banking",
    "classification_verified": True,
}


class RelaxedPreviewTests(unittest.TestCase):
    def check(self, job=None, evidence=None, inventory=None, complete=True):
        return assess(JOB if job is None else job, [] if inventory is None else inventory,
                      EVIDENCE if evidence is None else evidence, TODAY, inventory_complete=complete)

    def test_official_html_without_pdf_or_extracted_extra_fields_is_eligible_dry_run(self):
        self.assertEqual(self.check()["decision"], "eligible_for_dry_run")

    def test_verified_qualification_and_vacancy_count_are_not_mandatory(self):
        evidence = dict(EVIDENCE, official_qualification="Different", official_vacancy_count=999)
        self.assertEqual(self.check(evidence=evidence)["decision"], "eligible_for_dry_run")

    def test_raw_apify_evidence_is_not_enough(self):
        evidence = dict(EVIDENCE, retrieval_succeeded=False, official_content_verified=False)
        self.assertIn("official_retrieval_unconfirmed", self.check(evidence=evidence)["reasons"])

    def test_private_bank_classification_is_held(self):
        evidence = dict(EVIDENCE, verified_scope_category="private_sector")
        self.assertIn("government_psu_scope_not_verified", self.check(evidence=evidence)["reasons"])

    def test_unsourced_classification_is_held(self):
        evidence = dict(EVIDENCE, classification_verified=False)
        self.assertIn("government_psu_scope_not_verified", self.check(evidence=evidence)["reasons"])

    def test_expired_deadline_is_held(self):
        job = dict(JOB, last_date="2026-10-31")
        evidence = dict(EVIDENCE, official_last_date="2026-10-31")
        self.assertIn("expired_or_implausible_deadline", self.check(job=job, evidence=evidence)["reasons"])

    def test_no_inventory_is_held(self):
        self.assertIn("pending_and_published_inventory_unverified", self.check(complete=False)["reasons"])

    def test_duplicate_pending_is_held(self):
        self.assertEqual(self.check(inventory=[dict(JOB, status="pending")])["decision"], "duplicate_or_update_review")

    def test_stale_page_is_held(self):
        self.assertIn("official_evidence_stale",
                      self.check(evidence=dict(EVIDENCE, checked_on="2026-10-30"))["reasons"])

    def test_notice_withdrawal_is_held(self):
        self.assertIn("withdrawn_notice", self.check(evidence=dict(EVIDENCE, withdrawn=True))["reasons"])

    def test_batch_duplicate_is_held(self):
        second = dict(JOB, job_id="ibps-assistant-copy")
        outcomes = assess_batch([JOB, second], [], {JOB["job_id"]: EVIDENCE,
                      second["job_id"]: EVIDENCE}, TODAY, inventory_complete=True)
        self.assertEqual([x["decision"] for x in outcomes],
                         ["eligible_for_dry_run", "duplicate_or_update_review"])


if __name__ == "__main__":
    unittest.main()
