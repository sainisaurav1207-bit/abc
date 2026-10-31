"""Chunking + embedding search. Uses sentence-transformers embeddings if installed,
otherwise falls back automatically to TF-IDF vectors (no download needed)."""
import re
from functools import lru_cache

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


def chunk_text(text: str, size: int = 900, overlap: int = 150):
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) + 2 <= size:
            cur = (cur + "\n\n" + p).strip()
        else:
            if cur:
                chunks.append(cur)
            while len(p) > size:
                chunks.append(p[:size])
                p = p[size - overlap:]
            cur = p
    if cur:
        chunks.append(cur)
    return chunks


@lru_cache(maxsize=1)
def _load_st():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None


class Index:
    def __init__(self, chunks):
        self.chunks = chunks
        self.mode = "tfidf"
        model = _load_st() if chunks else None
        if model is not None:
            self.model = model
            self.emb = model.encode(chunks, normalize_embeddings=True)
            self.mode = "embeddings"
        else:
            self.vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
            self.mat = self.vec.fit_transform(chunks)

    def search(self, query: str, k: int = 4):
        if not self.chunks:
            return []
        if self.mode == "embeddings":
            q = self.model.encode([query], normalize_embeddings=True)[0]
            scores = self.emb @ q
        else:
            q = self.vec.transform([query])
            scores = (self.mat @ q.T).toarray().ravel()
        top = np.argsort(-scores)[:k]
        hits = [self.chunks[i] for i in top if scores[i] > 0]
        return hits or [self.chunks[top[0]]]
