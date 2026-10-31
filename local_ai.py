"""Offline engine. Builds quizzes, flashcards and tutor hints straight from the
student's notes with plain text processing, so the app works with no API key."""
import random
import re
from collections import Counter
 
STOP = set("""a an the and or but if then than that this these those is are was were be been being of in on at to
for from by with as it its into over under about between during before after also can could may might will would
should must not no nor so such which who whom whose what when where why how there their they them he she his her we
our you your all any each other some more most many much very just only own same both few too while until because
usually often called known used uses using use makes make made takes take taken happens happen""".split())
 
TERM_RE = re.compile(r"\b[A-Z]{2,}[A-Za-z0-9]*\b|\b[A-Za-z][A-Za-z\-]{4,}\b")
DEF_RE = re.compile(r"^(?P<t>[A-Za-z][A-Za-z\- ]{2,40}?) (?:is|are|refers to|means) (?P<d>.{20,})$")
GENERIC = set("""including inside matters speed absorbs releases released loses lowers lowering stored fits
goes goings things something anything everything within without across around through different another
several certain given again always never usually general important simple""".split())
NOT_SUBJECT = {"it", "this", "that", "they", "these", "those", "there", "he", "she", "we", "which"}
 
# remembers what answer the tutor is waiting for, keyed by the tutor's own message
_EXPECT = {}
 
 
# ---------- reading the notes ----------
 
def _is_heading(line):
    l = line.strip()
    if not l or len(l) > 70 or l[-1] in ".,;!?":
        return False
    if len(l.split()) > 8 or not (l[0].isupper() or l[0].isdigit()):
        return False
    return not l.startswith(("-", "*", "\u2022"))
 
 
def _heading_lines(lines):
    """indexes of lines that look like headings"""
    found = set()
    for i, line in enumerate(lines):
        if not _is_heading(line) or line.strip().lower() in STOP:
            continue
        after_blank = i == 0 or not lines[i - 1].strip()
        numbered = bool(re.match(r"^(chapter|unit|section|topic)\s+\d+|^\d+(\.\d+)*[.)]?\s+\S", line.strip(), re.I))
        if after_blank or numbered or line.strip().isupper():
            found.add(i)
    return found
 
 
def _clean_heading(line):
    line = re.sub(r"^(chapter|unit|section|topic)\s+\d+\s*[:.\-]*\s*", "", line.strip(), flags=re.I)
    line = re.sub(r"^\d+(\.\d+)*[.)]?\s+", "", line)
    return line.strip(" :-")
 
 
def sections(text):
    secs, title, buf = [], "Notes", []
    lines = text.splitlines()
    heads = _heading_lines(lines)
    for i, line in enumerate(lines):
        if i in heads:
            if " ".join(buf).strip():
                secs.append((title, "\n".join(buf)))
            title, buf = _clean_heading(line), []
        else:
            buf.append(line)
    if " ".join(buf).strip():
        secs.append((title, "\n".join(buf)))
    return secs
 
 
def sentences(text):
    raw = text.splitlines()
    heads = _heading_lines(raw)
    lines = [l.strip() for i, l in enumerate(raw) if l.strip() and i not in heads]
    flat = " ".join(lines)
    good = []
    for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", flat):
        s = s.strip()
        if 7 <= len(s.split()) <= 40 and "->" not in s and "=" not in s:
            if sum(c.isalpha() for c in s) / len(s) > 0.7:
                good.append(s)
    return good
 
 
def candidates(sentence, include_first=False):
    out = []
    for m in TERM_RE.finditer(sentence):
        w = m.group().strip("-")
        lw = w.lower()
        if (m.start() == 0 and not include_first) or lw in STOP or lw in GENERIC:
            continue
        if not w.isupper() and lw.endswith(("ing", "ed", "ly")):   # verbs and adverbs make bad answers
            continue
        if len(w) < 6 and not w.isupper() and not w[0].isupper():
            continue
        out.append(w)
    return out
 
 
def doc_freq(sents):
    df = Counter()
    for s in sents:
        for w in {x.lower() for x in candidates(s)}:
            df[w] += 1
    return df
 
 
def pick_term(sentence, df, total, skip=()):
    ok = [w for w in candidates(sentence)
          if df[w.lower()] <= max(2, total * 0.35) and w.lower() not in skip]
    if not ok:
        return None
    return max(ok, key=lambda w: (3 if w.isupper() else 0) + min(len(w), 12) + 2 * min(df[w.lower()], 3))
 
 
def distractors(answer, sentence, pool, similar=True):
    sl = sentence.lower()
    shape = lambda w: (w.isupper(), w[0].isupper())
    opts = [w for w in pool if w.lower()[:5] != answer.lower()[:5] and w.lower() not in sl]
    same = [w for w in opts if shape(w) == shape(answer)]
    use = same if len(same) >= 3 else opts
    if similar:
        use.sort(key=lambda w: (abs(len(w) - len(answer)), random.random()))
        use = use[:8]
    random.shuffle(use)
    return use[:3] if len(use) >= 3 else None
 
 
def blank(sentence, term):
    return re.sub(r"\b" + re.escape(term) + r"\b", "_____", sentence, count=1)
 
 
def _subject(t):
    return re.sub(r"^(the|a|an)\s+", "", t.strip(), flags=re.I)
 
 
def definitions(sents):
    found = []
    for s in sents:
        m = DEF_RE.match(s)
        if not m:
            continue
        t, d = m.group("t"), m.group("d").rstrip(".")
        if len(t.split()) > 5 or t.split()[0].lower() in NOT_SUBJECT:
            continue
        if len(d) > 130:
            d = d[:130].rsplit(" ", 1)[0] + "..."
        found.append((_subject(t), d[0].upper() + d[1:], s))
    return found
 
 
# ---------- topics ----------
 
def find_topics(text):
    secs = [(t, b) for t, b in sections(text) if t != "Notes" and len(b) > 120]
    names = []
    for t, _ in secs:
        if t not in names:
            names.append(t)
    if len(names) >= 2:
        return names[:12]
 
    # no headings: split into parts and name each one after its most typical words
    sents = sentences(text)
    k = min(8, max(2, len(sents) // 8))
    size = max(1, len(sents) // k)
    parts = [sents[i:i + size] for i in range(0, len(sents), size)][:k]
    overall = Counter(w.lower() for s in sents for w in candidates(s))
    acronyms = {w.lower() for s in sents for w in candidates(s) if w.isupper()}
    names = []
    for part in parts:
        c = Counter(w.lower() for s in part for w in candidates(s))
        top = sorted(c, key=lambda w: c[w] ** 2 / overall[w], reverse=True)[:2]
        name = " and ".join(w.upper() if w in acronyms else w.title() for w in top) or "General"
        while name in names:
            name += " II"
        names.append(name)
    return names
 
 
# ---------- quiz ----------
 
def make_quiz(topic, material, level, n):
    sents = sentences(material)
    if len(sents) < 4:
        raise ValueError("Not enough text on this topic to build a quiz. Add more detailed notes.")
    df = doc_freq(sents)
    pool = {}
    for s in sents:
        for w in candidates(s):
            pool.setdefault(w.lower(), w)
    pool = list(pool.values())
    random.shuffle(sents)
    similar = level != "easy"
 
    cloze_qs, def_qs = [], []
    for s in sents:
        term = pick_term(s, df, len(sents))
        if not term:
            continue
        dis = distractors(term, s, pool, similar)
        if not dis:
            continue
        opts = [term] + dis
        cloze_qs.append({
            "sentence": s,
            "question": "Fill in the blank: " + blank(s, term),
            "options": opts,
            "answer": 0,
            "explanation": s,
            "misconceptions": ["", *[f"Confuses {d} with {term}" for d in dis]],
        })
 
    defs = definitions(sents)
    if len(defs) >= 4:
        for t, d, s in defs:
            others = [x for x in defs if x[0].lower() != t.lower()]
            random.shuffle(others)
            others = others[:3]
            if len(others) < 3:
                continue
            def_qs.append({
                "sentence": s,
                "question": f"Which of these best describes {t}?",
                "options": [d] + [o[1] for o in others],
                "answer": 0,
                "explanation": s,
                "misconceptions": ["", *[f"Mixes up {t} with {o[0]}" for o in others]],
            })
 
    quiz, used = [], set()
    for i in range(n):
        want_def = level == "hard" or (level == "medium" and i % 2 == 1)
        first, second = (def_qs, cloze_qs) if want_def else (cloze_qs, def_qs)
        q = None
        for src in (first, second):
            while src and q is None:
                cand = src.pop()
                if cand["sentence"] not in used:
                    q = cand
        if q is None:
            break
        used.add(q["sentence"])
        order = list(range(4))
        random.shuffle(order)
        quiz.append({
            "question": q["question"],
            "options": [q["options"][j] for j in order],
            "answer": order.index(0),
            "explanation": q["explanation"],
            "misconceptions": [q["misconceptions"][j] for j in order],
        })
    if not quiz:
        raise ValueError("Could not build questions from this text. Add more detailed notes.")
    return quiz
 
 
def make_cards(topic, material, n=6):
    sents = sentences(material)
    df = doc_freq(sents)
    cards, used = [], set()
    defs = definitions(sents)
    random.shuffle(defs)
    for t, d, s in defs:
        cards.append({"front": f"Explain: {t}", "back": d})
        used.add(s)
        if len(cards) >= n // 2:
            break
    random.shuffle(sents)
    for s in sents:
        if len(cards) >= n:
            break
        if s in used:
            continue
        term = pick_term(s, df, len(sents))
        if term:
            cards.append({"front": "Fill in the blank: " + blank(s, term), "back": term})
            used.add(s)
    if not cards:
        raise ValueError("Not enough text to make flashcards.")
    return cards
 
 
# ---------- tutor ----------
 
def _stems(text):
    return {w.lower()[:5] for w in re.findall(r"[A-Za-z]{3,}", text) if w.lower() not in STOP}
 
 
def _is_question(msg):
    return msg.endswith("?") or bool(re.match(
        r"^(what|why|how|when|where|which|who|explain|define|tell|can|does|do|is|are)\b", msg.lower()))
 
 
def tutor_reply(history, material, level):
    msg = history[-1]["content"].strip()
    prev = next((m["content"] for m in reversed(history[:-1]) if m["role"] == "assistant"), None)
    stuck = re.search(r"\b(idk|don'?t know|stuck|no idea|hint|help)\b", msg.lower())
 
    # was the tutor waiting for a specific word?
    exp = _EXPECT.get(prev)
    if exp and (stuck or not _is_question(msg) or any(t.lower() in msg.lower() for t in exp[0])):
        terms, sentence = exp
        if any(t.lower() in msg.lower() for t in terms):
            return (f"Yes, that's it. This is the full line from your notes: \"{sentence}\"\n\n"
                    "Now explain in your own words why that is the case.")
        t = terms[0]
        reply = (f"Not yet. The word starts with \"{t[0]}\" and has {len(t)} letters. "
                 "Read the rest of the sentence again: what would make it make sense?")
        _EXPECT[reply] = exp
        return reply
 
    sents = sentences(material)
    q = _stems(msg)
    scored = sorted(((len(q & _stems(s)), s) for s in sents), key=lambda x: -x[0])
    if not scored or scored[0][0] == 0:
        return ("I can't find that in your notes. Try using words from your notes, "
                "or add more notes on this topic.")
    best = scored[0][1]
    df = doc_freq(sents)
 
    preface = ""
    if not _is_question(msg) and not stuck:
        keys = {w.lower()[:5] for w in candidates(best)}
        hit = len(keys & q) / len(keys) if keys else 0
        if hit >= 0.4:
            return ("That matches your notes. Take it one step further: why does it work that way, "
                    "or what would change if it did not?")
        preface = "You are close, but something is missing. "
 
    asked = {w.lower() for w in re.findall(r"[A-Za-z]{3,}", msg)}
    focus = next((w for w in candidates(best, include_first=True) if w.lower()[:5] in q), None)
    term = pick_term(best, df, len(sents), skip=asked)
    if term is None or level == 1:
        t = focus or term or "this idea"
        options = [
            f"What do you already know about {t}? Say what it does or where it happens, then we can build on it.",
            "Which word in your question is the key idea, and how would you define it yourself?",
            f"Start small: what is {t}, and what is it connected to in your notes?",
        ]
        return preface + options[len(msg) % 3]
 
    if level == 2:
        reply = (f"{preface}Here is a line from your notes with a word missing:\n\n> {blank(best, term)}\n\n"
                 "Which word fits in the blank?")
        _EXPECT[reply] = ([term], best)
        return reply
 
    second = pick_term(best, df, len(sents), skip=asked | {term.lower()})
    terms = [term] + ([second] if second else [])
    text = best
    for t in terms:
        text = blank(text, t)
    pool = list({w.lower(): w for s in sents for w in candidates(s)}.values())
    extra = [w for w in pool if w.lower() not in {t.lower() for t in terms} and w.lower()[:5] not in q]
    random.shuffle(extra)
    bank = terms + extra[:2]
    random.shuffle(bank)
    reply = (f"{preface}Let's do this step by step. Fill in the blanks:\n\n> {text}\n\n"
             f"Word bank: {', '.join(bank)}\n\nTell me the word for the first blank.")
    _EXPECT[reply] = (terms, best)
    return reply
 
 
# ---------- teacher summary ----------
 
def class_report(by_topic, table):
    weakest = by_topic.iloc[0]
    lines = [f"**Revisit first:** {weakest['topic']} ({weakest['accuracy']:.0%} correct across the class).", ""]
    lines.append("**Main misconceptions and what to do about them**")
    for _, r in table.head(5).iterrows():
        m = r["misconception"]
        if m.startswith(("Mixes up", "Confuses")):
            fix = ("put the two ideas side by side in a table, then have students sort six example "
                   "statements into the right column")
        elif m.startswith("Thinks"):
            fix = ("give a short scenario, ask students to predict the outcome, then check it against "
                   "the notes to expose the wrong idea")
        else:
            fix = "ask students to explain the idea to a partner in one minute, then correct together"
        lines.append(f"- {r['topic']}: {m} ({r['students']} students). Try this: {fix}.")
    lines += ["", "Re-run a short quiz on the weakest topic next class to check whether it improved."]
    return "\n".join(lines)