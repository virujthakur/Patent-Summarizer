import streamlit as st

from db import get_patent_record, init_db, search_patent_chunks
from functions import chat_with_patent, embed_text_dense

st.set_page_config(layout="wide", page_title="Patent Workspace", initial_sidebar_state="collapsed")

st.markdown(
    """
<style>
[data-testid="stSidebar"] {
  display: none !important;
}

[data-testid="collapsedControl"] {
  display: none !important;
}
</style>
""",
    unsafe_allow_html=True,
)

results = st.session_state.get("results", [])
if not results:
    st.switch_page("app.py")

try:
    init_db()
except Exception as exc:
    st.error(f"Database connection failed: {exc}")
    st.stop()

if "chat_histories" not in st.session_state:
    st.session_state["chat_histories"] = {}
if "chat_model" not in st.session_state:
    st.session_state["chat_model"] = "llama3:8b"

default_index = st.session_state.get("selected_patent_index", 0)
default_index = max(0, min(default_index, len(results) - 1))

if "viewer_select_index_dropdown" not in st.session_state:
    st.session_state["viewer_select_index_dropdown"] = default_index


def on_patent_change():
    st.session_state["selected_patent_index"] = st.session_state["viewer_select_index_dropdown"]

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500&display=swap');

.stApp {
    font-family: 'IBM Plex Sans', sans-serif;
    background:
        radial-gradient(circle at 8% 12%, rgba(241, 91, 66, 0.2), transparent 30%),
        radial-gradient(circle at 85% 10%, rgba(11, 110, 121, 0.2), transparent 35%),
        linear-gradient(150deg, #f8f6ef 20%, #edf6f8 100%);
    color: #0e1726;
}

h1, h2, h3 {
    font-family: 'Space Grotesk', sans-serif;
    letter-spacing: -0.02em;
}

[data-testid="stSidebar"] {
  display: none;
}

[data-testid="collapsedControl"] {
  display: none;
}

header[data-testid="stHeader"] {
    display: none;
}

[data-testid="stToolbar"] {
    display: none;
}

[data-testid="stDecoration"] {
    display: none;
}

[data-testid="stStatusWidget"] {
    display: none;
}

#MainMenu {
    visibility: hidden;
}

div[data-testid="stButton"] button[kind="primary"] {
  font-weight: 700;
  letter-spacing: 0.01em;
  border-radius: 999px;
  padding: 0.45rem 0.9rem;
}

div[data-testid="stVerticalBlockBorderWrapper"] {
  background: rgba(255, 255, 255, 0.82);
  border-radius: 16px;
  box-shadow: 0 8px 22px rgba(14, 23, 38, 0.08);
}

.top-nav-label {
  font-size: 0.9rem;
  font-weight: 700;
  margin-bottom: 0.35rem;
}

@media (max-width: 980px) {
  .top-nav-label {
    margin-top: 0.4rem;
  }
}
</style>
""",
    unsafe_allow_html=True,
)


st.title("Patent Workspace")
st.caption("Top navigation")

with st.container(border=True):
    nav_left, nav_mid, nav_right = st.columns([1.2, 3.8, 1.4])

    with nav_left:
        st.markdown("<div class='top-nav-label'>Actions</div>", unsafe_allow_html=True)
        if st.button("← Back to processing", type="primary", use_container_width=True):
            st.switch_page("app.py")

    with nav_mid:
        st.markdown("<div class='top-nav-label'>Patent navigation</div>", unsafe_allow_html=True)
        st.selectbox(
            "Select patent",
            options=list(range(len(results))),
            format_func=lambda i: f"{i+1}. {results[i]['url']}",
            key="viewer_select_index_dropdown",
            on_change=on_patent_change,
            label_visibility="collapsed",
        )

    with nav_right:
        st.markdown("<div class='top-nav-label'>Chat model</div>", unsafe_allow_html=True)
        model_name = st.text_input(
            "Chat model",
            value=st.session_state["chat_model"],
            key="chat_model_input",
            help="Ollama model used for patent Q&A",
            label_visibility="collapsed",
        )
        st.session_state["chat_model"] = model_name.strip() or "llama3:8b"

selected_index = st.session_state["viewer_select_index_dropdown"]
st.session_state["selected_patent_index"] = selected_index

selected = results[selected_index]
patent_id = selected["patent_id"]
record = get_patent_record(patent_id)

if not record:
    st.error("No patent record found in database.")
    st.stop()

pdf_bytes = record.get("pdf_data")
patent_text = record.get("text_content") or ""
summary_text = selected.get("summary") or record.get("summary") or "No summary available."

st.caption(selected["url"])

tabs = st.tabs(["PDF", "Summary", "Chat"])

with tabs[0]:
    if not pdf_bytes:
        st.error("PDF not found in database for this patent.")
    else:
        st.pdf(pdf_bytes)

with tabs[1]:
    st.subheader("Summary")
    st.markdown(summary_text)

with tabs[2]:
    st.subheader("Chat With This Patent")
    patent_history = st.session_state["chat_histories"].setdefault(patent_id, [])

    clear_col, _ = st.columns([1, 4])
    with clear_col:
        if st.button("Clear chat", key=f"clear_{patent_id}"):
            st.session_state["chat_histories"][patent_id] = []
            st.rerun()

    for message in patent_history:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    question = st.chat_input("Ask a question about this patent")
    if question:
        if not patent_text.strip():
            st.error("No extracted text found in database for this patent.")
        else:
            patent_history.append({"role": "user", "content": question})
            with st.chat_message("user"):
                st.write(question)

            with st.chat_message("assistant"):
                with st.spinner("Thinking over patent context..."):
                    query_embedding = embed_text_dense(question)
                    chunks = search_patent_chunks(
                        patent_id=patent_id,
                        query_embedding=query_embedding,
                        top_k=4,
                    )

                    answer, chunks = chat_with_patent(
                        question=question,
                        patent_text=patent_text,
                        history=patent_history,
                        model=st.session_state["chat_model"],
                        retrieved_chunks=chunks,
                    )
                    st.write(answer)
                    with st.expander("Retrieved context"):
                        for idx, chunk in enumerate(chunks, start=1):
                            st.markdown(f"**Excerpt {idx}**")
                            st.write(chunk)

            patent_history.append({"role": "assistant", "content": answer})