"""Run the real local model without FastAPI, Flutter, or hidden retries."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['AI_PROVIDER'] = 'local'

import httpx
from ai_quiz_agent.agents.quiz_generation_agent import QuizGenerationAgent
from ai_quiz_agent.generation_control import bounded_generation
from ai_quiz_agent.schemas.models import Difficulty, QuestionType


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT / 'examples/sample-study-notes.txt')
    parser.add_argument('--count', type=int, default=3)
    parser.add_argument('--runs', type=int, default=2)
    parser.add_argument('--output', type=Path, default=ROOT / '.local/model-benchmark.json')
    args = parser.parse_args()
    text = args.input.read_text(encoding='utf-8-sig')
    # Model loading is separate from generation latency. Never mistake a closed
    # port or loading response for a completed generation benchmark.
    url = os.getenv('LOCAL_MODEL_URL', 'http://127.0.0.1:8081/v1/chat/completions')
    health_url = url.split('/v1/', 1)[0] + '/health'
    try:
        ready = httpx.get(health_url, timeout=5, trust_env=False)
        ready.raise_for_status()
        template = httpx.post(url.split('/v1/', 1)[0] + '/apply-template',
            json={'messages': [{'role': 'system', 'content': 'SYSTEM_CHECK'},
                               {'role': 'user', 'content': 'USER_CHECK'}]},
            timeout=5, trust_env=False)
        template.raise_for_status()
        if '<|im_start|>system\nSYSTEM_CHECK' not in template.json()['prompt']:
            print('Incorrect Qwen chat template. Restart the model with --chat-template chatml.', flush=True)
            return 2
    except httpx.HTTPError as exc:
        print(f'Model is not ready: {exc}. Start scripts/start_local.ps1 and wait for model loading.', flush=True)
        return 2
    results = []
    real_post = httpx.post
    for run in range(1, args.runs + 1):
        metrics = []

        def measured_post(*a, **kw):
            started = time.perf_counter()
            response = real_post(*a, **kw)
            payload = response.json()
            metrics.append({'seconds': round(time.perf_counter() - started, 2),
                            'usage': payload.get('usage'), 'timings': payload.get('timings'),
                            'finish_reason': payload.get('choices', [{}])[0].get('finish_reason'),
                            'raw_response': payload.get('choices', [{}])[0].get('message')})
            return response

        started = time.perf_counter()
        result = {'run': run, 'count': args.count, 'input': str(args.input), 'model_calls': metrics}
        print(f'Run {run}: {args.count} questions, model only, no retries', flush=True)
        try:
            with patch('httpx.post', side_effect=measured_post):
                quiz = bounded_generation(QuizGenerationAgent(max_retries=1).generate_quiz)(
                    text, Difficulty.EASY, args.count, QuestionType.MCQ, 'benchmark', 'benchmark')
            result.update(status='structural_validation_passed', quiz=quiz.model_dump(mode='json'))
        except Exception as exc:
            result.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        result['seconds'] = round(time.perf_counter() - started, 2)
        results.append(result)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({'note': 'Structural validation is not a semantic quality guarantee.',
                                          'runs': results}, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"{result['status']}: {result['seconds']} seconds", flush=True)
    print(f'Results: {args.output}', flush=True)
    return 0 if all(r['status'] == 'structural_validation_passed' for r in results) else 1


if __name__ == '__main__':
    sys.exit(main())
