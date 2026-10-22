# 🎓 Study Buddy

Assistant de révision **interactif et adaptatif** propulsé par un LLM. Importe ton cours, l'IA devient ton tuteur personnel.

## Fonctionnalités

- **Quiz dynamiques** : QCM et/ou questions à réponse courte générés *uniquement* à partir de ton cours (correction automatique, indices).
- **Explications adaptatives** : « comme si j'avais 10 ans », analogie sportive/cuisine/jeux vidéo, étape par étape, niveau expert… ou ton propre style.
- **Suivi des erreurs** : l'application retient les questions ratées *et* celles où tu as hésité (indice utilisé, réponse partielle, plus de 45 s). Elles te sont reposées jusqu'à 2 bonnes réponses nettes d'affilée, et l'IA peut générer de nouvelles questions sur tes notions faibles.
- **Bilan de session** exportable en JSON.

## Installation

```bash
git clone https://github.com/<ton-compte>/study-buddy.git
cd study-buddy
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

```bash
streamlit run app.py
```

### Option A — OpenAI
Copie `.env.example` en `.env` et renseigne `OPENAI_API_KEY` (ou saisis la clé dans la barre latérale).

### Option B — Modèle local avec Ollama (gratuit)
```bash
ollama pull llama3.1
ollama serve
```
Puis choisis « Ollama (local) » dans la barre latérale.

## Architecture

```
app.py                  Interface Streamlit (4 onglets)
study_buddy/
  llm.py                Client unique OpenAI / Ollama (API compatible OpenAI)
  quiz.py               Génération + parsing JSON robuste + correction
  explain.py            Styles d'explication
  tracker.py            Erreurs, hésitations, file de révision
  models.py             Dataclass Question
tests/                  Tests pytest (LLM simulé, aucun appel réseau)
```

## Tests

```bash
pytest -q
```

## Pistes d'amélioration

- Persistance de la progression entre sessions (SQLite).
- Répétition espacée (algorithme SM-2).
- Découpage de gros PDF + recherche sémantique (RAG).
- Export des questions au format Anki.

## Licence

MIT
