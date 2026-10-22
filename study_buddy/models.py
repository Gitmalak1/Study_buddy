from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass
class Question:
    """Une question de quiz générée à partir du cours."""

    type: str  # "mcq" ou "short"
    question: str
    answer: str  # réponse attendue (texte)
    explanation: str = ""
    hint: str = ""
    topic: str = "Général"
    choices: list[str] = field(default_factory=list)
    answer_index: int = -1  # index de la bonne réponse pour les QCM

    @property
    def id(self) -> str:
        """Identifiant stable, basé sur l'énoncé."""
        return hashlib.md5(self.question.strip().lower().encode()).hexdigest()[:10]
