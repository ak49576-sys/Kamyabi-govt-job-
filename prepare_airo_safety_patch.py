"""Generate a REVIEW-ONLY unified diff for the exported Airo backend.

This script NEVER writes to the project, calls an endpoint or deploys a change.
It refuses unexpected source versions. Output is a proposed patch only.
"""
import argparse
import difflib
from pathlib import Path

APIFY = "src/server/api/v1/admin/apify-import/POST.ts"
ADD_JOBS = "src/server/api/v1/add-jobs/POST.ts"
AUTO_VERIFY = "src/server/api/v1/admin/jobs/auto-verify/POST.ts"

AUTO_BLOCK_OLD = """            // GitHub pipeline records must never be auto-approved via this
            // endpoint. A human must use POST /api/v1/admin/jobs/approve.
            // Do NOT write to rejection_reason — that field is for human
            // review notes, not for pipeline-source guards.
            if (r.importSource === 'github_pipeline') {
              return {
                job_id:   r.jobId,
                approved: false,
                reason:   'github_pipeline import requires manual approval via /admin/jobs/approve',
                blocked:  true,
              };
            }
            // Approve the job (non-pipeline records only)
            await db.update(govtJobs).set({
              verified:           true,
              verificationStatus: 'approved',
              lastVerifiedAt:     new Date(),
              rejectionReason:    null,
            }).where(eq(govtJobs.jobId, r.jobId));
            return { job_id: r.jobId, approved: true };"""
AUTO_BLOCK_NEW = """            // Domain and date checks are not proof of the specific notice.
            // Keep all imported records pending until separately reviewed.
            return {
              job_id: r.jobId,
              approved: false,
              reason: 'Specific official notification requires manual review',
              blocked: true,
            };"""

REPLACEMENTS = {
    APIFY: (
        ("const approved = avResult.passed;", "const approved = false;"),
        ("if (!approved) inserted++;\n          else inserted++; // count all inserts; admin panel shows auto-approved separately",
         "inserted++; // Every new Actor record stays pending"),
        ("auto_verify_pass:  approved,", "auto_verify_pass:  avResult.passed,"),
    ),
    ADD_JOBS: (
        ("const approved = isGithubPipeline ? false : result.passed;",
         "const approved = false; // Imports never establish notice verification"),
        ("const canAutoPromote =\n              !isGithubPipeline &&\n              (existing?.importSource ?? null) !== 'github_pipeline';",
         "const canAutoPromote = false; // Hold until authoritative evidence gate exists"),
    ),
    AUTO_VERIFY: (
        (AUTO_BLOCK_OLD, AUTO_BLOCK_NEW),
        ("import { eq } from 'drizzle-orm';", "import { and, eq } from 'drizzle-orm';"),
        ("where(eq(govtJobs.jobId, singleJobId));",
         "where(and(eq(govtJobs.jobId, singleJobId), eq(govtJobs.verificationStatus, 'pending')));"),
        ("            await db.update(govtJobs).set({\n              rejectionReason: `[Rule ${result.rule}] ${result.reason}`,\n            }).where(eq(govtJobs.jobId, r.jobId));",
         "            await db.update(govtJobs).set({\n              rejectionReason: `[Rule ${result.rule}] ${result.reason}`,\n            }).where(and(eq(govtJobs.jobId, r.jobId), eq(govtJobs.verificationStatus, 'pending')));"),
    ),
}


class UnexpectedSource(ValueError):
    pass


def patched_versions(source_by_path):
    result = {}
    for path, replacements in REPLACEMENTS.items():
        original = source_by_path.get(path)
        if not isinstance(original, str):
            raise UnexpectedSource(f"Missing required source: {path}")
        updated = original
        for before, after in replacements:
            if updated.count(before) != 1:
                raise UnexpectedSource(f"Unexpected source contract: {path}")
            updated = updated.replace(before, after, 1)
        result[path] = updated
    return result


def proposal_diff(source_by_path):
    updated = patched_versions(source_by_path)
    chunks = []
    for path in REPLACEMENTS:
        before = source_by_path[path].splitlines(keepends=True)
        after = updated[path].splitlines(keepends=True)
        chunks.extend(difflib.unified_diff(
            before, after, fromfile="a/" + path, tofile="b/" + path, n=4))
    return "".join(chunks)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True,
                        help="Directory containing extracted Airo project src/")
    args = parser.parse_args()
    root = Path(args.source_root)
    sources = {}
    for relative in REPLACEMENTS:
        path = root / relative
        if not path.is_file():
            parser.error(f"Source is missing: {relative}")
        sources[relative] = path.read_text(encoding="utf-8")
    try:
        diff = proposal_diff(sources)
    except UnexpectedSource as error:
        parser.error(str(error))
    print(diff, end="")


if __name__ == "__main__":
    main()
