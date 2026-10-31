
"""SQLite storage: notes, topics, quiz attempts, flashcards."""
import os
import random
import sqlite3
from datetime import date, datetime, timedelta
 
import pandas as pd
 
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "study.db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
 
 
def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c
 
 
def init():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS notes(id INTEGER PRIMARY KEY, student TEXT, title TEXT, text TEXT);
        CREATE TABLE IF NOT EXISTS topics(id INTEGER PRIMARY KEY, student TEXT, name TEXT);
        CREATE TABLE IF NOT EXISTS attempts(
            id INTEGER PRIMARY KEY, student TEXT, topic TEXT, question TEXT, chosen TEXT,
            correct_answer TEXT, is_correct INTEGER, misconception TEXT, difficulty TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS cards(
            id INTEGER PRIMARY KEY, student TEXT, topic TEXT, front TEXT, back TEXT,
            ease REAL DEFAULT 2.5, interval INTEGER DEFAULT 0, reps INTEGER DEFAULT 0,
            due TEXT, updated TEXT);
        """)
 
 
# ---------- notes & topics ----------
def add_note(student, title, text):
    with conn() as c:
        c.execute("INSERT INTO notes(student,title,text) VALUES(?,?,?)", (student, title, text))
 
 
def get_notes(student):
    with conn() as c:
        return [(r["title"], r["text"]) for r in c.execute("SELECT title,text FROM notes WHERE student=? ORDER BY id", (student,))]
 
 
def clear_notes(student):
    with conn() as c:
        for t in ("notes", "topics"):
            c.execute(f"DELETE FROM {t} WHERE student=?", (student,))
 
 
def save_topics(student, topics):
    with conn() as c:
        c.execute("DELETE FROM topics WHERE student=?", (student,))
        c.executemany("INSERT INTO topics(student,name) VALUES(?,?)", [(student, t) for t in topics])
 
 
def get_topics(student):
    with conn() as c:
        return [r["name"] for r in c.execute("SELECT name FROM topics WHERE student=? ORDER BY id", (student,))]
 
 
# ---------- attempts & mastery ----------
def log_attempt(student, topic, question, chosen, correct_answer, is_correct, misconception, difficulty, ts=None):
    with conn() as c:
        c.execute(
            "INSERT INTO attempts(student,topic,question,chosen,correct_answer,is_correct,misconception,difficulty,ts) VALUES(?,?,?,?,?,?,?,?,?)",
            (student, topic, question, chosen, correct_answer, int(is_correct), misconception or "", difficulty,
             ts or datetime.now().isoformat(timespec="seconds")),
        )
 
 
def attempts_df(student=None):
    with conn() as c:
        if student:
            df = pd.read_sql_query("SELECT * FROM attempts WHERE student=?", c, params=(student,))
        else:
            df = pd.read_sql_query("SELECT * FROM attempts", c)
    if not df.empty:
        df["date"] = pd.to_datetime(df["ts"]).dt.strftime("%d %b")
    return df
 
 
def topic_mastery(student):
    """Recency-weighted accuracy per topic (0..1) over the last 20 attempts."""
    df = attempts_df(student)
    out = {}
    for topic, g in df.groupby("topic"):
        g = g.sort_values("id").tail(20)
        w = list(range(1, len(g) + 1))
        out[topic] = sum(wi * ci for wi, ci in zip(w, g["is_correct"])) / sum(w)
    return out
 
 
# ---------- flashcards ----------
def add_cards(student, topic, cards):
    today = date.today().isoformat()
    now = datetime.now().isoformat(timespec="seconds")
    with conn() as c:
        c.executemany(
            "INSERT INTO cards(student,topic,front,back,due,updated) VALUES(?,?,?,?,?,?)",
            [(student, topic, k["front"], k["back"], today, now) for k in cards],
        )
 
 
def due_cards(student):
    with conn() as c:
        return c.execute(
            "SELECT * FROM cards WHERE student=? AND due<=? ORDER BY due, updated, id",
            (student, date.today().isoformat()),
        ).fetchall()
 
 
def card_count(student):
    with conn() as c:
        return c.execute("SELECT COUNT(*) FROM cards WHERE student=?", (student,)).fetchone()[0]
 
 
def review_card(card_id, quality):
    import srs
    with conn() as c:
        r = c.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        ease, interval, reps = srs.update(r["ease"], r["interval"], r["reps"], quality)
        due = (date.today() + timedelta(days=interval)).isoformat()
        c.execute("UPDATE cards SET ease=?,interval=?,reps=?,due=?,updated=? WHERE id=?",
                  (ease, interval, reps, due, datetime.now().isoformat(timespec="seconds"), card_id))
 
 
# ---------- demo data for the teacher dashboard ----------
def seed_demo():
    random.seed(7)
    mis = {
        "Photosynthesis": ["Thinks plants get their mass from soil, not CO2", "Believes photosynthesis happens only in leaves' roots"],
        "Cellular Respiration": ["Thinks plants don't respire", "Confuses respiration with breathing"],
        "Enzymes": ["Believes enzymes are used up in reactions", "Thinks high heat always speeds enzymes up"],
        "Cell Membrane": ["Thinks membrane lets everything pass freely", "Confuses osmosis with diffusion of solutes"],
    }
    weak = {"Photosynthesis": 0.45, "Cellular Respiration": 0.6, "Enzymes": 0.3, "Cell Membrane": 0.75}
    for s in ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Sana"]:
        for topic, p in weak.items():
            for i in range(5):
                ok = random.random() < p
                ts = (datetime.now() - timedelta(days=random.randint(0, 6))).isoformat(timespec="seconds")
                log_attempt(s, topic, f"Demo question {i+1} on {topic}", "demo", "demo", ok,
                            "" if ok else random.choice(mis[topic]), "medium", ts)