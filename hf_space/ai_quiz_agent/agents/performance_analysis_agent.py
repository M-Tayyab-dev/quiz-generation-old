"""
agents/performance_analysis_agent.py
--------------------------------------
Agent 2: PerformanceAnalysisAgent

Responsible ONLY for:
- Interpreting quiz performance (already computed deterministically by Python)
- Explaining mistakes in plain language
- Identifying learning patterns
- Generating study recommendations

It does NOT recalculate the score or topic percentages -- those are passed
in as already-computed, trusted numbers from evaluation_service.py.
"""

from __future__ import annotations

import json
from typing import Dict, List

from pydantic import ValidationError

from ..config import get_openai_client, settings
from ..schemas.models import (
    PerformanceAnalysis,
    Question,
    Quiz,
    QuizResult,
    TopicPerformance,
)


class PerformanceAnalysisError(Exception):
    pass


SYSTEM_PROMPT = """You are an expert learning coach AI. You will be given a student's \
quiz results (already scored by deterministic software -- you must NOT recompute or \
contradict the numbers given to you). Your job is to interpret the results and produce \
constructive, specific, encouraging feedback.

Rules:
- Never make unsupported claims about the student's general ability.
- Base every statement strictly on the quiz data provided.
- Keep feedback constructive and specific, not generic.
- Recommendations must be practical and actionable.
- For each incorrect question, explain the concept the student should review.

Respond with ONLY valid JSON matching this exact schema, and nothing else:

{
  "overall_feedback": "string",
  "strong_areas": ["string", ...],
  "weak_areas": ["string", ...],
  "mistake_analysis": [
    {
      "question_id": "string",
      "student_answer": "string or null",
      "correct_answer": "string or null",
      "explanation": "string",
      "concept_to_review": "string"
    }
  ],
  "recommendations": ["string", ...]
}
"""


def _build_user_prompt(
    quiz: Quiz,
    student_answers: Dict[str, str],
    quiz_result: QuizResult,
    topic_performance: Dict[str, TopicPerformance],
    incorrect: List[Question],
) -> str:
    topic_summary = {
        t: {"total": tp.total, "correct": tp.correct, "incorrect": tp.incorrect, "percentage": tp.percentage}
        for t, tp in topic_performance.items()
    }

    mistakes = [
        {
            "question_id": q.id,
            "question": q.question,
            "student_answer": student_answers.get(q.id),
            "correct_answer": q.correct_answer,
            "topic": q.topic,
            "explanation": q.explanation,
        }
        for q in incorrect
    ]

    return f"""QUIZ SCORE (already calculated by software -- trust these numbers):
{json.dumps(quiz_result.model_dump(mode="json"), indent=2)}

TOPIC PERFORMANCE (already calculated by software -- trust these numbers):
{json.dumps(topic_summary, indent=2)}

INCORRECT QUESTIONS (source-grounded explanations included):
{json.dumps(mistakes, indent=2)}

Generate the JSON performance analysis described in the system instructions."""


class PerformanceAnalysisAgent:
    """
    Generates a validated PerformanceAnalysis from already-computed quiz results.

    Usage:
        agent = PerformanceAnalysisAgent()
        analysis = agent.analyze(quiz, student_answers, quiz_result, topic_performance, incorrect_qs)
    """

    def __init__(self, model: str | None = None, max_retries: int | None = None):
        self.model = model or settings.OPENAI_MODEL
        self.max_retries = max_retries or settings.MAX_ANALYSIS_RETRIES

    def analyze(
        self,
        quiz: Quiz,
        student_answers: Dict[str, str],
        quiz_result: QuizResult,
        topic_performance: Dict[str, TopicPerformance],
        incorrect: List[Question],
    ) -> PerformanceAnalysis:
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                raw = self._call_ai(quiz, student_answers, quiz_result, topic_performance, incorrect)
                return PerformanceAnalysis(**raw)
            except (ValidationError, json.JSONDecodeError, KeyError, ValueError) as e:
                last_error = e
                print(f"[PerformanceAnalysisAgent] Attempt {attempt}/{self.max_retries} failed: {e}")
                continue

        raise PerformanceAnalysisError(
            f"Failed to generate valid performance analysis after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )

    def _call_ai(
        self,
        quiz: Quiz,
        student_answers: Dict[str, str],
        quiz_result: QuizResult,
        topic_performance: Dict[str, TopicPerformance],
        incorrect: List[Question],
    ) -> dict:
        client = get_openai_client()
        user_prompt = _build_user_prompt(quiz, student_answers, quiz_result, topic_performance, incorrect)

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.5,
        )

        raw_text = response.choices[0].message.content
        return json.loads(raw_text)
