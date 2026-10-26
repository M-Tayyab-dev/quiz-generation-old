"""Live HF smoke check; no mocked generation or provider calls."""
import json
import os
import tempfile
from pathlib import Path
from ai_quiz_agent.workflow import QuizWorkflow

os.environ["AI_PROVIDER"] = "huggingface"
# Default verifies the same pretrained model used by the UI.
# Set HF_ADAPTER explicitly only when evaluating an experimental adapter.

with tempfile.TemporaryDirectory() as tmp:
    app = QuizWorkflow(Path(tmp)/"verification.sqlite3")
    uploaded = app.upload("practice_notes.txt", Path("examples/practice_notes.txt").read_bytes())
    quiz = app.generate(uploaded["document_id"], count=1, difficulty="easy", subject="Mathematics and Reasoning", on_progress=print)
    assert "correct_answer" not in quiz["questions"][0]
    internal = app.get(quiz["quiz_id"], "quiz")["quiz"]
    key = {q["id"]:q["correct_answer"] for q in internal["questions"]}
    report = app.submit(quiz["quiz_id"], key)
    assert report["score"]["percentage"] == 100
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/live-verification.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print("PASS: live model generation, safe quiz display, submission, scoring and saved result.")
    print("This checks software integration; model factual accuracy still needs independent review.")
