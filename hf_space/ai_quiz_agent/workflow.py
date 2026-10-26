"""Shared upload -> generation -> solve -> review workflow for Colab and API."""
import json
import sqlite3
import tempfile
import uuid
from contextlib import contextmanager
from pathlib import Path

from .generation_control import bounded_generation, remaining_seconds
from .agents.quiz_generation_agent import QuizGenerationAgent
from .schemas.models import Difficulty, QuestionType, Quiz
from .services.document_service import clean_text, extract_text, validate_content, chunk_text
from .services.evaluation_service import evaluate_quiz, calculate_topic_performance

class QuizWorkflow:
    def __init__(self, db_path="quiz-data.sqlite3", agent=None):
        self.db_path = str(db_path)
        self.agent = agent or QuizGenerationAgent()
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS items (id TEXT PRIMARY KEY, kind TEXT, payload TEXT)")

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.db_path, timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, key, kind, value):
        with self.db() as db:
            db.execute("INSERT OR REPLACE INTO items VALUES (?, ?, ?)", (key, kind, json.dumps(value)))

    def get(self, key, kind):
        with self.db() as db:
            row = db.execute("SELECT payload FROM items WHERE id=? AND kind=?", (key, kind)).fetchone()
        if row is None:
            raise KeyError("Item not found")
        return json.loads(row[0])

    def upload(self, filename, data, start_page=1, end_page=None):
        suffix = Path(filename).suffix.lower()
        if suffix not in {".pdf", ".docx", ".txt"}:
            raise ValueError("Upload PDF, Word .docx, or TXT. Save legacy .doc files as .docx first.")
        if not data or len(data) > 25 * 1024 * 1024:
            raise ValueError("Upload a nonempty file of at most 25 MB.")
        metadata = {}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ("document" + suffix)
            path.write_bytes(data)
            if suffix == '.pdf':
                from .services.pdf_service import extract_pdf
                metadata = extract_pdf(str(path), start_page, end_page)
                text = metadata.pop('text')
            else:
                text = clean_text(extract_text(str(path)))
        validate_content(text)
        if len(text) > 1_000_000:
            raise ValueError("Document exceeds one million extracted characters; split it into sections.")
        key = str(uuid.uuid4())
        self.save(key, "document", {"filename": Path(filename).name, "text": text,
                                  'requires_review': False})
        return {"document_id": key, "filename": Path(filename).name, "characters": len(text),
                'text': text, 'requires_review': False, **metadata}

    def review_document(self, document_id, text):
        original = self.get(document_id, 'document')
        text = clean_text(text)
        validate_content(text)
        if len(text) > 1_000_000:
            raise ValueError('Reviewed text is too long. Select fewer pages.')
        key = str(uuid.uuid4())
        self.save(key, 'document', {'filename': original['filename'], 'text': text,
                                   'requires_review': False, 'reviewed_from': document_id})
        return {'document_id': key, 'characters': len(text)}

    @bounded_generation
    def generate(self, document_id, count=5, difficulty="medium", language="English", on_progress=None):
        if not 1 <= count <= 30:
            raise ValueError("Choose 1 to 30 MCQs per practice quiz.")
        if language not in ("English", "Urdu"):
            raise ValueError("Choose English or Urdu.")
        difficulty = Difficulty(difficulty)
        document = self.get(document_id, "document")
        if document.get('requires_review'):
            raise ValueError('Review and confirm this previously uploaded document before generating a quiz.')
        if on_progress:
            on_progress(f"Generating {count} questions in one request...")
        remaining_seconds()
        quiz = self.agent.generate_quiz(document["text"], difficulty, count, QuestionType.MCQ,
                                        "local-student", document_id)
        self.save(quiz.quiz_id, "quiz", {"quiz": quiz.model_dump(mode="json"),
                  "language": language})
        return self.display(quiz.quiz_id)

    def display(self, quiz_id):
        record = self.get(quiz_id, "quiz")
        quiz = Quiz(**record["quiz"])
        return {"quiz_id": quiz_id,
                "questions": [q.model_dump() for q in quiz.to_display()]}

    def submit(self, quiz_id, answers):
        # Exactly one stored result per generated quiz; retry with a newly generated quiz.
        try:
            return self.get("result:" + quiz_id, "result")
        except KeyError:
            pass
        quiz = Quiz(**self.get(quiz_id, "quiz")["quiz"])
        score, grades = evaluate_quiz(quiz, answers)
        topics = calculate_topic_performance(quiz, grades)
        weak = [name for name, stats in topics.items() if stats.percentage < 60]
        result = {"quiz_id": quiz_id, "score": score.model_dump(mode="json"),
                  "grade": next(g for cutoff, g in [(90,"A+"),(80,"A"),(70,"B"),(60,"C"),(50,"D"),(0,"F")]
                                if score.percentage >= cutoff),
                  "grade_note": "Practice rubric, not an official exam grade or pass decision.",
                  "topics": {k:v.model_dump(mode="json") for k,v in topics.items()},
                  "recommendations": [f"Review {t} in your source and try a fresh practice quiz." for t in weak]
                     or ["Review any missed questions, then try a harder quiz using the same material."],
                  "review": [{**q.model_dump(mode="json"), "student_answer": answers.get(q.id),
                              "correct": grades[q.id]} for q in quiz.questions]}
        # Separate result key prevents overwriting the quiz row.
        with self.db() as db:
            db.execute("INSERT OR IGNORE INTO items VALUES (?, ?, ?)",
                       ("result:" + quiz_id, "result", json.dumps(result)))
        return self.get("result:" + quiz_id, "result")

    def history(self):
        with self.db() as db:
            rows = db.execute("SELECT payload FROM items WHERE kind='result' ORDER BY rowid DESC").fetchall()
        return [{"quiz_id": r["quiz_id"], "score": r["score"], "grade": r["grade"]}
                for r in (json.loads(row[0]) for row in rows)]
