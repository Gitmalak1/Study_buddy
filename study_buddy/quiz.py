"""Génération et correction de quiz à partir d'un cours."""
from __future__ import annotations

import json
import re

from .models import Question

MAX_COURSE_CHARS = 15000

SYSTEM_TEMPLATE = (
    "Tu es un tuteur pédagogue et rigoureux. "
    "Tu t'appuies UNIQUEMENT sur le cours fourni par l'élève : n'invente jamais "
    "d'information qui n'y figure pas. Réponds en {language}."
)


def extract_json(text: str):
    """Extrait le premier objet/tableau JSON d'une réponse de LLM (tolère les ```json)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        raise ValueError("Aucun JSON trouvé dans la réponse du modèle.")
    start = min(starts)
    end = max(text.rfind("}"), text.rfind("]"))
    if end <= start:
        raise ValueError("JSON incomplet dans la réponse du modèle.")
    return json.loads(text[start : end + 1])


def parse_questions(raw: str) -> list[Question]:
    """Transforme la réponse du LLM en liste de Question valides (les invalides sont ignorées)."""
    data = extract_json(raw)
    items = data.get("questions", []) if isinstance(data, dict) else data
    questions: list[Question] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        text = str(item.get("question", "")).strip()
        if not text:
            continue
        qtype = "mcq" if str(item.get("type", "")).lower() in ("mcq", "qcm") else "short"
        topic = str(item.get("topic", "Général")).strip() or "Général"
        explanation = str(item.get("explanation", "")).strip()
        hint = str(item.get("hint", "")).strip()

        if qtype == "mcq":
            choices = [str(c).strip() for c in item.get("choices", []) if str(c).strip()]
            idx = item.get("answer_index")
            if len(choices) < 2 or not isinstance(idx, int) or not 0 <= idx < len(choices):
                continue
            questions.append(
                Question("mcq", text, choices[idx], explanation, hint, topic, choices, idx)
            )
        else:
            answer = str(item.get("answer", "")).strip()
            if not answer:
                continue
            questions.append(Question("short", text, answer, explanation, hint, topic))
    return questions


def generate_quiz(
    llm,
    course: str,
    n: int = 5,
    qtype: str = "mixed",  # "mcq", "short" ou "mixed"
    difficulty: str = "moyen",
    language: str = "français",
    focus_topics: list[str] | None = None,
    avoid: list[str] | None = None,
) -> list[Question]:
    """Génère `n` questions basées uniquement sur `course`."""
    type_rule = {
        "mcq": "Toutes les questions sont des QCM (type \"mcq\") avec 4 choix.",
        "short": "Toutes les questions sont à réponse courte (type \"short\").",
        "mixed": "Mélange des QCM (type \"mcq\", 4 choix) et des questions à réponse courte (type \"short\").",
    }[qtype]
    focus = (
        f"Concentre-toi sur ces notions que l'élève maîtrise mal : {', '.join(focus_topics)}.\n"
        if focus_topics
        else ""
    )
    avoid_txt = (
        "Ne repose PAS ces questions déjà posées :\n- " + "\n- ".join(avoid[:20]) + "\n"
        if avoid
        else ""
    )
    user = f"""COURS :
\"\"\"
{course[:MAX_COURSE_CHARS]}
\"\"\"

Génère {n} questions de difficulté « {difficulty} ». {type_rule}
{focus}{avoid_txt}
Réponds UNIQUEMENT par un objet JSON de la forme :
{{"questions": [
  {{"type": "mcq", "topic": "notion courte", "question": "...", "choices": ["A", "B", "C", "D"],
    "answer_index": 0, "hint": "indice sans donner la réponse", "explanation": "pourquoi c'est la bonne réponse"}},
  {{"type": "short", "topic": "notion courte", "question": "...", "answer": "réponse attendue concise",
    "hint": "...", "explanation": "..."}}
]}}
Les choix incorrects doivent être plausibles. Place la bonne réponse à des positions variées."""
    system = SYSTEM_TEMPLATE.format(language=language)

    last_error: Exception | None = None
    for _ in range(2):  # un essai + un nouvel essai si le JSON est invalide
        raw = llm.chat(system, user, json_mode=True, temperature=0.5)
        try:
            questions = parse_questions(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            continue
        if questions:
            return questions[:n]
    raise ValueError(f"Impossible de générer un quiz exploitable ({last_error}).")


def grade_short_answer(llm, question: Question, user_answer: str, language: str = "français"):
    """Corrige une réponse courte. Retourne (verdict, feedback) avec verdict ∈ correct/partial/incorrect."""
    user = f"""Question : {question.question}
Réponse attendue (d'après le cours) : {question.answer}
Réponse de l'élève : {user_answer}

Évalue la réponse de l'élève en acceptant les reformulations équivalentes.
Réponds UNIQUEMENT en JSON : {{"verdict": "correct" | "partial" | "incorrect", "feedback": "1 à 3 phrases bienveillantes expliquant ce qui est juste ou manquant"}}"""
    try:
        raw = llm.chat(SYSTEM_TEMPLATE.format(language=language), user, json_mode=True, temperature=0.0)
        data = extract_json(raw)
        verdict = str(data.get("verdict", "")).lower()
        if verdict not in ("correct", "partial", "incorrect"):
            raise ValueError("verdict invalide")
        return verdict, str(data.get("feedback", "")).strip()
    except (ValueError, json.JSONDecodeError):
        return "partial", f"Correction automatique indisponible. Réponse attendue : {question.answer}"
