import unittest
from unittest.mock import patch

from pydantic import ValidationError
from ai_quiz_agent.agents.quiz_generation_agent import QuizGenerationAgent, QuizGenerationError
from ai_quiz_agent.schemas.models import Difficulty, QuestionType, Quiz
from ai_quiz_agent.services.evaluation_service import evaluate_quiz


class QuizTests(unittest.TestCase):
    def fixture(self):
        return dict(student_id="test", document_id="test", difficulty="easy",
                    question_count=1, question_type="mcq", questions=[dict(
                        id="q1", question="Which stores data?", options=["RAM", "Fan", "Cable", "Case"],
                        correct_answer="RAM", explanation="RAM stores working data.",
                        topic="Memory", difficulty="easy", source_quote="RAM stores working data.")])

    def test_generation_display_and_scoring(self):
        raw = self.fixture()["questions"]
        with patch.object(QuizGenerationAgent, "_call_ai", return_value=raw):
            quiz = QuizGenerationAgent().generate_quiz("RAM stores working data.", Difficulty.EASY,
                    1, QuestionType.MCQ, "test", "test")
        display = quiz.to_display()[0].model_dump()
        self.assertNotIn("correct_answer", display)
        self.assertNotIn("explanation", display)
        self.assertEqual(evaluate_quiz(quiz, {"q1": "RAM"})[0].percentage, 100)
        self.assertEqual(evaluate_quiz(quiz, {"q1": "Fan"})[0].incorrect_answers, 1)
        self.assertEqual(evaluate_quiz(quiz, {})[0].unanswered, 1)

    def test_mcq_without_options_rejected(self):
        data = self.fixture()
        data["questions"][0]["options"] = None
        with self.assertRaises(ValidationError):
            Quiz(**data)

    def test_easy_answer_must_be_in_source_quote(self):
        raw = self.fixture()["questions"]
        raw[0]["correct_answer"] = "Fan"
        with patch.object(QuizGenerationAgent, "_call_ai", return_value=raw):
            with self.assertRaisesRegex(QuizGenerationError, "Easy recall answers"):
                QuizGenerationAgent(max_retries=1).generate_quiz(
                    "RAM stores working data.", Difficulty.EASY, 1, QuestionType.MCQ, "test", "test")

    def test_duplicate_ids_rejected(self):
        data = self.fixture()
        second = dict(data["questions"][0], question="Which is working memory?")
        data["questions"].append(second)
        data["question_count"] = 2
        with self.assertRaises(ValidationError):
            Quiz(**data)


if __name__ == "__main__":
    unittest.main()
