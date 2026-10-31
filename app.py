import os
import time
 
import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
 
load_dotenv()
import engine as ai
import rag
import store
 
st.set_page_config(page_title="StudyPath", layout="wide")
store.setup()
 
st.markdown("""
<style>
#MainMenu, footer {visibility: hidden;}
.block-container {padding-top: 2rem; max-width: 1100px;}
h1, h2, h3 {letter-spacing: -0.01em;}
.stTabs [data-baseweb="tab"] {font-size: 0.95rem; padding: 0.6rem 1.1rem;}
div[data-testid="stMetric"] {background: #f0ede6; padding: 0.8rem 1rem; border-radius: 6px;}
</style>
""", unsafe_allow_html=True)
 
SAMPLE = """Photosynthesis
Photosynthesis is how plants, algae and some bacteria turn light energy into chemical energy stored in glucose. It happens in chloroplasts. The overall equation is 6CO2 + 6H2O + light -> C6H12O6 + 6O2. The carbon in glucose comes from carbon dioxide in the air, not from the soil.
 
The light-dependent reactions happen in the thylakoid membranes. Chlorophyll absorbs light, water is split (photolysis) and oxygen is released, and ATP and NADPH are made. The Calvin cycle happens in the stroma and uses that ATP and NADPH to fix CO2 into glucose.
 
Cellular Respiration
Cellular respiration releases energy from glucose to make ATP. Every living cell does it, including plant cells. The overall equation is C6H12O6 + 6O2 -> 6CO2 + 6H2O + ATP. Glycolysis happens in the cytoplasm, the Krebs cycle in the mitochondrial matrix, and the electron transport chain on the inner mitochondrial membrane, which makes most of the ATP. Respiration is a chemical process inside cells and is not the same thing as breathing.
 
Enzymes
Enzymes are biological catalysts, usually proteins, that speed up reactions by lowering the activation energy. They are not used up. Each enzyme has an active site that fits its substrate (lock and key, induced fit). The rate goes up with temperature until the optimum, then the enzyme denatures and loses its shape. pH matters too: pepsin works best in acid, amylase near neutral.
 
Cell Membrane
The cell membrane is a fluid mosaic of phospholipids and proteins and is selectively permeable. Diffusion is the movement of particles from high to low concentration. Osmosis is the movement of water across a selectively permeable membrane from low solute concentration to high solute concentration. Active transport moves substances against their gradient and needs ATP.
"""
 
CELL_COLORS = ["#b5483a", "#e0b84e", "#3f7d5c"]
 
 
def read_upload(f):
    if f.name.lower().endswith(".pdf"):
        from pypdf import PdfReader
        return "\n\n".join((p.extract_text() or "") for p in PdfReader(f).pages)
    return f.read().decode("utf-8", errors="ignore")
 
 
def level_for(m):
    if m < 0.4:
        return "easy"
    return "medium" if m < 0.75 else "hard"
 
 
def get_index(student):
    notes = store.get_notes(student)
    sig = (student, tuple(body for _, body in notes))
    if st.session_state.get("index_sig") != sig:
        chunks = []
        for _, body in notes:
            chunks += rag.split_text(body)
        st.session_state.index = rag.NoteIndex(chunks)
        st.session_state.index_sig = sig
    return st.session_state.index
 
 
def heatmap(df, x, y, x_title):
    return alt.Chart(df).mark_rect(stroke="white", strokeWidth=2).encode(
        x=alt.X(f"{x}:O", title=x_title, sort=None),
        y=alt.Y(f"{y}:N", title=None),
        color=alt.Color("accuracy:Q", title="Accuracy",
                        scale=alt.Scale(domain=[0, 0.5, 1], range=CELL_COLORS)),
        tooltip=[y, x, alt.Tooltip("accuracy:Q", format=".0%"), "attempts:Q"],
    ).properties(height=max(140, 42 * df[y].nunique()))
 
 
# ---------------- sidebar ----------------
with st.sidebar:
    st.title("StudyPath")
    st.caption("Learn from your own notes")
    role = st.radio("Signed in as", ["Student", "Teacher"], horizontal=True)
    student = st.text_input("Your name", key="name").strip() if role == "Student" else ""
    st.caption("Engine: " + ai.mode())
    if ai.last_error:
        st.warning(ai.last_error)
 
 
# =============== teacher page ===============
if role == "Teacher":
    st.header("Class overview")
    pin = st.sidebar.text_input("Teacher PIN", type="password")
    if pin != os.getenv("TEACHER_PIN", "1234"):
        st.info("Enter the teacher PIN in the sidebar.")
        st.stop()
 
    if st.sidebar.button("Load sample class data"):
        store.load_demo_class()
        st.rerun()
 
    df = store.get_attempts()
    if df.empty:
        st.info("Nobody has taken a quiz yet. Use 'Load sample class data' in the sidebar to see how this page looks.")
        st.stop()
 
    a, b, c = st.columns(3)
    a.metric("Students", df["student"].nunique())
    b.metric("Questions answered", len(df))
    c.metric("Class accuracy", f"{df['correct'].mean():.0%}")
 
    st.subheader("Accuracy by student and topic")
    g = df.groupby(["student", "topic"]).agg(accuracy=("correct", "mean"), attempts=("correct", "size")).reset_index()
    st.altair_chart(heatmap(g, "student", "topic", "Student"), use_container_width=True)
 
    st.subheader("Topics, weakest first")
    by_topic = df.groupby("topic")["correct"].mean().sort_values().reset_index()
    by_topic.columns = ["topic", "accuracy"]
    st.bar_chart(by_topic.set_index("topic"))
 
    st.subheader("Common misconceptions")
    wrong = df[(df["correct"] == 0) & (df["misconception"] != "")]
    table = (wrong.groupby(["topic", "misconception"])
             .agg(students=("student", "nunique"), times=("id", "size"))
             .reset_index().sort_values(["students", "times"], ascending=False))
    st.dataframe(table, use_container_width=True, hide_index=True)
 
    if st.button("Summarise and suggest fixes", type="primary"):
        with st.spinner("Working on it..."):
            try:
                st.markdown(ai.class_report(by_topic, table))
            except Exception as e:
                st.error(str(e))
    st.stop()
 
 
# =============== student pages ===============
if not student:
    st.info("Enter your name in the sidebar to start.")
    st.stop()
 
index = get_index(student)
topics = store.get_topics(student)
scores = store.mastery(student)
 
tab_notes, tab_quiz, tab_cards, tab_tutor, tab_progress = st.tabs(
    ["Notes", "Quiz", "Flashcards", "Tutor", "Progress"]
)
 
# ---- notes ----
with tab_notes:
    st.subheader("Add your notes")
    files = st.file_uploader("PDF, TXT or MD files", type=["pdf", "txt", "md"], accept_multiple_files=True)
    st.text_area("Or paste text", height=180, key="pasted")
    st.button("Use sample biology notes", on_click=lambda: st.session_state.update(pasted=SAMPLE))
 
    left, right = st.columns(2)
    if left.button("Save and find topics", type="primary"):
        new = [(f.name, read_upload(f)) for f in files]
        if st.session_state.get("pasted", "").strip():
            new.append(("Pasted notes", st.session_state["pasted"]))
        if not new:
            st.warning("Upload a file or paste some text first.")
        else:
            for title, body in new:
                store.add_note(student, title, body)
            everything = "\n\n".join(body for _, body in store.get_notes(student))
            with st.spinner("Reading your notes..."):
                try:
                    store.set_topics(student, ai.find_topics(everything))
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
    if right.button("Delete my notes"):
        store.clear_notes(student)
        st.rerun()
 
    if topics:
        st.subheader("Topics")
        for t in topics:
            m = scores.get(t)
            label = f"{t}  -  {m:.0%}" if m is not None else f"{t}  -  not attempted"
            st.progress(m or 0.0, text=label)
 
# ---- quiz ----
with tab_quiz:
    if not topics:
        st.info("Add some notes first.")
    else:
        auto = "Weakest topic (automatic)"
        pick = st.selectbox("Topic", [auto] + topics)
        n = st.slider("Questions", 3, 8, 5)
 
        if st.button("Start quiz", type="primary"):
            topic = min(topics, key=lambda t: scores.get(t, 0.5)) if pick == auto else pick
            level = level_for(scores.get(topic, 0.5))
            material = "\n\n".join(index.search(topic, 5))
            with st.spinner(f"Writing {level} questions on {topic}..."):
                try:
                    st.session_state.quiz = {
                        "id": int(time.time()), "topic": topic, "level": level,
                        "questions": ai.make_quiz(topic, material, level, n), "results": None,
                    }
                except Exception as e:
                    st.error(str(e))
 
        quiz = st.session_state.get("quiz")
        if quiz:
            st.markdown(f"### {quiz['topic']}")
            st.caption(f"Difficulty: {quiz['level']}")
            with st.form(f"quiz_{quiz['id']}"):
                for i, q in enumerate(quiz["questions"]):
                    st.radio(f"{i + 1}. {q['question']}", q["options"], index=None, key=f"q{quiz['id']}_{i}")
                sent = st.form_submit_button("Submit")
 
            if sent and quiz["results"] is None:
                results, missed = [], []
                for i, q in enumerate(quiz["questions"]):
                    chosen = st.session_state.get(f"q{quiz['id']}_{i}")
                    answer = q["options"][q["answer"]]
                    ok = chosen == answer
                    idea = q["misconceptions"][q["options"].index(chosen)] if chosen and not ok else ""
                    store.log_attempt(student, quiz["topic"], q["question"], chosen or "(skipped)",
                                      answer, ok, idea, quiz["level"])
                    if not ok:
                        missed.append({"front": q["question"], "back": f"{answer}. {q['explanation']}"})
                    results.append((q, chosen, answer, ok))
                if missed:
                    store.add_cards(student, quiz["topic"], missed)
                quiz["results"] = results
                st.rerun()
 
            if quiz["results"]:
                got = sum(r[3] for r in quiz["results"])
                st.success(f"You got {got} out of {len(quiz['results'])}. Questions you missed were added to your flashcards.")
                for i, (q, chosen, answer, ok) in enumerate(quiz["results"], 1):
                    with st.expander(f"{'Correct' if ok else 'Wrong'}: question {i}"):
                        st.write(q["question"])
                        st.write(f"Your answer: {chosen or 'skipped'}")
                        st.write(f"Correct answer: {answer}")
                        st.caption(q["explanation"])
                now = store.mastery(student).get(quiz["topic"], 0.5)
                st.info(f"Mastery in {quiz['topic']} is now {now:.0%}. Next quiz on it will be {level_for(now)}.")
 
# ---- flashcards ----
with tab_cards:
    if not topics:
        st.info("Add some notes first.")
    else:
        with st.expander("Make flashcards from a topic"):
            t = st.selectbox("Topic", topics, key="card_topic")
            if st.button("Make 6 cards"):
                with st.spinner("Writing cards..."):
                    try:
                        store.add_cards(student, t, ai.make_cards(t, "\n\n".join(index.search(t, 5))))
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
 
        due = store.due_cards(student)
        a, b = st.columns(2)
        a.metric("Due now", len(due))
        b.metric("Total cards", store.count_cards(student))
 
        if not due:
            st.success("Nothing due right now.")
        else:
            card = due[0]
            st.caption(card["topic"])
            st.markdown(f"#### {card['front']}")
            if st.session_state.get("flipped") == card["id"]:
                st.info(card["back"])
                cols = st.columns(4)
                for col, (label, q) in zip(cols, [("Again", 1), ("Hard", 3), ("Good", 4), ("Easy", 5)]):
                    if col.button(label, key=f"rate{q}_{card['id']}"):
                        store.review(card["id"], q)
                        st.session_state.flipped = None
                        st.rerun()
            elif st.button("Show answer"):
                st.session_state.flipped = card["id"]
                st.rerun()
 
# ---- tutor ----
with tab_tutor:
    if not topics:
        st.info("Add some notes first.")
    else:
        names = ["Small nudge", "Bigger hint", "Step by step"]
        choice = st.select_slider("How much help?", names)
        level = names.index(choice) + 1
        st.caption("The tutor asks questions to lead you to the answer instead of giving it away.")
        if st.button("Clear chat"):
            st.session_state.chat = []
        st.session_state.setdefault("chat", [])
 
        for m in st.session_state.chat:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
 
        msg = st.chat_input("Ask something, or try answering a question")
        if msg:
            st.session_state.chat.append({"role": "user", "content": msg})
            with st.chat_message("user"):
                st.markdown(msg)
            material = "\n\n".join(index.search(msg, 4))
            with st.chat_message("assistant"):
                with st.spinner("..."):
                    try:
                        reply = ai.tutor_reply(st.session_state.chat[-10:], material, level)
                    except Exception as e:
                        reply = f"Something went wrong: {e}"
                st.markdown(reply)
            st.session_state.chat.append({"role": "assistant", "content": reply})
 
# ---- progress ----
with tab_progress:
    df = store.get_attempts(student)
    if df.empty:
        st.info("Take a quiz and your progress will show up here.")
    else:
        days = df.sort_values("id")["day"].unique().tolist()
        g = df.groupby(["topic", "day"]).agg(accuracy=("correct", "mean"), attempts=("correct", "size")).reset_index()
        g["day"] = pd.Categorical(g["day"], categories=days, ordered=True)
        g = g.sort_values("day")
        g["day"] = g["day"].astype(str)
 
        st.subheader("Accuracy by topic")
        st.altair_chart(heatmap(g, "day", "topic", "Day"), use_container_width=True)
 
        st.subheader("Work on these first")
        for t, m in sorted(store.mastery(student).items(), key=lambda x: x[1])[:3]:
            st.write(f"{t}: {m:.0%}")
 