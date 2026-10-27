import json
import sys
import urllib.error
import urllib.request

from search import search         

MODEL = "llama3.2:3b"               
OLLAMA_URL = "http://localhost:11434/api/chat"
TOP_K = 4                           
MIN_SCORE = 0.60                   
                                    

SYSTEM_PROMPT = """You are a study assistant for a Grade 12 A/L Chemistry resource book.
Rules:
1. Answer ONLY using the numbered excerpts below. Do not use outside knowledge.
2. After each fact, cite the excerpt like [c194, p.123-124].
3. If the excerpts do not contain the answer, reply exactly: Not in the book.
4. Keep answers short and clear. Show calculation steps when the excerpts give them.
5. In the excerpts, "->" is a reaction arrow added by a script (it may really be an
   equilibrium arrow), and "[?]" marks a formula that could not be read. If you need
   something marked "[?]", say you cannot read it."""


def pages_text(h):
    return (f"p.{h['page_start']}" if h["page_start"] == h["page_end"]
            else f"pp.{h['page_start']}-{h['page_end']}")


def build_user_message(question, hits):
    parts = []
    for h in hits:
        parts.append(f"--- Excerpt {h['chunk_id']} ({pages_text(h)}) ---\n{h['text']}")
    return "\n\n".join(parts) + f"\n\nQuestion: {question}"


def call_ollama(system_prompt, user_message):
    payload = json.dumps({
        "model": MODEL,
        "stream": False,
        "options": {"temperature": 0, "num_ctx": 4096},
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user_message}],
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read().decode("utf-8"))["message"]["content"].strip()


def answer(question, min_score=None, top_k=None):
    """Returns (answer_text, hits). Never crashes if Ollama is off - it explains instead."""
    min_score = MIN_SCORE if min_score is None else min_score
    top_k = TOP_K if top_k is None else top_k
    hits = search(question, k=top_k)
    best = hits[0]["score"]
    if best < min_score:
        return (f"Not in the book. (Best match score {best:.2f} is below the cutoff "
                f"{min_score:.2f}.)"), hits
    try:
        text = call_ollama(SYSTEM_PROMPT, build_user_message(question, hits))
    except urllib.error.URLError:
        return ("Could not reach Ollama. Open the Ollama app (or run 'ollama serve' in "
                "another terminal) and try again."), hits
    return text, hits


def show(question):
    print(f"\nQ: {question}\n(thinking... the first answer is slow while the model loads)")
    text, hits = answer(question)
    print(f"\n{text}\n")
    print("Sources searched:")
    for h in hits:
        flag = "  [garbled text, double-check in the book]" if h["flag"] else ""
        print(f"  {h['chunk_id']} | {h['section']} | {pages_text(h)} | score {h['score']:.2f}{flag}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        show(" ".join(sys.argv[1:]))
    else:
        while True:
            q = input("\nQuestion (empty to quit): ").strip()
            if not q:
                break
            show(q)
