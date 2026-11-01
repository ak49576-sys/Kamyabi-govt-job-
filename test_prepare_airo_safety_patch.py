import unittest
from prepare_airo_safety_patch import (
    ADD_JOBS, APIFY, AUTO_VERIFY, AUTO_BLOCK_OLD, REPLACEMENTS,
    UnexpectedSource, patched_versions, proposal_diff,
)


def sample_sources():
    sources = {}
    for path, replacements in REPLACEMENTS.items():
        sources[path] = "\n".join(before for before, _ in replacements) + "\n"
    return sources


class AiroPatchTests(unittest.TestCase):
    def test_patch_forces_every_import_pending(self):
        originals = sample_sources()
        result = patched_versions(originals)
        self.assertIn("const approved = false;", result[APIFY])
        self.assertIn("auto_verify_pass:  avResult.passed,", result[APIFY])
        self.assertIn("const approved = false;", result[ADD_JOBS])
        self.assertIn("const canAutoPromote = false;", result[ADD_JOBS])
        self.assertIn("approved: false,", result[AUTO_VERIFY])
        self.assertNotIn("return { job_id: r.jobId, approved: true };", result[AUTO_VERIFY])
        self.assertEqual(originals, sample_sources())  # no mutation

    def test_diff_has_only_expected_paths(self):
        diff = proposal_diff(sample_sources())
        self.assertEqual(diff.count("--- a/"), 3)
        self.assertEqual(diff.count("+++ b/"), 3)
        self.assertNotIn("API_KEY=", diff)

    def test_missing_source_fails_closed(self):
        docs = sample_sources()
        del docs[APIFY]
        with self.assertRaises(UnexpectedSource):
            proposal_diff(docs)

    def test_source_drift_fails_closed(self):
        docs = sample_sources()
        docs[ADD_JOBS] = docs[ADD_JOBS].replace("const approved =", "const maybeApproved =")
        with self.assertRaises(UnexpectedSource):
            proposal_diff(docs)

    def test_ambiguous_duplicate_pattern_fails_closed(self):
        docs = sample_sources()
        docs[APIFY] += REPLACEMENTS[APIFY][0][0]
        with self.assertRaises(UnexpectedSource):
            proposal_diff(docs)


if __name__ == "__main__":
    unittest.main()
