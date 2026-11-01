import unittest
from datetime import date
from smart_publish_gate import assess, assess_batch

TODAY = date(2026, 11, 1)
JOB = {
    "job_id": "ibps-server-assistant-2026", "title": "Assistant",
    "recruiting_body": "IBPS", "advt_no": "IBPS/2026-27/06",
    "last_date": "2026-11-12", "official_notification_url": "https://www.ibps.in/notice.pdf",
    "vacancy_count": 3, "qualification": "Graduate",
}
EVIDENCE = {
    "source_type": "official_notice", "url": JOB["official_notification_url"],
    "retrieval_succeeded": True, "official_title": JOB["title"],
    "official_recruiting_body": JOB["recruiting_body"],
    "official_advt_no": JOB["advt_no"], "official_last_date": JOB["last_date"],
    "official_vacancy_count": JOB["vacancy_count"],
    "official_qualification": JOB["qualification"],
}

class SmartPublishingGateTests(unittest.TestCase):
    def check(self, job=None, existing=None, evidence=None, complete=True):
        return assess(job if job is not None else JOB,
                      existing if existing is not None else [],
                      evidence if evidence is not None else EVIDENCE,
                      TODAY, inventory_complete=complete)

    def test_complete_valid_record_only_dry_run_eligible(self):
        self.assertEqual(self.check()["decision"], "eligible_for_dry_run")

    def test_missing_inventory_fails_closed(self):
        result = self.check(complete=False)
        self.assertEqual(result["decision"], "manual_review")
        self.assertIn("pending_and_published_inventory_unverified", result["reasons"])

    def test_aggregator_is_not_official_evidence(self):
        job = dict(JOB, official_notification_url="https://www.freejobalert.com/a")
        self.assertEqual(self.check(job=job)["decision"], "manual_review")

    def test_malformed_official_url_is_held_without_crashing(self):
        bad = dict(JOB, official_notification_url="https://[invalid")
        result = self.check(job=bad)
        self.assertEqual(result["decision"], "manual_review")
        self.assertIn("nonofficial_notice_url", result["reasons"])

    def test_malformed_existing_record_url_does_not_crash(self):
        existing = [dict(JOB, job_id="other", title="Other post",
                         advt_no="OTHER", official_notification_url="https://[invalid",
                         status="pending")]
        result = self.check(existing=existing)
        self.assertEqual(result["decision"], "eligible_for_dry_run")

    def test_official_evidence_required(self):
        self.assertEqual(self.check(evidence={})["decision"], "manual_review")

    def test_conflicting_official_deadline_is_held(self):
        evidence = dict(EVIDENCE, official_last_date="2026-11-20")
        self.assertIn("official_mismatch:last_date", self.check(evidence=evidence)["reasons"])

    def test_unretrieved_pdf_is_held(self):
        evidence = dict(EVIDENCE, retrieval_succeeded=False)
        self.assertEqual(self.check(evidence=evidence)["decision"], "manual_review")

    def test_expired_is_held(self):
        job = dict(JOB, last_date="2026-10-31")
        evidence = dict(EVIDENCE, official_last_date="2026-10-31")
        self.assertIn("expired_or_implausible_deadline", self.check(job=job, evidence=evidence)["reasons"])

    def test_same_id_pending_is_duplicate(self):
        existing = [dict(JOB, status="pending")]
        self.assertEqual(self.check(existing=existing)["decision"], "duplicate_or_update_review")

    def test_same_advertisement_different_id_is_duplicate(self):
        existing = [dict(JOB, job_id="another-slug", title="Programming Assistant", status="published")]
        self.assertEqual(self.check(existing=existing)["decision"], "duplicate_or_update_review")

    def test_same_title_year_different_advertisement_is_flagged(self):
        existing = [dict(JOB, job_id="another-slug", advt_no="OTHER/2026", status="approved")]
        self.assertEqual(self.check(existing=existing)["decision"], "duplicate_or_update_review")

    def test_unrecognized_inventory_state_is_held(self):
        existing = [dict(JOB, job_id="other", title="Unrelated", advt_no="OTHER", status="unknown")]
        self.assertEqual(self.check(existing=existing)["decision"], "manual_review")

    def test_duplicate_within_batch_is_held(self):
        second = dict(JOB, job_id="another-ibps-slug")
        results = assess_batch([JOB, second], [], {JOB["job_id"]: EVIDENCE,
            second["job_id"]: EVIDENCE}, TODAY, inventory_complete=True)
        self.assertEqual([r["decision"] for r in results],
                         ["eligible_for_dry_run", "duplicate_or_update_review"])


    def test_held_first_record_blocks_later_duplicate(self):
        first = dict(JOB, job_id="held-first")
        second = dict(JOB, job_id="later-copy")
        evidence = dict(EVIDENCE, official_last_date="2026-11-20")
        results = assess_batch([first, second], [], {
            first["job_id"]: evidence, second["job_id"]: EVIDENCE,
        }, TODAY, inventory_complete=True)
        self.assertEqual([r["decision"] for r in results],
                         ["manual_review", "duplicate_or_update_review"])

    def test_blank_ids_do_not_look_like_same_id_without_other_identity(self):
        existing = [{"job_id": None, "status": "pending"}]
        result = assess({}, existing, {}, TODAY, inventory_complete=True)
        self.assertEqual(result["decision"], "manual_review")

    def test_malformed_candidate_in_batch_is_held_without_crashing(self):
        results = assess_batch([None, JOB, "broken"], [], {JOB["job_id"]: EVIDENCE}, TODAY, inventory_complete=True)
        self.assertEqual([r["decision"] for r in results],
                         ["manual_review", "eligible_for_dry_run", "manual_review"])
        self.assertEqual(results[0]["reasons"], ["invalid_candidate"])

    def test_invalid_batch_containers_fail_closed(self):
        for candidates, existing, evidence in ((None, [], {}), ([JOB], None, {}), ([JOB], [], None)):
            with self.subTest(candidates=candidates, existing=existing, evidence=evidence):
                result = assess_batch(candidates, existing, evidence, TODAY, inventory_complete=True)
                self.assertEqual(result[0]["decision"], "manual_review")
                self.assertIn("invalid_batch_input", result[0]["reasons"])

    def test_rejected_record_is_collision_not_new_job(self):
        existing = [dict(JOB, status="rejected")]
        self.assertEqual(self.check(existing=existing)["decision"], "duplicate_or_update_review")

    def test_matching_official_url_different_title_id_and_advertisement(self):
        existing = [dict(JOB, job_id="prior-ibps-job", title="Different post",
                         advt_no="DIFFERENT/2026", status="pending")]
        self.assertEqual(self.check(existing=existing)["decision"], "duplicate_or_update_review")

    def test_fragment_does_not_hide_duplicate_notice(self):
        existing = [dict(JOB, job_id="prior-ibps-job", title="Different post",
                         advt_no="DIFFERENT/2026", status="approved",
                         official_notification_url=JOB["official_notification_url"] + "#page=2")]
        self.assertEqual(self.check(existing=existing)["decision"], "duplicate_or_update_review")

    def test_ongc_conflicting_deadline_never_eligible(self):
        job = dict(JOB, job_id="ongc-apprentice-2026", title="Apprentice",
                   recruiting_body="ONGC", advt_no="ONGC/APPR/1/2026",
                   last_date="2026-11-20")
        evidence = dict(EVIDENCE, url=job["official_notification_url"],
                        official_title="Apprentice", official_recruiting_body="ONGC",
                        official_advt_no=job["advt_no"], official_last_date="2026-11-05")
        self.assertEqual(self.check(job=job, evidence=evidence)["decision"], "manual_review")

if __name__ == "__main__":
    unittest.main()
