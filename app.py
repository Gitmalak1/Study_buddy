"""Study Buddy — assistant de révision interactif et adaptatif (Streamlit)."""
from __future__ import annotations

import json
import os
import time

import streamlit as st

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv est optionnel
    pass

from study_buddy.explain import STYLES, explain
from study_buddy.llm import PROVIDERS, LLMClient, LLMError
from study_buddy.quiz import MAX_COURSE_CHARS, generate_quiz, grade_short_answer
from study_buddy.tracker import WeakPointTracker

st.set_page_config(page_title="Study Buddy", page_icon="🎓", layout="wide")

VERDICT_UI = {
    "correct": ("success", "✅ Correct !"),
    "partial": ("warning", "🟡 Partiellement juste"),
    "incorrect": ("error", "❌ Incorrect"),
}


# ----------------------------------------------------------------- état
def init_state() -> None:
    defaults = {
        "course": "",
        "quiz": [],
        "current": 0,
        "feedback": None,
        "started_at": None,
        "hint_used": False,
        "tracker": WeakPointTracker(),
        "asked": [],
        "explanation": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def reset_question_state() -> None:
    st.session_state.feedback = None
    st.session_state.started_at = None
    st.session_state.hint_used = False


def start_quiz(questions) -> None:
    st.session_state.quiz = questions
    st.session_state.current = 0
    st.session_state.asked += [q.question for q in questions]
    reset_question_state()


# -------------------------------------------------------------- sidebar
def sidebar() -> tuple[LLMClient | None, str]:
    st.sidebar.title("⚙️ Configuration")
    provider = st.sidebar.selectbox(
        "Fournisseur LLM", list(PROVIDERS), format_func=lambda p: PROVIDERS[p]["label"]
    )
    cfg = PROVIDERS[provider]
    model = st.sidebar.text_input("Modèle", value=os.getenv("MODEL", cfg["default_model"]))
    api_key, base_url = None, None
    if provider == "openai":
        api_key = st.sidebar.text_input(
            "Clé API OpenAI", value=os.getenv("OPENAI_API_KEY", ""), type="password"
        )
    else:
        base_url = st.sidebar.text_input(
            "URL Ollama", value=os.getenv("OLLAMA_BASE_URL", cfg["base_url"])
        )
        st.sidebar.caption("Lance Ollama puis `ollama pull " + model + "`.")
    language = st.sidebar.selectbox("Langue des réponses", ["français", "English"])

    st.sidebar.divider()
    s = st.session_state.tracker.summary()
    st.sidebar.metric("Réponses données", s["attempts"])
    st.sidebar.metric("À réviser", s["to_review"])

    try:
        return LLMClient(provider, model, api_key, base_url), language
    except LLMError as exc:
        st.sidebar.warning(str(exc))
        return None, language


# ----------------------------------------------------------------- cours
def read_upload(file) -> str:
    if file.name.lower().endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(file)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    return file.read().decode("utf-8", errors="ignore")


def tab_course() -> None:
    st.subheader("1. Importe ton cours")
    upload = st.file_uploader("Fichier .txt, .md ou .pdf", type=["txt", "md", "pdf"])
    if upload is not None and st.button("Charger le fichier"):
        st.session_state.course = read_upload(upload)
        st.rerun()
    st.session_state.course = st.text_area(
        "…ou colle ton résumé / sujet ici", value=st.session_state.course, height=350
    )
    n = len(st.session_state.course)
    st.caption(f"{n} caractères")
    if n > MAX_COURSE_CHARS:
        st.warning(f"Seuls les {MAX_COURSE_CHARS} premiers caractères seront utilisés.")


# ------------------------------------------------------------------ quiz
def tab_quiz(llm: LLMClient | None, language: str) -> None:
    st.subheader("2. Teste-toi")
    course = st.session_state.course.strip()
    tracker: WeakPointTracker = st.session_state.tracker

    with st.expander("Paramètres du quiz", expanded=not st.session_state.quiz):
        c1, c2, c3 = st.columns(3)
        n = c1.slider("Nombre de questions", 3, 15, 5)
        qtype = c2.selectbox(
            "Type", ["mixed", "mcq", "short"],
            format_func={"mixed": "Mixte", "mcq": "QCM", "short": "Réponse courte"}.get,
        )
        difficulty = c3.selectbox("Difficulté", ["facile", "moyen", "difficile"], index=1)

        b1, b2, b3 = st.columns(3)
        if b1.button("🎲 Nouveau quiz", disabled=not (course and llm), use_container_width=True):
            with st.spinner("Génération du quiz…"):
                try:
                    start_quiz(generate_quiz(llm, course, n, qtype, difficulty, language,
                                             avoid=st.session_state.asked))
                except (ValueError, LLMError) as exc:
                    st.error(str(exc))
        queue = tracker.review_queue(limit=n)
        if b2.button(f"🔁 Revoir mes points faibles ({len(queue)})", disabled=not queue,
                     use_container_width=True):
            start_quiz(queue)
            st.rerun()
        weak = tracker.weak_topics()
        if b3.button("🧠 Nouvelles questions sur mes faiblesses", disabled=not (weak and llm),
                     use_container_width=True):
            with st.spinner("Génération ciblée…"):
                try:
                    start_quiz(generate_quiz(llm, course, n, qtype, difficulty, language,
                                             focus_topics=weak, avoid=st.session_state.asked))
                except (ValueError, LLMError) as exc:
                    st.error(str(exc))

    if not course:
        st.info("Commence par importer un cours dans l'onglet « Cours ».")
        return
    if st.session_state.quiz:
        render_question(llm, language)


def render_question(llm: LLMClient | None, language: str) -> None:
    quiz, i = st.session_state.quiz, st.session_state.current
    if i >= len(quiz):
        st.success("🎉 Quiz terminé ! Consulte l'onglet « Bilan » pour voir tes points faibles.")
        return

    q = quiz[i]
    st.progress(i / len(quiz), text=f"Question {i + 1} / {len(quiz)} · {q.topic}")
    st.markdown(f"### {q.question}")
    fb = st.session_state.feedback

    if fb is None:
        if st.session_state.started_at is None:
            st.session_state.started_at = time.time()
        if q.hint:
            if st.button("💡 Indice"):
                st.session_state.hint_used = True
            if st.session_state.hint_used:
                st.info(q.hint)

        with st.form(f"form_{q.id}_{i}"):
            if q.type == "mcq":
                answer = st.radio("Ta réponse", q.choices, index=None)
            else:
                answer = st.text_area("Ta réponse")
            submitted = st.form_submit_button("Valider")

        if submitted:
            if not answer:
                st.warning("Réponds avant de valider.")
                return
            elapsed = time.time() - st.session_state.started_at
            if q.type == "mcq":
                verdict = "correct" if q.choices.index(answer) == q.answer_index else "incorrect"
                text = q.explanation
            else:
                with st.spinner("Correction…"):
                    try:
                        verdict, text = grade_short_answer(llm, q, answer, language)
                    except LLMError as exc:
                        st.error(str(exc))
                        return
            st.session_state.tracker.record(q, verdict, elapsed, st.session_state.hint_used)
            st.session_state.feedback = {"verdict": verdict, "text": text}
            st.rerun()
    else:
        kind, label = VERDICT_UI[fb["verdict"]]
        getattr(st, kind)(label)
        st.markdown(f"**Réponse attendue :** {q.answer}")
        if fb["text"]:
            st.write(fb["text"])
        if st.button("Question suivante ➡️"):
            st.session_state.current += 1
            reset_question_state()
            st.rerun()


# ------------------------------------------------------------ explication
def tab_explain(llm: LLMClient | None, language: str) -> None:
    st.subheader("3. Fais-toi expliquer une notion")
    concept = st.text_input("Notion à expliquer", placeholder="ex. : la photosynthèse, la récursivité…")
    c1, c2 = st.columns([1, 2])
    style = c1.selectbox("Style", list(STYLES) + ["Personnalisé"])
    custom = c2.text_input("Ton propre style", disabled=style != "Personnalisé",
                           placeholder="ex. : avec une métaphore musicale")
    instruction = custom if style == "Personnalisé" else STYLES[style]

    ready = bool(concept.strip() and st.session_state.course.strip() and llm and instruction.strip())
    if st.button("✨ Expliquer", disabled=not ready):
        with st.spinner("Réflexion…"):
            try:
                st.session_state.explanation = explain(
                    llm, st.session_state.course, concept, instruction, language
                )
            except LLMError as exc:
                st.error(str(exc))
    if st.session_state.explanation:
        st.markdown(st.session_state.explanation)


# ------------------------------------------------------------------ bilan
def tab_report() -> None:
    st.subheader("4. Ton bilan de session")
    tracker: WeakPointTracker = st.session_state.tracker
    s = tracker.summary()
    if not s["attempts"]:
        st.info("Réponds à quelques questions pour voir ton bilan.")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Réponses", s["attempts"])
    c2.metric("Erreurs", s["errors"])
    c3.metric("Hésitations", s["hesitations"])
    c4.metric("Réussite nette", f"{int(s['clean_success_rate'] * 100)} %")

    st.markdown("**Par notion**")
    st.dataframe(
        [
            {"Notion": n, "Réponses": t.attempts, "Erreurs": t.errors,
             "Hésitations": t.hesitations, "Difficulté": f"{int(t.difficulty_rate * 100)} %"}
            for n, t in sorted(tracker.topics.items(), key=lambda kv: -kv[1].difficulty_rate)
        ],
        use_container_width=True, hide_index=True,
    )
    queue = tracker.review_queue()
    if queue:
        st.markdown("**À revoir en priorité**")
        for q in queue:
            st.write(f"- {q.question}  _({q.topic})_")
    else:
        st.success("Rien à revoir pour l'instant 👏")

    st.download_button("⬇️ Exporter le bilan (JSON)",
                       json.dumps(tracker.to_dict(), ensure_ascii=False, indent=2),
                       file_name="study_buddy_bilan.json", mime="application/json")


# ------------------------------------------------------------------- main
def main() -> None:
    init_state()
    st.title("🎓 Study Buddy")
    st.caption("Ton tuteur IA : quiz basés sur ton cours, explications sur mesure, révision des points faibles.")
    llm, language = sidebar()
    t1, t2, t3, t4 = st.tabs(["📚 Cours", "📝 Quiz", "💬 Explications", "📊 Bilan"])
    with t1:
        tab_course()
    with t2:
        tab_quiz(llm, language)
    with t3:
        tab_explain(llm, language)
    with t4:
        tab_report()


main()
