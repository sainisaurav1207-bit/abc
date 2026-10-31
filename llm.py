"""All Claude (LLM API) calls live here."""
import json
import os
import random
import re
 
import anthropic
from dotenv import load_dotenv
 
load_dotenv()
MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")
_client = None
 
 
def _c():
    global _client
    if _client is None:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key or key == "PASTE_YOUR_KEY_HERE":
            raise RuntimeError("Set ANTHROPIC_API_KEY in the .env file.")
        _client = anthropic.Anthropic(api_key=key)
    return _client
 
 
def chat(system: str, messages: list, max_tokens: int = 2000) -> str:
    r = _c().messages.create(model=MODEL, max_tokens=max_tokens, system=system, messages=messages)
    return "".join(b.text for b in r.content if b.type == "text")
 
 
def ask(system: str, user: str, max_tokens: int = 2000) -> str:
    return chat(system, [{"role": "user", "content": user}], max_tokens)
 
 
def _parse(text: str):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    m = re.search(r"(\[.*\]|\{.*\})", text, re.S)
    return json.loads(m.group(1) if m else text)
 
 
def ask_json(system: str, user: str, max_tokens: int = 3000):
    last = None
    for _ in range(2):
        try:
            return _parse(ask(system + " Reply with valid JSON only, no commentary.", user, max_tokens))
        except Exception as e:  # retry once on bad JSON
            last = e
    raise last
 
 
def extract_topics(text: str):
    data = ask_json(
        "You are a curriculum analyst.",
        "Read these study notes and list 5-10 distinct, short topic names (2-4 words each) "
        'that a student should master. Format: ["Topic 1", "Topic 2"]\n\nNOTES:\n' + text[:14000],
        500,
    )
    return [str(t).strip() for t in data if str(t).strip()][:12]
 
 
def make_quiz(topic: str, context: str, difficulty: str, n: int):
    data = ask_json(
        "You are an expert teacher writing multiple-choice questions strictly from the given material.",
        f"""Topic: {topic}
Difficulty: {difficulty} (easy = recall, medium = understanding, hard = application/analysis)
Write {n} MCQs. Each has exactly 4 options and exactly one correct answer. Do not prefix options with letters.
For each WRONG option, put in "misconceptions" the specific student misconception that choosing it reveals
(a short phrase). Use "" for the correct option.
Format: [{{"question": "...", "options": ["..","..","..",".."], "answer_index": 0, "explanation": "...", "misconceptions": ["","..","..",".."]}}]
 
STUDY MATERIAL:
{context}""",
        3500,
    )
    out = []
    for q in data:
        try:
            opts = list(q["options"])
            mis = list(q.get("misconceptions", [""] * 4))
            mis += [""] * (len(opts) - len(mis))
            ans = int(q["answer_index"])
            if len(opts) != 4 or not (0 <= ans < 4):
                continue
            order = list(range(4))
            random.shuffle(order)  # LLMs love putting the answer first
            out.append({
                "question": q["question"],
                "options": [opts[i] for i in order],
                "answer_index": order.index(ans),
                "explanation": q.get("explanation", ""),
                "misconceptions": [mis[i] for i in order],
            })
        except Exception:
            continue
    if not out:
        raise ValueError("Could not generate a valid quiz, please try again.")
    return out
 
 
def make_flashcards(topic: str, context: str, n: int = 6):
    data = ask_json(
        "You write concise, high-quality flashcards.",
        f'Topic: {topic}\nCreate {n} flashcards from this material. Format: [{{"front": "question", "back": "short answer"}}]\n\nMATERIAL:\n{context}',
        2000,
    )
    return [{"front": d["front"], "back": d["back"]} for d in data if "front" in d and "back" in d]
 
 
HINT_LEVELS = {
    1: "Level 1: ask ONE guiding question only. Reveal no facts.",
    2: "Level 2: give a concrete hint or analogy, then ask a question.",
    3: "Level 3: break the problem into steps, do all but the final step, and ask the student to finish.",
}
 
 
def socratic_reply(history: list, context: str, level: int = 1) -> str:
    system = (
        "You are a patient Socratic tutor. NEVER give the final answer directly, even if asked. "
        "Guide the student to discover it. " + HINT_LEVELS[level] + " "
        "If the student answers correctly, confirm it and ask a deeper follow-up. "
        "If they are wrong, don't say 'wrong' harshly, probe their reasoning. Max 120 words. "
        "Base your guidance on the study material below; if the question is outside it, say so.\n\n"
        "STUDY MATERIAL:\n" + context
    )
    return chat(system, history, 500)
 
 
def class_summary(report: str) -> str:
    return ask(
        "You are an instructional coach helping a teacher.",
        "Below is class-wide quiz data (topic accuracy + misconceptions students showed, with counts). "
        "1) Cluster the misconceptions into the 3-5 biggest themes. 2) For each, explain in one line what students "
        "wrongly believe and a 2-3 minute re-teaching activity. 3) Give a one-line verdict on which topic to revisit first.\n\n"
        + report,
        1200,
    )