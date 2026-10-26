"""
services/progress_service.py
------------------------------
Tracks a student's quiz history over time and computes progress statistics.

In this Jupyter/prototype version storage is in-memory (a Python dict).
The class is written so that swapping the storage for SQLite/SQLAlchemy
later only requires changing the internals of ProgressTracker, not its
public API -- which is what the future FastAPI service layer will call.

All numerical calculations here are deterministic Python. The AI may be
used elsewhere to *interpret* these numbers, but never to compute them.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List

from ..schemas.models import (
    Difficulty,
    ProgressRecord,
    ProgressSummary,
    Quiz,
    QuizResult,
    RecommendedNextQuiz,
    TopicClassification,
    TopicImprovement,
    TopicPerformance,
)


class ProgressTracker:
    """In-memory store of ProgressRecord objects, keyed by student_id."""

    def __init__(self):
        self._records: Dict[str, List[ProgressRecord]] = defaultdict(list)

    # -- writing ----------------------------------------------------------

    def add_result(
        self,
        student_id: str,
        quiz: Quiz,
        quiz_result: QuizResult,
        topic_performance: Dict[str, TopicPerformance],
    ) -> ProgressRecord:
        record = ProgressRecord(
            student_id=student_id,
            quiz_id=quiz.quiz_id,
            document_id=quiz.document_id,
            score=quiz_result.correct_answers,
            percentage=quiz_result.percentage,
            difficulty=quiz.difficulty,
            topic_performance=topic_performance,
        )
        self._records[student_id].append(record)
        return record

    # -- reading ------------------------------------------------------------

    def history(self, student_id: str) -> List[ProgressRecord]:
        return sorted(self._records.get(student_id, []), key=lambda r: r.date)

    def get_summary(self, student_id: str, recent_n: int = 5) -> ProgressSummary:
        records = self.history(student_id)

        if not records:
            return ProgressSummary(
                total_quizzes=0,
                average_score=0.0,
                highest_score=0.0,
                lowest_score=0.0,
                recent_scores=[],
                strong_topics=[],
                weak_topics=[],
            )

        percentages = [r.percentage for r in records]
        average_score = round(sum(percentages) / len(percentages), 2)
        highest_score = max(percentages)
        lowest_score = min(percentages)
        recent_scores = percentages[-recent_n:]

        # Aggregate topic performance across ALL quizzes to find overall
        # strong/weak topics (weighted by total questions attempted per topic).
        topic_totals: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "correct": 0})
        for record in records:
            for topic, tp in record.topic_performance.items():
                topic_totals[topic]["total"] += tp.total
                topic_totals[topic]["correct"] += tp.correct

        strong_topics: List[str] = []
        weak_topics: List[str] = []
        for topic, counts in topic_totals.items():
            pct = (counts["correct"] / counts["total"]) * 100 if counts["total"] else 0
            if pct >= 80:
                strong_topics.append(topic)
            elif pct < 60:
                weak_topics.append(topic)

        return ProgressSummary(
            total_quizzes=len(records),
            average_score=average_score,
            highest_score=highest_score,
            lowest_score=lowest_score,
            recent_scores=recent_scores,
            strong_topics=strong_topics,
            weak_topics=weak_topics,
        )

    def topic_improvement(self, student_id: str, topic: str) -> TopicImprovement:
        """
        Compare a student's performance on `topic` across all quizzes that
        included it, in chronological order, and report the point change
        from the first to the most recent attempt.
        """
        records = self.history(student_id)
        history_pct = [
            r.topic_performance[topic].percentage
            for r in records
            if topic in r.topic_performance
        ]

        if not history_pct:
            return TopicImprovement(
                topic=topic,
                history=[],
                change_points=0.0,
                summary=f"No quiz history found for topic '{topic}'.",
            )

        change = round(history_pct[-1] - history_pct[0], 2)

        if len(history_pct) == 1:
            summary = f"Only one attempt so far in '{topic}' at {history_pct[0]}%."
        elif change > 0:
            summary = (
                f"Your performance in {topic} improved by {abs(change)} percentage "
                f"points from your first attempt ({history_pct[0]}%) to your most "
                f"recent attempt ({history_pct[-1]}%)."
            )
        elif change < 0:
            summary = (
                f"Your performance in {topic} dropped by {abs(change)} percentage "
                f"points from your first attempt ({history_pct[0]}%) to your most "
                f"recent attempt ({history_pct[-1]}%)."
            )
        else:
            summary = f"Your performance in {topic} has stayed steady at {history_pct[-1]}%."

        return TopicImprovement(topic=topic, history=history_pct, change_points=change, summary=summary)

    def recommend_next_quiz(
        self,
        student_id: str,
        default_question_count: int = 10,
    ) -> RecommendedNextQuiz:
        """
        Deterministically pick the weakest topic (lowest aggregate percentage,
        using only topics with at least one attempt) and recommend a quiz
        configuration to target it. The AI may explain this further, but the
        selection itself is pure Python.
        """
        records = self.history(student_id)

        if not records:
            return RecommendedNextQuiz(
                recommended_topic="General Review",
                recommended_difficulty=Difficulty.EASY,
                recommended_question_count=default_question_count,
                reason="No quiz history yet -- start with a baseline quiz.",
            )

        topic_totals: Dict[str, Dict[str, int]] = defaultdict(lambda: {"total": 0, "correct": 0})
        for record in records:
            for topic, tp in record.topic_performance.items():
                topic_totals[topic]["total"] += tp.total
                topic_totals[topic]["correct"] += tp.correct

        weakest_topic = None
        weakest_pct = 101.0
        for topic, counts in topic_totals.items():
            pct = (counts["correct"] / counts["total"]) * 100 if counts["total"] else 0
            if pct < weakest_pct:
                weakest_pct = pct
                weakest_topic = topic

        if weakest_topic is None:
            return RecommendedNextQuiz(
                recommended_topic="General Review",
                recommended_difficulty=Difficulty.EASY,
                recommended_question_count=default_question_count,
                reason="Not enough topic data yet -- start with a baseline quiz.",
            )

        difficulty = Difficulty.EASY if weakest_pct < 40 else Difficulty.MEDIUM

        return RecommendedNextQuiz(
            recommended_topic=weakest_topic,
            recommended_difficulty=difficulty,
            recommended_question_count=default_question_count,
            reason=(
                f"Your recent performance in {weakest_topic} is "
                f"{round(weakest_pct, 2)}%, which is below the strong-area threshold."
            ),
        )
