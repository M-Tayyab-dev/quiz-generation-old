"""
schemas/models.py
------------------
Pydantic models used across the AI Quiz Agent system.

These models are the contract between:
- The AI agents (which must produce data matching these shapes)
- The Python evaluation/progress logic (which consumes them)
- The future FastAPI layer (which will serialise/deserialise them directly)

Keeping strict validation here means invalid AI output is caught immediately,
before it can corrupt scoring or analysis.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionType(str, Enum):
    MCQ = "mcq"
    QUESTION_GENERATION = "question_generation"
    # Reserved for future extensibility (not implemented yet):
    SHORT_ANSWER = "short_answer"
    TRUE_FALSE = "true_false"
    FILL_IN_THE_BLANK = "fill_in_the_blank"


class TopicClassification(str, Enum):
    STRONG = "strong"
    AVERAGE = "average"
    WEAK = "weak"


class PerformanceLevel(str, Enum):
    EXCELLENT = "Excellent"
    VERY_GOOD = "Very Good"
    GOOD = "Good"
    NEEDS_IMPROVEMENT = "Needs Improvement"
    WEAK = "Weak"


# ---------------------------------------------------------------------------
# Question / Quiz models
# ---------------------------------------------------------------------------

class Question(BaseModel):
    """
    Full internal representation of a question, INCLUDING the correct answer.
    This must never be sent to the student before quiz submission.
    """

    id: str
    question: str = Field(min_length=3)
    options: Optional[List[str]] = None  # None for QUESTION_GENERATION mode
    correct_answer: Optional[str] = None  # None for QUESTION_GENERATION mode
    explanation: str
    topic: str
    difficulty: Difficulty
    source_quote: str = ""

    @model_validator(mode="after")
    def _validate_mcq_shape(self) -> "Question":
        if self.options is not None:
            if len(self.options) != 4:
                raise ValueError(f"Question {self.id} must have exactly 4 options.")
            if any(not option.strip() for option in self.options):
                raise ValueError("Options must not be blank.")
            if len({option.strip().casefold() for option in self.options}) != 4:
                raise ValueError(f"Question {self.id} has duplicate options.")
            if self.correct_answer is None:
                raise ValueError(f"Question {self.id} is missing a correct_answer.")
            if self.correct_answer not in self.options:
                raise ValueError(
                    f"Question {self.id}: correct_answer does not match any option."
                )
        return self


class QuizDisplayQuestion(BaseModel):
    """
    Student-facing view of a question. NEVER includes correct_answer or explanation.
    """

    id: str
    question: str
    options: Optional[List[str]] = None
    topic: str

    @classmethod
    def from_question(cls, q: "Question") -> "QuizDisplayQuestion":
        return cls(id=q.id, question=q.question, options=q.options, topic=q.topic)


class Quiz(BaseModel):
    quiz_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    student_id: str
    document_id: str
    difficulty: Difficulty
    question_count: int = Field(ge=1, le=50)
    question_type: QuestionType
    questions: List[Question]
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def _validate_question_count(self) -> "Quiz":
        if len(self.questions) != self.question_count:
            raise ValueError(
                f"Expected {self.question_count} questions, got {len(self.questions)}."
            )
        # No duplicate questions (by normalised question text)
        seen = set()
        seen_ids = set()
        if self.question_type not in (QuestionType.MCQ, QuestionType.QUESTION_GENERATION):
            raise ValueError("This question type is not implemented yet.")
        for q in self.questions:
            if q.id in seen_ids:
                raise ValueError(f"Duplicate question id: {q.id}")
            seen_ids.add(q.id)
            if self.question_type == QuestionType.MCQ and q.options is None:
                raise ValueError(f"MCQ {q.id} must include options and an answer.")
            key = q.question.strip().lower()
            if key in seen:
                raise ValueError(f"Duplicate question detected: {q.question!r}")
            seen.add(key)
        return self

    def to_display(self) -> List[QuizDisplayQuestion]:
        """Return the safe, student-facing version of this quiz (no answers)."""
        return [QuizDisplayQuestion.from_question(q) for q in self.questions]

    def answer_key(self) -> Dict[str, Optional[str]]:
        """Backend-only mapping of question id -> correct answer."""
        return {q.id: q.correct_answer for q in self.questions}

    def topic_map(self) -> Dict[str, str]:
        return {q.id: q.topic for q in self.questions}


# ---------------------------------------------------------------------------
# Answers / Evaluation models
# ---------------------------------------------------------------------------

class StudentAnswer(BaseModel):
    """Wrapper around the raw {question_id: answer} dict submitted by a student."""

    answers: Dict[str, str]


class QuizResult(BaseModel):
    total_questions: int
    correct_answers: int
    incorrect_answers: int
    unanswered: int
    percentage: float
    performance_level: PerformanceLevel

    @field_validator("percentage")
    @classmethod
    def _round_percentage(cls, v: float) -> float:
        return round(v, 2)


class TopicPerformance(BaseModel):
    topic: str
    total: int
    correct: int
    incorrect: int
    percentage: float
    classification: TopicClassification

    @field_validator("percentage")
    @classmethod
    def _round_percentage(cls, v: float) -> float:
        return round(v, 2)


# ---------------------------------------------------------------------------
# AI Performance Analysis models
# ---------------------------------------------------------------------------

class MistakeAnalysisItem(BaseModel):
    question_id: str
    student_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    explanation: str
    concept_to_review: str


class PerformanceAnalysis(BaseModel):
    overall_feedback: str
    strong_areas: List[str]
    weak_areas: List[str]
    mistake_analysis: List[MistakeAnalysisItem]
    recommendations: List[str]


# ---------------------------------------------------------------------------
# Progress tracking models
# ---------------------------------------------------------------------------

class ProgressRecord(BaseModel):
    """One row of quiz history for a student, used to build progress reports."""

    student_id: str
    quiz_id: str
    document_id: str
    score: int  # correct_answers count
    percentage: float
    difficulty: Difficulty
    date: datetime = Field(default_factory=datetime.utcnow)
    topic_performance: Dict[str, TopicPerformance]


class ProgressSummary(BaseModel):
    total_quizzes: int
    average_score: float
    highest_score: float
    lowest_score: float
    recent_scores: List[float]
    strong_topics: List[str]
    weak_topics: List[str]


class TopicImprovement(BaseModel):
    topic: str
    history: List[float]  # chronological percentages
    change_points: float  # last - first
    summary: str


class RecommendedNextQuiz(BaseModel):
    recommended_topic: str
    recommended_difficulty: Difficulty
    recommended_question_count: int
    reason: str
