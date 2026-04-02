import io
import zipfile

import pandas as pd
import requests
import streamlit as st

from auth import get_current_user, render_auth_gate, sign_out
from db import (
    get_patent_record,
    grant_patent_access,
    has_patent_chunks,
    init_db,
    list_user_patent_records,
    replace_patent_chunks,
    upsert_patent_record,
    upsert_user_from_profile,
)
from functions import (
    build_retrieval_payload,
    download_pdf,
    extract_text,
    get_pdf_link,
    normalize_url,
    patent_id_from_url,
    summarize_text,
)
from db import has_patent_chunks, replace_patent_chunks

st.set_page_config(layout="wide", page_title="Patent Studio")

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500&display=swap');

:root {
  --paper: #f8f6ef;
  --ink: #0e1726;
  --coral: #f15b42;
  --teal: #0b6e79;
}

.stApp {
  font-family: 'IBM Plex Sans', sans-serif;
  background:
    radial-gradient(circle at 8% 12%, rgba(241, 91, 66, 0.2), transparent 30%),
    radial-gradient(circle at 85% 10%, rgba(11, 110, 121, 0.2), transparent 35%),
    linear-gradient(150deg, #f8f6ef 20%, #edf6f8 100%);
  color: var(--ink);
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

h1, h2, h3 {
  font-family: 'Space Grotesk', sans-serif;
  letter-spacing: -0.02em;
}

.card {
  border: 1px solid rgba(14, 23, 38, 0.12);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.65);
  padding: 14px;
}
</style>
""",
    unsafe_allow_html=True,
)

st.title("Patent Studio")
st.caption("Upload Excel links, download patents locally, auto-summarize, and open each patent for deep Q&A.")

if "results" not in st.session_state:
    st.session_state["results"] = []
if "failed" not in st.session_state:
    st.session_state["failed"] = []
if "processed_file_name" not in st.session_state:
    st.session_state["processed_file_name"] = None


def check_ollama():
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def check_database():
    try:
        init_db()
        return True, ""
    except Exception as exc:
        return False, str(exc)


def load_results_for_user(user_id):
    records = list_user_patent_records(user_id)
    results = []
    for record in records:
        results.append(
            {
                "status": "stored",
                "url": record["url"],
                "patent_id": record["patent_id"],
                "summary": record.get("summary", ""),
            }
        )
    return results


current_user = get_current_user()
if not current_user:
    render_auth_gate()
    st.stop()

upsert_user_from_profile(current_user)

if st.session_state.get("auth_loaded_user_id") != current_user["user_id"]:
    st.session_state["results"] = load_results_for_user(current_user["user_id"])
    st.session_state["failed"] = []
    st.session_state["auth_loaded_user_id"] = current_user["user_id"]

st.caption(f"Signed in as {current_user.get('display_name') or current_user.get('email') or current_user['user_id']}")

signout_col, _ = st.columns([1, 6])
with signout_col:
    if st.button("Sign out", use_container_width=True):
        sign_out()
        st.rerun()


def parse_urls_from_excel(file_obj):
    df = pd.read_excel(file_obj)
    if "url" not in df.columns:
        raise ValueError("Excel must contain a 'url' column")

    df["url"] = df["url"].astype(str).map(normalize_url)
    df = df[df["url"] != ""]
    df = df.drop_duplicates(subset=["url"])
    return df


def process_patent_url(url, model_name, force_reprocess=False):
    patent_id = patent_id_from_url(url)
    existing = get_patent_record(patent_id)
    has_chunks = has_patent_chunks(patent_id)

    if (
        not force_reprocess
        and existing
        and existing.get("pdf_data")
        and existing.get("text_content")
        and existing.get("summary")
        and has_chunks
    ):
        return {
            "status": "cached",
            "url": url,
            "patent_id": patent_id,
            "summary": existing.get("summary", ""),
        }

    pdf_url = get_pdf_link(url)
    pdf_bytes = download_pdf(pdf_url)
    text = extract_text(pdf_bytes=pdf_bytes)
    if not text.strip():
        raise ValueError("Extracted text is empty")

    summary = summarize_text(text, model=model_name)
    chunks, embeddings = build_retrieval_payload(text)

    upsert_patent_record(
        patent_id=patent_id,
        url=url,
        pdf_data=pdf_bytes,
        text_content=text,
        summary=summary,
    )
    replace_patent_chunks(patent_id, chunks, embeddings)
    grant_patent_access(current_user["user_id"], patent_id)

    return {
        "status": "done",
        "url": url,
        "patent_id": patent_id,
        "summary": summary,
    }


def create_pdf_zip(results):
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in results:
            patent_id = item.get("patent_id")
            if not patent_id:
                continue

            record = get_patent_record(patent_id)
            pdf_bytes = record.get("pdf_data") if record else None
            if pdf_bytes:
                archive.writestr(f"{patent_id}.pdf", pdf_bytes)
    zip_buffer.seek(0)
    return zip_buffer


with st.container():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        uploaded_file = st.file_uploader("Upload Excel with patent links", type=["xlsx"])
    with col2:
        model_name = st.text_input("Ollama model", value="llama3:8b")
    with col3:
        force_reprocess = st.checkbox("Reprocess existing", value=False)

    process_clicked = st.button("Process Patents", type="primary", disabled=uploaded_file is None)
    st.markdown("</div>", unsafe_allow_html=True)

if process_clicked and uploaded_file is not None:
    db_ok, db_error = check_database()
    if not db_ok:
        st.error(f"Database connection failed: {db_error}")
    elif not check_ollama():
        st.error("Ollama is not reachable at localhost:11434. Start Ollama and retry.")
    else:
        try:
            df = parse_urls_from_excel(uploaded_file)
            urls = df["url"].tolist()
            if not urls:
                st.warning("No valid URLs found in the uploaded file.")
            else:
                results = []
                failed = []
                progress = st.progress(0)
                status_box = st.empty()
                total = len(urls)

                for idx, url in enumerate(urls, start=1):
                    try:
                        status_box.info(f"Processing {idx}/{total}: {url}")
                        item = process_patent_url(url, model_name=model_name, force_reprocess=force_reprocess)
                        results.append(item)
                    except Exception as exc:
                        failed.append({"url": url, "error": str(exc)})
                    progress.progress(idx / total)

                st.session_state["results"] = results
                st.session_state["failed"] = failed
                st.session_state["processed_file_name"] = uploaded_file.name

                status_box.success(f"Finished: {len(results)} succeeded, {len(failed)} failed.")
        except Exception as exc:
            st.error(str(exc))

results = st.session_state.get("results", [])
failed = st.session_state.get("failed", [])

if results:
    st.subheader("Processed Patents")
    st.caption("Open any patent to view PDF, read summary, and chat with document context.")

    for idx, item in enumerate(results):
        c1, c2 = st.columns([8, 1])
        c1.write(f"{idx + 1}. {item['url']} ({item['status']})")
        if c2.button("Open", key=f"open_{idx}"):
            st.session_state["selected_patent_index"] = idx
            st.switch_page("pages/patent_viewer.py")

    result_df = pd.DataFrame(results)
    st.download_button(
        "Download Summaries CSV",
        result_df[["url", "patent_id", "summary"]].to_csv(index=False),
        file_name="patent_summaries.csv",
        mime="text/csv",
    )

    zip_payload = create_pdf_zip(results)
    st.download_button(
        "Download PDFs (ZIP)",
        data=zip_payload,
        file_name="patent_documents.zip",
        mime="application/zip",
    )

if failed:
    st.subheader("Failed URLs")
    st.dataframe(pd.DataFrame(failed), use_container_width=True)

if not results and st.session_state.get("processed_file_name"):
    st.info("No successful patents are available from the last processing run.")