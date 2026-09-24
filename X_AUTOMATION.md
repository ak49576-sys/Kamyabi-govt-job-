# Kamyabi → X automatic publication

This integration uses Buffer to publish **newly open, publicly visible** Kamyabi jobs to one X account. The first enabled run records the current open listings as a baseline and posts none of them. Later runs check every 30 minutes and publish one new job per run, with its Kamyabi detail-page link. Expired, upcoming, and placeholder-deadline records are skipped. A stable `job_id` is posted once; edits to an existing job do not produce another post.

## Account setup required before enabling

1. Connect the intended X account to a Buffer account. Confirm its handle and automatic publishing permission in Buffer.
2. Create a Buffer API key in Buffer account settings. Add it as the GitHub Actions secret `BUFFER_API_KEY` in this repository. Never place the key in a source file, workflow input, chat, or log.
3. Obtain that X channel's ID from Buffer and add it as the Actions secret `BUFFER_X_CHANNEL_ID`. The script checks that the channel service is `twitter` before posting.
4. Merge the workflow after reviewing the account and an initial read-only preview. The first scheduled or manual run writes `x-published-jobs.json` with the current open jobs as the baseline. Verify the baseline commit, then wait for a newly open verified job and inspect the Buffer/X result.

The workflow skips publication when either secret is absent. It requires `contents: write` only to commit the nonsecret receipt file, which prevents repeat posts. Each run publishes at most one new job so the receipt is saved quickly. If the Buffer call succeeds but GitHub cannot save its receipt, pause the workflow and reconcile that job manually before retrying; the external post may already exist. GitHub's scheduled runs may be delayed, so publication is not guaranteed to be immediate.

Buffer's Free plan supports an X channel and its API but has publishing and request limits. Confirm the plan suits the number of new Kamyabi jobs before enabling. Buffer handles the connection to X; this workflow does not use X developer credentials or buy X API credits.

## Local checks

`python -m unittest -v test_kamyabi_x_publisher.py` tests gating, baseline, deduplication, failure and post formatting. `python kamyabi_x_publisher.py` previews the next job using the public API without posting or writing state. `--publish` is reserved for the configured GitHub workflow.
