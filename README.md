# Chemistry Study Chatbot (RAG)

A free, local chatbot that answers questions from a chemistry study book. It looks up the most relevant passages from the book first, then a small local language model writes the answer using only those passages.

I built and tested it with the **Advanced Level Inorganic Chemistry resource book** (Units 1, 2, 3 and 6).

Built as a learning project in plain Python, so every step is easy to read and change.


## How it works

```
PDF  ->  extract.py  ->  chunk.py  ->  build_index.py  ->  search  ->  Ollama  ->  Streamlit
         (raw text)      (labelled     (embeddings        (top       (writes     (chat
                          chunks)       + Chroma)          chunks)    answer)     window)
```

| Step | File | What it does |
|------|------|--------------|
| 1 | `extract.py` | Pulls the text of every page out of the PDF into `pages.json` |
| 2 | `chunk.py` | Cleans the text and cuts it into ~220-word chunks, each labelled with unit, section and page range. Saves `chunks.json` and `chunks_preview.txt` |
| 3 | `make_book.py` | Builds a single `book.txt` used for a baseline test (attach it to a chat and ask questions) |
| 4 | `build_index.py` | Turns each chunk into a vector with the `BAAI/bge-small-en-v1.5` embedding model and stores them in a Chroma database (`chroma_db/`, collection `chem`) |
| 5 | `app.py` | Streamlit chat window: searches the index, sends the best chunks and your question to Ollama, shows the answer with its sources |

Steps 4 and 5 are in progress.

## What `chunk.py` does

1. Skips the cover, contents pages and each unit's opening page.
2. Works out the real printed page number (PDF page - 10) and the unit from the page header.
3. Removes the repeated header and page number, restores lost reaction arrows as `->` (a best guess), and marks garbled formulas as `[?]`.
4. Finds the book's own section headings (like `2.3.1 Hybridization`) and starts a new section at each one.
5. Splits each section into chunks of about 220 words with a 30-word overlap, and adds a breadcrumb such as `Unit 2: Structure and Bonding > 2.3.3 Resonance structures`.
6. Flags any chunk containing `[?]` or sitting on a garbled page with `needs_vision_check`.

## Requirements

- Python 3.10+
- [Ollama](https://ollama.com) installed, with a small model pulled
- The Python packages in `requirements.txt`

## Usage

1. Put your PDF in the `data/` folder and set its filename in `extract.py`.
2. Run the steps in order:

```bash
python extract.py        # PDF -> pages.json
python chunk.py          # pages.json -> chunks.json + chunks_preview.txt
python build_index.py    # chunks.json -> chroma_db/
streamlit run app.py     # start the chatbot
```

3. Open `chunks_preview.txt` after step 2 and proofread a few chunks, especially those marked `[CHECK: garbled text]`.

## Using a different book

`chunk.py` is tuned to the A/L Inorganic Chemistry resource book. For another book, change these at the top of the file:

- `FRONT_MATTER_LAST_PDF_PAGE` and `PAGE_OFFSET`
- `UNIT_TITLES` and `UNIT_SECTION_PREFIX`
- `HEADER_RE` (the pattern for the running page header)

Some of the cleaning tricks (such as arrow restoration) may not apply.

## Known limitations

- Nuclear-reaction equations and formulas in a broken maths font may be garbled (marked `[?]`).
- Restored arrows are always `->`, so equilibrium arrows cannot be told apart.
- Tables from the PDF come out flattened.
- The source book has its own typos, which are kept as they are.
- Small local models can struggle with calculations, so check numerical answers against the book.
- If you change the embedding model, delete `chroma_db/` and rebuild the index.

## Tech stack

- Python
- [sentence-transformers](https://www.sbert.net/) (`BAAI/bge-small-en-v1.5`) for embeddings
- [Chroma](https://www.trychroma.com/) for the vector database
- [Ollama](https://ollama.com) for the local language model
- [Streamlit](https://streamlit.io) for the interface
