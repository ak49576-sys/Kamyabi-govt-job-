"""Join extracted official PDF facts to candidates for editorial review.

These drafts are not accepted by the reviewed-job submission API.
"""
import json
from pathlib import Path


def enrich(queue, pdf_report):
    documents = {row['official_pdf_url']: row for row in pdf_report.get('documents', [])
                 if isinstance(row, dict) and row.get('status') == 'text_extracted'}
    candidates = []
    for row in queue.get('candidates', []):
        item = dict(row)
        document = documents.get(row.get('official_candidate_url'))
        if document:
            item['pdf_text_extracted'] = True
            item['possible_closing_dates_unverified'] = document.get('possible_closing_dates', [])
            item['qualification_keywords_unverified'] = document.get('qualification_keywords', [])
            item['source_evidence'] = 'official_pdf_text'
        else:
            item['pdf_text_extracted'] = False
            item['possible_closing_dates_unverified'] = []
            item['qualification_keywords_unverified'] = []
            item['source_evidence'] = 'official_listing_link_only'
        item['reviewed'] = False
        item['publishable'] = False
        item['job_id'] = None
        candidates.append(item)
    return {'reviewed': False, 'submission_ready': False, 'published': 0,
            'candidates': candidates,
            'with_pdf_text': sum(x['pdf_text_extracted'] for x in candidates),
            'note': 'Evidence only. Dates and qualifications are unverified, and this file cannot be submitted.'}


def main():
    folder = Path('output/official-coverage')
    queue = json.loads((folder / 'official-candidate-review.json').read_text())
    pdf_report = json.loads((folder / 'pdf-evidence.json').read_text())
    report = enrich(queue, pdf_report)
    (folder / 'evidence-enriched-review.json').write_text(json.dumps(report, indent=2))
    print(json.dumps({'candidates': len(report['candidates']),
                      'with_pdf_text': report['with_pdf_text'], 'published': 0}))


if __name__ == '__main__':
    main()
