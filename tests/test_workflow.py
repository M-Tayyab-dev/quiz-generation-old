import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from ai_quiz_agent.workflow import QuizWorkflow
from ai_quiz_agent.services.document_service import chunk_text, select_relevant_chunks
from ai_quiz_agent.services.evaluation_service import EvaluationError

PASSAGE = 'RAM stores working data. ' * 12
QUESTION = dict(id='q1', question='Which stores working data?', options=['RAM','Fan','Case','Cable'],
    correct_answer='RAM', explanation='The notes describe RAM as working storage.', topic='Memory',
    difficulty='easy', source_quote='RAM stores working data.')


class WorkflowTests(unittest.TestCase):
    def test_upload_generate_submit_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp)/'test.sqlite3'
            flow = QuizWorkflow(db)
            doc = flow.upload('notes.txt', PASSAGE.encode())
            with patch.object(flow.agent, '_call_ai', return_value=[QUESTION]):
                quiz = flow.generate(doc['document_id'], count=1, difficulty='easy')
            self.assertNotIn('correct_answer', quiz['questions'][0])
            self.assertNotIn('source_quote', quiz['questions'][0])
            with self.assertRaises(EvaluationError):
                flow.submit(quiz['quiz_id'], {'q1':'not an option'})
            result = flow.submit(quiz['quiz_id'], {'q1':'RAM'})
            self.assertEqual(result['score']['percentage'], 100)
            reopened = QuizWorkflow(db)
            self.assertEqual(reopened.submit(quiz['quiz_id'], {'q1':'Fan'}), result)
            self.assertEqual(len(reopened.history()), 1)

    def test_document_bounds(self):
        text = 'a'*19000
        chunks = chunk_text(text, 1000, 100)
        self.assertTrue(all(len(c.text)<=1000 for c in chunks))
        self.assertLessEqual(len(select_relevant_chunks(chunks, 1200)), 1200)
        with self.assertRaises(ValueError):
            chunk_text(text, 10, 10)

    def test_pdf_and_word_upload(self):
        import fitz
        from docx import Document
        with tempfile.TemporaryDirectory() as tmp:
            flow = QuizWorkflow(Path(tmp)/'db.sqlite3')
            pdf = fitz.open()
            page = pdf.new_page()
            page.insert_textbox(fitz.Rect(40,40,500,700), PASSAGE)
            self.assertGreater(flow.upload('notes.pdf', pdf.tobytes())['characters'], 200)
            pdf.close()
            doc = Document()
            doc.add_paragraph(PASSAGE)
            path = Path(tmp)/'notes.docx'
            doc.save(path)
            self.assertGreater(flow.upload('notes.docx',path.read_bytes())['characters'],200)

    def test_bad_uploads(self):
        with tempfile.TemporaryDirectory() as tmp:
            flow = QuizWorkflow(Path(tmp)/'test.sqlite3')
            for name,data in [('file.doc',b'abc'),('empty.txt',b''),('short.txt',b'abc')]:
                with self.assertRaises(Exception):
                    flow.upload(name,data)
