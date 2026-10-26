import os
import unittest
from unittest.mock import Mock, patch

from ai_quiz_agent.providers import complete_json


class LocalProviderTests(unittest.TestCase):
    @patch.dict(os.environ, {'AI_PROVIDER': 'local'})
    def test_schema_is_sent_to_decoder(self):
        response = Mock()
        response.json.return_value = {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"items":[]}'}}]}
        schema = {'type': 'object'}
        with patch('httpx.post', return_value=response) as post:
            self.assertEqual(complete_json('system', 'source', json_schema=schema), {'items': []})
        self.assertEqual(post.call_args.kwargs['json']['response_format']['schema'], schema)

    @patch.dict(os.environ, {'AI_PROVIDER': 'local'})
    def test_truncated_output_is_not_accepted_as_finished_quiz(self):
        response = Mock()
        response.json.return_value = {'choices': [{'finish_reason': 'length', 'message': {'content': '{"items":[]}'}}]}
        with patch('httpx.post', return_value=response):
            with self.assertRaisesRegex(ValueError, 'output limit'):
                complete_json('system', 'source')
