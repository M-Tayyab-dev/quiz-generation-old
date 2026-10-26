import tempfile
import unittest
from pathlib import Path

from ai_quiz_agent.workflow import QuizWorkflow
from ai_quiz_agent.services.pdf_service import extract_pdf
from ai_quiz_agent.services.document_service import DocumentProcessingError


class PdfTests(unittest.TestCase):
    def test_scanned_pdf_rejected_instead_of_ocr(self):
        with tempfile.TemporaryDirectory() as tmp:
            flow = QuizWorkflow(Path(tmp) / 'test.sqlite3')
            with self.assertRaisesRegex(DocumentProcessingError, 'not supported'):
                flow.upload('scan.pdf', Path('examples/sample-scanned-notes.pdf').read_bytes())

    def test_selected_text_page_and_invalid_range(self):
        path = Path('examples/sample-study-notes.pdf')
        result = extract_pdf(path, 1, 1)
        self.assertIn('Evaporation', result['text'])
        self.assertEqual(result['page_end'], 1)
        with self.assertRaises(DocumentProcessingError):
            extract_pdf(path, 0, 1)
        with self.assertRaises(DocumentProcessingError):
            extract_pdf(path, 1, 0)

    def test_review_preserves_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            flow = QuizWorkflow(Path(tmp) / 'test.sqlite3')
            original = 'RAM stores working data. ' * 12
            doc = flow.upload('notes.txt', original.encode())
            corrected = 'RAM is volatile memory. ' * 12
            reviewed = flow.review_document(doc['document_id'], corrected)
            self.assertNotEqual(reviewed['document_id'], doc['document_id'])
            self.assertEqual(flow.get(doc['document_id'], 'document')['text'], original.strip())
            self.assertEqual(flow.get(reviewed['document_id'], 'document')['text'], corrected.strip())
