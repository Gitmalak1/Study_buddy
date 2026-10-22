"""Suivi des erreurs et hésitations pour la révision ciblée."""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import Question

HESITATION_SECONDS = 45  # au-delà, on considère que l'élève a hésité
MASTERY_STREAK = 2  # bonnes réponses nettes consécutives pour considérer la notion acquise


@dataclass
class QuestionStats:
    question: Question
    attempts: int = 0
    errors: int = 0
    hesitations: int = 0
    streak: int = 0
    last_verdict: str = ""

    @property
    def needs_review(self) -> bool:
        return (self.errors + self.hesitations) > 0 and self.streak < MASTERY_STREAK

    @property
    def priority(self) -> int:
        return 2 * self.errors + self.hesitations - self.streak


@dataclass
class TopicStats:
    attempts: int = 0
    errors: int = 0
    hesitations: int = 0

    @property
    def difficulty_rate(self) -> float:
        return (self.errors + 0.5 * self.hesitations) / self.attempts if self.attempts else 0.0


@dataclass
class WeakPointTracker:
    questions: dict[str, QuestionStats] = field(default_factory=dict)
    topics: dict[str, TopicStats] = field(default_factory=dict)

    def record(self, question: Question, verdict: str, elapsed: float = 0.0, hint_used: bool = False) -> None:
        """Enregistre une réponse. verdict ∈ {correct, partial, incorrect}."""
        stats = self.questions.setdefault(question.id, QuestionStats(question))
        topic = self.topics.setdefault(question.topic, TopicStats())
        stats.attempts += 1
        topic.attempts += 1
        stats.last_verdict = verdict

        hesitated = hint_used or elapsed > HESITATION_SECONDS
        if verdict == "incorrect":
            stats.errors += 1
            topic.errors += 1
            stats.streak = 0
        elif verdict == "partial" or hesitated:
            stats.hesitations += 1
            topic.hesitations += 1
            stats.streak = 0
        else:
            stats.streak += 1

    def review_queue(self, limit: int | None = None) -> list[Question]:
        """Questions à reposer, les plus problématiques en premier."""
        pending = sorted(
            (s for s in self.questions.values() if s.needs_review),
            key=lambda s: s.priority,
            reverse=True,
        )
        queue = [s.question for s in pending]
        return queue[:limit] if limit else queue

    def weak_topics(self, threshold: float = 0.4) -> list[str]:
        ranked = sorted(self.topics.items(), key=lambda kv: kv[1].difficulty_rate, reverse=True)
        return [name for name, t in ranked if t.difficulty_rate >= threshold]

    def summary(self) -> dict:
        attempts = sum(t.attempts for t in self.topics.values())
        errors = sum(t.errors for t in self.topics.values())
        hes = sum(t.hesitations for t in self.topics.values())
        return {
            "attempts": attempts,
            "errors": errors,
            "hesitations": hes,
            "clean_success_rate": round((attempts - errors - hes) / attempts, 2) if attempts else 0.0,
            "to_review": len(self.review_queue()),
        }

    def to_dict(self) -> dict:
        return {
            "summary": self.summary(),
            "topics": {
                n: {"attempts": t.attempts, "errors": t.errors, "hesitations": t.hesitations}
                for n, t in self.topics.items()
            },
            "questions": [
                {
                    "question": s.question.question,
                    "topic": s.question.topic,
                    "attempts": s.attempts,
                    "errors": s.errors,
                    "hesitations": s.hesitations,
                    "to_review": s.needs_review,
                }
                for s in self.questions.values()
            ],
        }
