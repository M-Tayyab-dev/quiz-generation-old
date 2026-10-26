import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from ai_quiz_agent.api.app import app, workflow
from ai_quiz_agent.workflow import QuizWorkflow


class ApiTests(unittest.TestCase):
    def test_auth_upload_and_answer_hiding(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"QUIZ_API_TOKEN":"test-token"}):
            flow = QuizWorkflow(Path(tmp)/'db.sqlite3')
            app.dependency_overrides.clear()
            with patch('ai_quiz_agent.api.app.workflow', return_value=flow):
                client = TestClient(app)
                self.assertEqual(client.get('/profiles').status_code,401)
                headers = {"Authorization":"Bearer test-token"}
                response = client.post('/documents', headers=headers, files={'file':('notes.txt',b'RAM stores working data. '*12,'text/plain')})
                self.assertEqual(response.status_code,200)
                raw = dict(id='q1',question='Which stores working data?',options=['RAM','Fan','Cable','Case'],
                    correct_answer='RAM',explanation='RAM stores working data.',source_quote='RAM stores working data.',
                    topic='Memory',difficulty='easy')
                with patch.object(flow.agent,'_call_ai',return_value=[raw]):
                    generated=client.post('/quizzes',headers=headers,json={'document_id':response.json()['document_id'],'count':1})
                self.assertEqual(generated.status_code,200)
                quiz = generated.json()
                self.assertNotIn('correct_answer',quiz['questions'][0])
                result=client.post('/quizzes/'+quiz['quiz_id']+'/submit',headers=headers,json={'answers':{'q1':'RAM'}})
                self.assertEqual(result.json()['score']['percentage'],100)
