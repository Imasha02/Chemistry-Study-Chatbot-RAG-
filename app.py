"""
app.py  --  Step 7: a chat window for your study bot.

Run:  streamlit run app.py
(needs Ollama running, plus chroma_db built by build_index.py)
"""

import streamlit as st

from ask import answer, MIN_SCORE, TOP_K, pages_text

st.set_page_config(page_title="Chemistry Study Bot", page_icon="🧪")
st.title("Chemistry Study Bot")
st.caption("Grade 12 A/L Chemistry resource book (Units 1, 2, 3 and 6). "
           "Answers come only from the book, with page numbers.")

with st.sidebar:
    st.header("Settings")
    min_score = st.slider(
        "Search cutoff", 0.0, 0.9, MIN_SCORE, 0.01,
        help="If the best search match scores below this, the bot says 'Not in the book' "
             "without asking the model. Set it to 0 to test the model's own refusal.")
    top_k = st.slider("Chunks shown to the model", 2, 8, TOP_K)
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()
    st.markdown("---")
    st.caption("Small local models can be wrong, especially on calculations. "
               "Check important answers against the cited page.")

if "messages" not in st.session_state:
    st.session_state.messages = []


def render_sources(hits):
    with st.expander("Sources searched"):
        for h in hits:
            flag = "  (garbled text, double-check in the book)" if h["flag"] else ""
            st.write(f"**{h['chunk_id']}** | {h['section']} | {pages_text(h)} | "
                     f"score {h['score']:.2f}{flag}")


for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("hits"):
            render_sources(m["hits"])

question = st.chat_input("Ask a question about the book")
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching the book and thinking... (the first answer is slow)"):
            text, hits = answer(question, min_score=min_score, top_k=top_k)
        st.markdown(text)
        render_sources(hits)

    st.session_state.messages.append({"role": "assistant", "content": text, "hits": hits})