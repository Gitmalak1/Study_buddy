"""Explications adaptatives d'une notion."""
from __future__ import annotations

from .quiz import MAX_COURSE_CHARS, SYSTEM_TEMPLATE

STYLES = {
    "Comme si j'avais 10 ans": "Explique avec des mots très simples, des phrases courtes et des exemples du quotidien, comme à un enfant de 10 ans.",
    "Analogie sportive": "Explique à l'aide d'une analogie filée avec un sport (football, tennis, course à pied...).",
    "Analogie cuisine": "Explique à l'aide d'une analogie avec la cuisine (recettes, ingrédients, étapes).",
    "Analogie jeux vidéo": "Explique à l'aide d'une analogie avec les jeux vidéo (niveaux, personnages, mécaniques).",
    "Étape par étape": "Décompose en étapes numérotées, chacune courte et claire, avec un mini-exemple.",
    "Résumé en 3 points": "Résume l'essentiel en exactement 3 points, puis une phrase à retenir.",
    "Niveau expert": "Explique de façon précise et technique, avec le vocabulaire exact et les nuances.",
}


def explain(llm, course: str, concept: str, style_instruction: str, language: str = "français") -> str:
    user = f"""COURS :
\"\"\"
{course[:MAX_COURSE_CHARS]}
\"\"\"

Notion à expliquer : « {concept} »

Consigne de style : {style_instruction}

Appuie-toi sur le cours. Si la notion n'y figure pas, dis-le clairement en une phrase, puis donne une
brève explication générale en la signalant comme « hors cours ». Termine par une question de
vérification pour tester la compréhension."""
    return llm.chat(SYSTEM_TEMPLATE.format(language=language), user, temperature=0.6)
