"""Read-only text checks of ONGC's official 2026 apprentice advertisement."""
import json
import re
from io import BytesIO
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pypdf import PdfReader

URL = 'https://www.ongcindia.com/documents/77751/2660534/Advertisement021126.pdf/3680ed1d-fcd1-cdde-c5af-1c25fcc3b8c8'
HOSTS = {'www.ongcindia.com', 'ongcindia.com'}


def verify(url=URL):
    with urlopen(Request(url, headers={'User-Agent': 'KamyabiOfficialNoticeReview/1.0'}), timeout=30) as response:
        final = urlparse(response.geturl())
        if final.scheme != 'https' or final.hostname not in HOSTS:
            raise ValueError('Official PDF redirected outside ONGC')
        payload = response.read(8_000_001)
    if len(payload) > 8_000_000 or not payload.startswith(b'%PDF-'):
        raise ValueError('Official PDF invalid or too large')
    pages = PdfReader(BytesIO(payload)).pages
    if len(pages) > 60:
        raise ValueError('Unexpectedly long PDF')
    text = '\n'.join(page.extract_text() or '' for page in pages)
    normalized = re.sub(r'\s+', ' ', text).upper()
    dates = {key: bool(re.search(pattern, normalized)) for key, pattern in {
        'opening_29_oct_2026': r'29[./-]10[./-]2026',
        'closing_20_nov_2026': r'20[./-]11[./-]2026',
        'closing_05_nov_2026': r'05[./-]11[./-]2026',
    }.items()}
    return {'url': url, 'pdf_pages': len(pages), 'text_characters': len(text),
            'advertisement_number_found': 'ONGC/APPR/1/2026' in normalized,
            'apprenticeship_found': 'APPRENTICE' in normalized,
            'vacancies_3047_found': bool(re.search(r'(?<!\d)3[,]?047(?!\d)', normalized)),
            'dates': dates, 'writes_attempted': 0}


if __name__ == '__main__':
    try:
        print(json.dumps(verify(), indent=2))
    except Exception as error:
        print(json.dumps({'status': 'unverified', 'error': type(error).__name__,
                          'writes_attempted': 0}, indent=2))
