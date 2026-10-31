"""Picks the engine. No API key -> offline engine (local_ai). With a key in .env,
Claude is used, and if a call fails the app quietly falls back to the offline one."""
import os
 
from dotenv import load_dotenv
 
import local_ai
 
load_dotenv()
last_error = ""
 
 
def using_api():
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    return bool(key) and key != "PASTE_YOUR_KEY_HERE"
 
 
def mode():
    return "Claude API" if using_api() else "Offline engine (no key needed)"
 
 
def _run(name, *args):
    global last_error
    if using_api():
        try:
            import llm
            last_error = ""
            return getattr(llm, name)(*args)
        except Exception as e:
            last_error = f"API call failed, used offline engine instead ({e})"
    return getattr(local_ai, name)(*args)
 
 
def find_topics(text):
    return _run("find_topics", text)
 
 
def make_quiz(topic, material, level, n):
    return _run("make_quiz", topic, material, level, n)
 
 
def make_cards(topic, material, n=6):
    return _run("make_cards", topic, material, n)
 
 
def tutor_reply(history, material, level):
    return _run("tutor_reply", history, material, level)
 
 
def class_report(by_topic, table):
    return _run("class_report", by_topic, table)