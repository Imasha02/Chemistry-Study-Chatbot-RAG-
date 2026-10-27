import sys
import chromadb
from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-en-v1.5"
DB_FOLDER = "chroma_db"
COLLECTION = "chem"
# bge models work a little better if questions get this prefix (chunks do not)
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

model = SentenceTransformer(MODEL_NAME)
col = chromadb.PersistentClient(path=DB_FOLDER).get_collection(COLLECTION)


def search(question, k=5):
    """Return the k best chunks as a list of dicts."""
    vec = model.encode([QUERY_PREFIX + question], normalize_embeddings=True)
    res = col.query(query_embeddings=vec.tolist(), n_results=k)
    hits = []
    for i in range(len(res["ids"][0])):
        meta = res["metadatas"][0][i]
        dist = res["distances"][0][i]
        hits.append({
            "chunk_id": res["ids"][0][i],
            "score": 1 - dist / 2,        # 1.0 = identical meaning (vectors are normalised)
            "unit": meta["unit"],
            "section": f"{meta['section_id']} {meta['section_title']}",
            "page_start": meta["page_start"],
            "page_end": meta["page_end"],
            "flag": meta["needs_vision_check"],
            "text": res["documents"][0][i],
        })
    return hits


def show(question):
    print(f"\nQ: {question}")
    for rank, h in enumerate(search(question), start=1):
        pages = (f"p.{h['page_start']}" if h["page_start"] == h["page_end"]
                 else f"pp.{h['page_start']}-{h['page_end']}")
        flag = "  [garbled text]" if h["flag"] else ""
        body = h["text"].split("\n", 1)[1] if "\n" in h["text"] else h["text"]
        print(f"  {rank}. {h['chunk_id']} | Unit {h['unit']} | {h['section']} | {pages} | "
              f"score {h['score']:.2f}{flag}")
        print(f"     {body[:140]}...")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        show(" ".join(sys.argv[1:]))
    else:
        while True:
            q = input("\nQuestion (empty to quit): ").strip()
            if not q:
                break
            show(q)
