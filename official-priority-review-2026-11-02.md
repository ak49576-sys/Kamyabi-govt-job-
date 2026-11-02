# Official recruitment shortlist review — 2 November 2026

This report follows the GitHub Actions priority-notice run 41491391591. Nine links were shortlisted from 466 official-source candidate links. The shortlist only indicates notice-title relevance; it does **not** establish a current application window or authorize publication.

## Findings

| Notice | Official evidence | Kamyabi / review decision |
| --- | --- | --- |
| POWERGRID Engineer Trainees 2027 (CC/03/2026) | [Official employment opportunities](https://www.powergrid.in/en/job-opportunities1) displays an application window ending **30 April 2027**. | Already appears at [powergrid-engineer-trainee-2027](https://kamyabi.in/jobs/powergrid-engineer-trainee-2027), whose public page showed **31 Dec 2099** as an unconfirmed placeholder. **Correct existing record; do not create duplicate.** Verify the official PDF before updating remaining fields. |
| POWERGRID ST Officer Trainee (CS) 2026 (CC/02/2026) | Official listing closes **19 May 2026**. | **Expired; no new submission.** |
| POWERGRID Engineer Trainees 2026 (CC/04/2025) | Official listing shows the application window ending in **2025**. | **Expired; no new submission.** |
| Canara Bank Graduate Apprentices FY 2026–27 | [Official advertisement PDF](https://www.canarabank.bank.in/documents/d/guest/apprenticeship-advertisement-2026-27) states **3,500 seats** and registration **1–17 October 2026**. | **Expired; no new submission.** |
| ONGC Apprentices FY 2026–27 | [ONGC recruitment notices](https://www.ongcindia.com/web/eng/career/recruitment-notice) list a new 2026 notice and link to an [official PDF](https://www.ongcindia.com/documents/77751/2660534/Advertisement021126.pdf/3680ed1d-fcd1-cdde-c5af-1c25fcc3b8c8). Independent summaries report **3,047 seats** with a deadline of **20 Nov 2026**, but this run has not extracted those values directly from the ONGC PDF. | [ongc-apprentice-2026](https://kamyabi.in/jobs/ongc-apprentice-2026) already exists and displays the earlier closing date **5 Nov 2026**. **Potential correction, not a new record.** Confirm whether the new notification supersedes the existing job, and verify the dates in the PDF before altering it. |
| ONGC Associate/Junior Consultants, Assam Well Services | Official PDF link present on ONGC site, but the application window is not captured in the source report. | **Hold; deadline and terms require review.** |
| ONGC Geologists and Engineers E1 (2/2026) | Official 2026 notice exists, but it is an older recruitment and the current application window was not confirmed. | **Hold; do not assume applications are open.** |
| ONGC PMIS Mentors 2026–27 | Official notice exists, but current application eligibility/deadline not confirmed. | **Hold.** |
| ONGC PMIS Mentors Round II (31 May 2026) | Notice title mentions a **31 May 2026** deadline. | **Expired; no new submission.** |

## Operational decision

- **0 new jobs staged or published** from this nine-link review: the strongest open candidates have existing Kamyabi pages or need a direct PDF date check.
- **2 existing-page correction candidates**: POWERGRID 2027 and ONGC Apprentices 2026.
- Keep candidate collection, triage, existing reviewed-job publishing, and the admin pending workflow independent. Do not create duplicate advertisements.
- The public Kamyabi pages were observed through public web retrieval; recheck the database's current record before any correction, since crawled pages may lag the live database.

## Follow-up correction — 2 November 2026

- [One-time ONGC correction run 41496344175](https://github.com/ak49576-sys/Kamyabi-govt-job-/actions/runs/41496344175): four safeguard tests passed. The exact existing `ongc-apprentice-2026` admin row was updated and re-approved; the read-back confirmed **last_date = 2026-11-20**. Its start date was changed to **2026-10-29**, official notification URL to the linked ONGC PDF, and the reported apprentice seat count to **3,047**. These figures were corroborated by current recruitment reports; direct PDF extraction from GitHub remained unavailable.
- Full pagination across all admin statuses returned **69 approved, 3 pending and 1 rejected** records. No `powergrid-engineer-trainee-2027` ID or POWERGRID 2027 title appeared in those records. Its public page is therefore not safely editable via the present admin-job route; inspect the separate/static site content before altering it.
- Only the ONGC record was changed. Do not create a second ONGC listing, and do not assume the separate POWERGRID page was corrected.
