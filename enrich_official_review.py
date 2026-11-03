"""Join extracted official PDF facts to candidates for editorial review.

These drafts are not accepted by the reviewed-job submission API.
"""
import json
from datetime import datetime
from pathlib import Path


def normalized_unique_date(evidence):
    """Return one ISO date only when all observed dates agree."""
    parsed = set()
    for entry in evidence:
        raw = entry.get('observed') if isinstance(entry, dict) else None
        if not isinstance(raw, str):
            return None
        value = raw.strip()
        date_value = None
        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%d.%m.%Y',
                    '%d-%b-%Y', '%d-%B-%Y', '%d %b %Y', '%d %B %Y'):
            try:
                date_value = datetime.strptime(value, fmt).date()
                break
            except ValueError:
                pass
        if date_value is None:
            return None
        parsed.add(date_value)
    return next(iter(parsed)).isoformat() if len(parsed) == 1 else None


def date_suggestions(item):
    """Display suggestions but never promote observed dates into verified fields."""
    opening = normalized_unique_date(item.get('possible_opening_dates_unverified', []))
    closing = normalized_unique_date(item.get('possible_closing_dates_unverified', []))
    if opening and closing and opening <= closing:
        return {'application_start_date': opening, 'application_last_date': closing,
                'status': 'coherent_unverified_pdf_evidence'}
    return {'application_start_date': None, 'application_last_date': None,
            'status': 'missing_ambiguous_or_inconsistent'}


def enrich(queue, pdf_report):
    documents = {row['official_pdf_url']: row for row in pdf_report.get('documents', [])
                 if isinstance(row, dict) and row.get('status') == 'text_extracted'}
    candidates = []
    missing_counts = {}
    for row in queue.get('candidates', []):
        item = dict(row)
        document = documents.get(row.get('official_candidate_url'))
        if document:
            item['pdf_text_extracted'] = True
            item['possible_closing_dates_unverified'] = document.get('possible_closing_dates', [])
            item['possible_opening_dates_unverified'] = document.get('possible_opening_dates', [])
            item['qualification_keywords_unverified'] = document.get('qualification_keywords', [])
            item['source_evidence'] = 'official_pdf_text'
        else:
            item['pdf_text_extracted'] = False
            item['possible_closing_dates_unverified'] = []
            item['possible_opening_dates_unverified'] = []
            item['qualification_keywords_unverified'] = []
            item['source_evidence'] = 'official_listing_link_only'
        item['date_suggestions_unverified'] = date_suggestions(item)
        # These observations are leads, never verified recruitment fields.
        # Report exactly what an editor must confirm before import.
        required = ('job_id', 'department', 'qualification',
                    'application_start_date', 'application_last_date',
                    'last_date', 'official_notification_url')
        missing = list(required)
        item['missing_required_fields'] = missing
        for field in missing:
            missing_counts[field] = missing_counts.get(field, 0) + 1
        item['review_priority'] = (
            0 if item.get('pdf_text_extracted') and item.get('possible_closing_dates_unverified')
            else 1 if item.get('pdf_text_extracted')
            else 2 if item.get('observed_deadline_iso_unverified')
            else 3)
        item['reviewed'] = False
        item['publishable'] = False
        item['job_id'] = None
        candidates.append(item)
    candidates.sort(key=lambda x: x['review_priority'])
    return {'reviewed': False, 'submission_ready': False, 'published': 0,
            'candidates': candidates,
            'with_pdf_text': sum(x['pdf_text_extracted'] for x in candidates),
            'ready_for_import': 0,
            'missing_field_counts': missing_counts,
            'note': 'Official links and PDF snippets are review evidence. Every listed field needs confirmation before import.'}


def main():
    folder = Path('output/official-coverage')
    queue = json.loads((folder / 'official-candidate-review.json').read_text())
    pdf_report = json.loads((folder / 'pdf-evidence.json').read_text())
    report = enrich(queue, pdf_report)
    (folder / 'evidence-enriched-review.json').write_text(json.dumps(report, indent=2))
    (folder / 'import-readiness.json').write_text(json.dumps({
        'ready_for_import': report['ready_for_import'],
        'missing_field_counts': report['missing_field_counts'],
        'priority_review': [
            {'source': item.get('source'), 'title': item.get('title_as_observed'),
             'official_candidate_url': item.get('official_candidate_url'),
             'missing_required_fields': item['missing_required_fields'],
             'review_priority': item['review_priority']}
            for item in report['candidates'][:30]],
        'note': report['note']}, indent=2))
    print(json.dumps({'candidates': len(report['candidates']),
                      'with_pdf_text': report['with_pdf_text'], 'published': 0}))


if __name__ == '__main__':
    main()
