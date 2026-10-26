"""
services/evaluation_service.py
--------------------------------
100% deterministic Python logic for:
- Evaluating a submitted quiz against the answer key
- Calculating score / percentage / performance level
- Topic-wise performance breakdown
- Strong / average / weak topic classification

The AI is NEVER used for scoring. This keeps grading fair, auditable,
and reproducible.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from ..schemas.models import (
    PerformanceLevel,
    Question,
    Quiz,
    QuizResult,
    TopicClassification,
    TopicPerformance,
    QuestionType,
)


class EvaluationError(Exception):
    pass


# ---------------------------------------------------------------------------
# Score calculation
# ---------------------------------------------------------------------------

def performance_level_for(percentage: float) -> PerformanceLevel:
    if percentage >= 90:
        return PerformanceLevel.EXCELLENT
    if percentage >= 80:
        return PerformanceLevel.VERY_GOOD
    if percentage >= 70:
        return PerformanceLevel.GOOD
    if percentage >= 60:
        return PerformanceLevel.NEEDS_IMPROVEMENT
    return PerformanceLevel.WEAK


def _validate_answers(quiz: Quiz, student_answers: Dict[str, str]) -> None:
    if quiz.question_type != QuestionType.MCQ:
        raise EvaluationError("Only MCQs can be automatically scored.")
    valid_ids = {q.id for q in quiz.questions}
    for qid in student_answers:
        if qid not in valid_ids:
            raise EvaluationError(f"Answer submitted for unknown question id: {qid}")
        question = next(q for q in quiz.questions if q.id == qid)
        if student_answers[qid] and student_answers[qid] not in question.options:
            raise EvaluationError(f"Answer for {qid} is not one of its options.")


def grade_questions(quiz: Quiz, student_answers: Dict[str, str]) -> Dict[str, bool | None]:
    """
    Returns {question_id: True/False/None}
    None means unanswered. Only meaningful for MCQ questions with a correct_answer.
    """
    _validate_answers(quiz, student_answers)

    grades: Dict[str, bool | None] = {}
    for q in quiz.questions:
        student_answer = student_answers.get(q.id)
        if student_answer is None or student_answer == "":
            grades[q.id] = None
            continue
        if q.correct_answer is None:
            # Open-ended question_generation mode: not auto-gradable.
            grades[q.id] = None
            continue
        grades[q.id] = (student_answer.strip() == q.correct_answer.strip())

    return grades


def evaluate_quiz(quiz: Quiz, student_answers: Dict[str, str]) -> Tuple[QuizResult, Dict[str, bool | None]]:
    """
    Compare student answers against the answer key using deterministic logic.
    Returns (QuizResult, per_question_grades).
    """
    grades = grade_questions(quiz, student_answers)

    total = len(quiz.questions)
    correct = sum(1 for v in grades.values() if v is True)
    incorrect = sum(1 for v in grades.values() if v is False)
    unanswered = sum(1 for v in grades.values() if v is None)

    percentage = round((correct / total) * 100, 2) if total > 0 else 0.0

    result = QuizResult(
        total_questions=total,
        correct_answers=correct,
        incorrect_answers=incorrect,
        unanswered=unanswered,
        percentage=percentage,
        performance_level=performance_level_for(percentage),
    )
    return result, grades


# ---------------------------------------------------------------------------
# Topic-wise analysis
# ---------------------------------------------------------------------------

def classify_topic(percentage: float) -> TopicClassification:
    if percentage >= 80:
        return TopicClassification.STRONG
    if percentage >= 60:
        return TopicClassification.AVERAGE
    return TopicClassification.WEAK


def calculate_topic_performance(
    quiz: Quiz, grades: Dict[str, bool | None]
) -> Dict[str, TopicPerformance]:
    """
    Aggregate per-question grades into per-topic totals/correct/incorrect/percentage,
    then classify each topic as strong / average / weak.

    Unanswered questions count toward `total` but not `correct`.
    """
    buckets: Dict[str, Dict[str, int]] = {}

    for q in quiz.questions:
        bucket = buckets.setdefault(q.topic, {"total": 0, "correct": 0, "incorrect": 0})
        bucket["total"] += 1
        grade = grades.get(q.id)
        if grade is True:
            bucket["correct"] += 1
        elif grade is False:
            bucket["incorrect"] += 1
        # grade is None (unanswered) -> counted in total only

    topic_performance: Dict[str, TopicPerformance] = {}
    for topic, counts in buckets.items():
        pct = round((counts["correct"] / counts["total"]) * 100, 2) if counts["total"] else 0.0
        topic_performance[topic] = TopicPerformance(
            topic=topic,
            total=counts["total"],
            correct=counts["correct"],
            incorrect=counts["incorrect"],
            percentage=pct,
            classification=classify_topic(pct),
        )

    return topic_performance


def split_strong_average_weak(
    topic_performance: Dict[str, TopicPerformance],
) -> Tuple[List[str], List[str], List[str]]:
    strong = [t for t, tp in topic_performance.items() if tp.classification == TopicClassification.STRONG]
    average = [t for t, tp in topic_performance.items() if tp.classification == TopicClassification.AVERAGE]
    weak = [t for t, tp in topic_performance.items() if tp.classification == TopicClassification.WEAK]
    return strong, average, weak


def incorrect_questions(quiz: Quiz, grades: Dict[str, bool | None]) -> List[Question]:
    return [q for q in quiz.questions if grades.get(q.id) is False]
