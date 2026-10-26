"""Extract selectable PDF text. Scanned/handwritten recognition is not supported."""
from .document_service import DocumentProcessingError, clean_text


def extract_pdf(path, start_page=1, end_page=None):
    import pymupdf
    try:
        doc = pymupdf.open(path)
    except Exception as exc:
        raise DocumentProcessingError('Could not open PDF. Check that it is valid and unlocked.') from exc
    with doc:
        if doc.needs_pass:
            raise DocumentProcessingError('Unlock the password-protected PDF before uploading.')
        total = len(doc)
        last = min(end_page if end_page is not None else total, total)
        if start_page < 1 or start_page > last:
            raise DocumentProcessingError(f'Choose a page range within this {total}-page PDF.')
        parts = []
        for i in range(start_page - 1, last):
            text = doc[i].get_text().replace('CamScanner', '').replace('Scanned with', '').strip()
            if len(text) < 50 and doc[i].get_images():
                raise DocumentProcessingError(
                    f'Page {i + 1} has no usable selectable text. Scanned and handwritten PDFs '
                    'are not supported. Choose text-based pages or upload typed Word/TXT notes.')
            parts.append(text)
        return {'text': clean_text('\n\n'.join(parts)), 'pages_total': total,
                'page_start': start_page, 'page_end': last}
