"""
services/quiz_service.py
--------------------------
Manages Quiz sessions: creating them (via the QuizGenerationAgent) and
retrieving a previously generated quiz by its ID.

In-memory storage for the Jupyter prototype; swap for SQLAlchemy later
without changing the public API (create_quiz / get_quiz).
"""

from __future__ import annotations

from typing import Dict, Optional

from ..agents.quiz_generation_agent import QuizGenerationAgent
from ..schemas.models import Difficulty, Quiz, QuestionType


class QuizNotFoundError(Exception):
    pass


class QuizSessionStore:
    """Simple in-memory quiz_id -> Quiz store."""

    def __init__(self):
        self._quizzes: Dict[str, Quiz] = {}

    def save(self, quiz: Quiz) -> Quiz:
        self._quizzes[quiz.quiz_id] = quiz
        return quiz

    def get(self, quiz_id: str) -> Quiz:
        quiz = self._quizzes.get(quiz_id)
        if quiz is None:
            raise QuizNotFoundError(f"No quiz found with id: {quiz_id}")
        return quiz

    def get_or_none(self, quiz_id: str) -> Optional[Quiz]:
        return self._quizzes.get(quiz_id)


def create_quiz(
    store: QuizSessionStore,
    agent: QuizGenerationAgent,
    content: str,
    difficulty: Difficulty,
    question_count: int,
    question_type: QuestionType,
    student_id: str,
    document_id: str,
) -> Quiz:
    """Generate a quiz via the AI agent, validate it, store it, and return it."""
    quiz = agent.generate_quiz(
        content=content,
        difficulty=difficulty,
        question_count=question_count,
        question_type=question_type,
        student_id=student_id,
        document_id=document_id,
    )
    store.save(quiz)
    return quiz
