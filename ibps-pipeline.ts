/**
 * IBPS collection and reviewed-job import. Candidate links are never job records.
 * Reuses the existing certificate-aware collector and reviewed-record validator.
 */
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

function run(args: string[], allowPartial = false): string {
  const result = spawnSync('python', args, { encoding: 'utf8', timeout: 180000 });
  if (result.error) throw new Error('Python step could not complete');
  if (result.status !== 0 && !(allowPartial && result.status === 1)) {
    const detail = result.stdout.trim().slice(0, 500);
    throw new Error(detail ? `Python step failed: ${detail}` :
      'Python step failed; inspect the generated reports');
  }
  return result.stdout;
}

const counts: Record<string, unknown> = {
  source: 'ibps', dry_run: true, discovered: 0, validated: 0,
  submitted: 0, inserted: 0, updated: 0, skipped: 0, pending: null,
  publication_status: 'not verified',
};
mkdirSync('output', { recursive: true });
const temporary = mkdtempSync(join(tmpdir(), 'kamyabi-ibps-'));
try {
  const source = process.env.SOURCE ?? 'ibps';
  const dry = process.env.DRY_RUN ?? 'true';
  if (source !== 'ibps') throw new Error('Only source=ibps is supported');
  if (!['true', 'false'].includes(dry)) throw new Error('DRY_RUN must be true or false');
  counts.dry_run = dry === 'true';

  const sources = JSON.parse(readFileSync('sources.json', 'utf8'));
  if (!Array.isArray(sources)) throw new Error('Invalid sources configuration');
  const filtered = sources.filter(s => typeof s.name === 'string' && /\bibps\b/i.test(s.name));
  if (!filtered.length) throw new Error('No IBPS source configured');
  const configuration = join(temporary, 'sources.json');
  writeFileSync(configuration, JSON.stringify(filtered));
  run(['monitor.py', '--sources', configuration, '--output', 'output'], true);
  const report = JSON.parse(readFileSync('output/report.json', 'utf8'));
  counts.discovered = report.candidate_records;
  if (!report.sources.every((s: any) => s.status === 'ok'))
    throw new Error('IBPS collection needs attention; candidates preserved in output');

  const reviewed = process.env.REVIEWED_JOBS_FILE?.trim();
  if (!reviewed) {
    counts.note = 'Candidate discovery only. Supply reviewed_jobs_file for validated job import.';
    if (dry === 'false') throw new Error('Import requires a reviewed jobs JSON file');
  } else {
    const file = resolve(reviewed);
    const root = resolve('.') + '/';
    if (!file.startsWith(root) || file.includes('/.git/'))
      throw new Error('Reviewed file must be inside the checked-out repository');
    const document = JSON.parse(readFileSync(file, 'utf8'));
    if (!Array.isArray(document.jobs)) throw new Error('Missing jobs array');
    for (const job of document.jobs) {
      if (job.recruiting_body?.toUpperCase() !== 'IBPS')
        throw new Error('Reviewed import must contain only IBPS records');
      for (const field of ['source_url', 'official_notification_url']) {
        const url = new URL(job[field]);
        if (url.protocol !== 'https:' || url.username || url.password ||
            !(url.hostname === 'ibps.in' || url.hostname.endsWith('.ibps.in')))
          throw new Error('IBPS official HTTPS evidence is required');
      }
    }
    run(['submit_jobs.py', '--file', file, '--output', 'output/validation.json']);
    const validation = JSON.parse(readFileSync('output/validation.json', 'utf8'));
    counts.validated = validation.validated_jobs;
    if (dry === 'false') {
      // No automatic retry: a failed response can have an unknown submission outcome.
      counts.submission_attempted = true;
      run(['submit_jobs.py', '--file', file, '--submit', '--output', 'output/submission.json']);
      const submission = JSON.parse(readFileSync('output/submission.json', 'utf8'));
      counts.submitted = counts.validated;
      for (const key of ['inserted', 'updated', 'skipped']) counts[key] = submission[key];
      counts.note = 'Import response received; pending/public status requires admin verification.';
    }
  }
  counts.status = 'ok';
} catch (error) {
  counts.status = 'error';
  counts.error = error instanceof Error ? error.message : 'Pipeline failed';
  process.exitCode = 1;
} finally {
  rmSync(temporary, { recursive: true, force: true });
  writeFileSync('output/import-counts.json', JSON.stringify(counts, null, 2));
  console.log(JSON.stringify(counts, null, 2));
}
