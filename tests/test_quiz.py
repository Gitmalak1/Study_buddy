import json

import pytest

from study_buddy.models import Question
from study_buddy.quiz import extract_json, generate_quiz, grade_short_answer, parse_questions

GOOD = {
    "questions": [
        {"type": "mcq", "topic": "Cellule", "question": "Où a lieu la photosynthèse ?",
         "choices": ["Noyau", "Chloroplaste", "Mitochondrie", "Ribosome"], "answer_index": 1,
         "hint": "Organite vert", "explanation": "Les chloroplastes contiennent la chlorophylle."},
        {"type": "short", "topic": "Énergie", "question": "Quel gaz est rejeté ?", "answer": "Le dioxygène"},
        {"type": "mcq", "question": "Invalide", "choices": ["a"], "answer_index": 5},  # ignorée
    ]
}


class FakeLLM:
    def __init__(self, *responses):
        self.responses = list(responses)

    def chat(self, *args, **kwargs):
        return self.responses.pop(0)


def test_extract_json_with_fence():
    assert extract_json('Voici :\n```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_fails_without_json():
    with pytest.raises(ValueError):
        extract_json("pas de json")


def test_parse_questions_filters_invalid():
    qs = parse_questions(json.dumps(GOOD))
    assert len(qs) == 2
    assert qs[0].answer == "Chloroplaste" and qs[0].answer_index == 1
    assert qs[1].type == "short"


def test_generate_quiz_retries_on_bad_json():
    llm = FakeLLM("n'importe quoi", json.dumps(GOOD))
    assert len(generate_quiz(llm, "cours", n=5)) == 2


def test_generate_quiz_raises_after_two_failures():
    with pytest.raises(ValueError):
        generate_quiz(FakeLLM("x", "y"), "cours")


def test_grade_short_answer_ok_and_fallback():
    q = Question("short", "Q ?", "réponse")
    verdict, fb = grade_short_answer(FakeLLM('{"verdict": "correct", "feedback": "Bravo"}'), q, "réponse")
    assert (verdict, fb) == ("correct", "Bravo")
    verdict, _ = grade_short_answer(FakeLLM("cassé"), q, "x")
    assert verdict == "partial"
