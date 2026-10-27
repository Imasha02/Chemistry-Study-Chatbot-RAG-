
import json
import chromadb
from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-en-v1.5"   
DB_FOLDER = "chroma_db"                 
COLLECTION = "chem"

chunks = json.load(open("chunks.json", encoding="utf-8"))
texts = [c["text"] for c in chunks]
print(f"Loaded {len(chunks)} chunks. Loading the model (first time downloads it)...")

model = SentenceTransformer(MODEL_NAME)
model.max_seq_length = 512

too_long = [c["chunk_id"] for c, t in zip(chunks, texts)
            if len(model.tokenizer.encode(t)) > 512]
print(f"Chunks longer than the model can read: {len(too_long)} of {len(chunks)}")
if too_long:
    print("  (their last few lines are invisible to search; see the note I gave you)")

vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=True)

client = chromadb.PersistentClient(path=DB_FOLDER)
try:
    client.delete_collection(COLLECTION)      # start fresh each time
except Exception:
    pass
col = client.create_collection(COLLECTION)

col.add(
    ids=[c["chunk_id"] for c in chunks],
    documents=texts,
    embeddings=vectors.tolist(),
    metadatas=[{
        "unit": c["unit"],
        "section_id": c["section_id"],
        "section_title": c["section_title"],
        "page_start": c["page_start"],
        "page_end": c["page_end"],
        "needs_vision_check": c["needs_vision_check"],
    } for c in chunks],
)
print(f"Done. Saved {col.count()} chunks into the '{DB_FOLDER}' folder.")