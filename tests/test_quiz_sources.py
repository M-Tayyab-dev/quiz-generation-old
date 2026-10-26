import unittest
from ai_quiz_agent.services.quiz_sources import select_sentences


class SourceSelectionTests(unittest.TestCase):
    def test_document_instructions_are_not_selected_as_facts(self):
        text = ('This authored handout is for testing document uploads. '
                'Every answer must be supported by the notes below. '
                'The heart pumps blood around the body. '
                'The lungs exchange oxygen during breathing. '
                'The kidneys filter waste from the blood.')
        sources = select_sentences(text, 3)
        self.assertEqual(len(sources), 3)
        self.assertTrue(all(s in text for s in sources))
        self.assertFalse(any('handout' in s or 'Every answer' in s for s in sources))

    def test_insufficient_facts_fail_before_model_request(self):
        with self.assertRaisesRegex(ValueError, 'only 1'):
            select_sentences('This document is for testing only. The heart pumps blood around the body.', 3)
