import math
import re
import unicodedata
from collections import Counter

STOP = set(
    "a al algo ante como cual cuales cuando cuanto cuantos cuanta cuantas de del desde donde el ella en es esta este esto hay la las lo los me mi para por puedo que quien se si sin sobre su sus te tiene un una unos y o u con son ser documento favor puedes dime dice saber solicita solicitan solicitar debo debe puedo puedes funciona funcionan hacer".split()
)


def tokens(text):
    text = "".join(
        c
        for c in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(c) != "Mn"
    )
    return [
        word
        for word in re.findall(r"[a-z0-9]+", text)
        if len(word) > 2 and word not in STOP
    ]


def lexical_search(question, chunks, limit=4):
    query = set(tokens(question))
    if not query:
        return []
    bags = [Counter(tokens(chunk["text"])) for chunk in chunks]
    ranked = []
    for chunk, bag in zip(chunks, bags):
        matched = query.intersection(bag)
        coverage = len(matched) / len(query)
        if coverage < 0.60:
            continue
        score = sum(
            1 + math.log((len(chunks) + 1) / (1 + sum(word in other for other in bags)))
            for word in matched
        )
        ranked.append({**chunk, "score": score, "coverage": coverage})
    return sorted(ranked, key=lambda c: c["score"], reverse=True)[:limit]


def cosine(a, b):
    denominator = math.sqrt(sum(x * x for x in a) * sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b)) / denominator if denominator else 0.0


def demo_answer(question, chunks):
    candidates = lexical_search(question, chunks)
    if not candidates:
        return None
    # Return verbatim sentences: the demo does not generate claims.
    citations, seen = [], set()
    query = set(tokens(question))
    for chunk in candidates:
        sentences = re.split(r"(?<=[.!?])\s+", chunk["text"])
        scored = sorted(
            sentences, key=lambda s: len(query.intersection(tokens(s))), reverse=True
        )
        if not scored or not query.intersection(tokens(scored[0])):
            continue
        quote = scored[0]
        if quote in seen:
            continue
        seen.add(quote)
        citations.append(
            {"chunk_id": chunk["id"], "page": chunk["page"], "quote": quote}
        )
        if len(citations) == 3:
            break
    return (
        {
            "answer": "Encontré estos fragmentos relacionados con tu pregunta:\n\n"
            + "\n\n".join(c["quote"] for c in citations),
            "citations": citations,
        }
        if citations
        else None
    )
