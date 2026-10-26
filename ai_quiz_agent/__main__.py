"""Run from the workspace root: python -m ai_quiz_agent material.txt."""
import argparse
import json
import sys
from pathlib import Path

from .agents.quiz_generation_agent import QuizGenerationAgent
from .schemas.models import Difficulty, QuestionType
from .services.document_service import process_document


def main():
    parser = argparse.ArgumentParser(description="Generate a quiz from PDF, DOCX or TXT.")
    parser.add_argument("document", type=Path)
    parser.add_argument("--count", type=int, default=5, choices=range(1, 51), metavar="1-50")
    parser.add_argument("--difficulty", choices=[d.value for d in Difficulty], default="medium")
    parser.add_argument("--output", type=Path, default=Path("quiz-output.json"))
    args = parser.parse_args()
    try:
        content = process_document(str(args.document))
        quiz = QuizGenerationAgent().generate_quiz(
            content, Difficulty(args.difficulty), args.count, QuestionType.MCQ,
            student_id="local-student", document_id=args.document.name,
        )
        args.output.write_text(json.dumps(quiz.model_dump(mode="json"), indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"Quiz generation failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1
    print(f"Saved quiz and answer key to {args.output.resolve()} (teacher/backend use only).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
