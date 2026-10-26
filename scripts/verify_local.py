"""Real local HTTP and model check; no mocked generation and no private source files."""
import json
import argparse
import time
from pathlib import Path
import httpx

root=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--count',type=int,default=3)
args=parser.parse_args()
config=json.loads((root/'.local/flutter-web.json').read_text(encoding='utf-8-sig'))
started=time.monotonic()
with httpx.Client(base_url=config['QUIZ_API_URL'], headers={'Authorization':'Bearer '+config['QUIZ_API_TOKEN']},
                  timeout=135, trust_env=False) as client:
    def checked(response):
        response.raise_for_status()
        return response.json()
    uploaded=checked(client.post('/documents', files={'file':('sample-study-notes.pdf',
        (root/'examples/sample-study-notes.pdf').read_bytes(), 'application/pdf')}))
    reviewed=checked(client.post('/documents/review',json={'document_id':uploaded['document_id'],'text':uploaded['text']}))
    quiz=checked(client.post('/quizzes',json={'document_id':reviewed['document_id'],'count':args.count,'difficulty':'easy'}))
    assert len(quiz['questions']) == args.count
    assert all('correct_answer' not in q for q in quiz['questions'])
    selected={q['id']:q['options'][0] for q in quiz['questions']}
    result=checked(client.post('/quizzes/'+quiz['quiz_id']+'/submit',json={'answers':selected}))
    for answer in result['review']:
        assert ' '.join(answer['source_quote'].split()) in ' '.join(uploaded['text'].split())
    correct=sum(selected[q['id']]==q['correct_answer'] for q in result['review'])
    expected=round(correct/args.count*100,2)
    assert result['score']['percentage']==expected
    report={'seconds':round(time.monotonic()-started,1),'quiz':quiz,'result':result,
            'scope':'Live local model and API integration; not a model accuracy benchmark.'}
    (root/'.local/local-verification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'seconds':report['seconds'],'questions':len(quiz['questions']),
                      'score_verified':True,'report':str(root/'.local/local-verification.json')},indent=2))
