import unittest
from unittest.mock import patch
from ai_quiz_agent.agents.quiz_generation_agent import QuizGenerationAgent, QuizGenerationError
from ai_quiz_agent.schemas.models import Difficulty, QuestionType

TEXT = 'RAM stores temporary working data. An SSD stores files without power. A keyboard is an input device.'


class CompactGenerationTests(unittest.TestCase):
    def test_one_model_call_generates_batch_and_attaches_exact_quotes(self):
        data = {'items': [
            {'s': 0, 'q': 'What stores temporary working data?', 'a': 'RAM', 'd': ['SSD', 'Keyboard', 'Monitor']},
            {'s': 1, 'q': 'What stores files without power?', 'a': 'SSD', 'd': ['RAM', 'Keyboard', 'Monitor']},
            {'s': 2, 'q': 'Which input device is named?', 'a': 'keyboard', 'd': ['Monitor', 'SSD', 'RAM']},
        ]}
        with patch('ai_quiz_agent.agents.quiz_generation_agent.complete_json', return_value=data) as model:
            quiz = QuizGenerationAgent(max_retries=1).generate_quiz(TEXT, Difficulty.EASY, 3, QuestionType.MCQ, 's', 'd')
        model.assert_called_once()
        self.assertEqual(len(quiz.questions), 3)
        for q in quiz.questions:
            self.assertIn(q.source_quote, TEXT)
            self.assertEqual(len(set(q.options)), 4)

    def test_unsupported_answer_is_rejected(self):
        data = {'items': [{'s': 0, 'q': 'What stores data?', 'a': 'Invented fact', 'd': ['A', 'B', 'C']}]}
        with patch('ai_quiz_agent.agents.quiz_generation_agent.complete_json', return_value=data):
            with self.assertRaisesRegex(QuizGenerationError, 'not supported'):
                QuizGenerationAgent(max_retries=1).generate_quiz(TEXT, Difficulty.EASY, 1, QuestionType.MCQ, 's', 'd')
