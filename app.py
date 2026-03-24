import streamlit as st
import pandas as pd
from functions import download_pdf, extract_text, summarize_text, get_pdf_link

st.title("📄 Patent Summarizer (Local LLM)")

if "results" not in st.session_state:
    st.session_state["results"] = []
if "processed_file_name" not in st.session_state:
    st.session_state["processed_file_name"] = None

uploaded_file = st.file_uploader("Upload Excel file with patent URLs", type=["xlsx"])
process_clicked = st.button("Process Patents", type="primary", disabled=uploaded_file is None)

if process_clicked and uploaded_file is not None:
    df = pd.read_excel(uploaded_file)

    if "url" not in df.columns:
        st.error("Excel must contain a 'url' column")
    else:
        results = []
        total = len(df)
        progress = st.progress(0)
        status_box = st.empty()  # one reusable element

        for i, row in df.iterrows():
            url = row["url"]

            try:
                pdf_url = get_pdf_link(url)
                pdf_path = f"patent_{i}.pdf"
                download_pdf(pdf_url, pdf_path)
                text = extract_text(pdf_path)
                summary = summarize_text(text)

                results.append(
                    {
                        "url": url,
                        "pdf_path": pdf_path,
                        "summary": summary,
                    }
                )

                status_box.success(f"Done {i + 1}/{total}")

            except Exception as e:
                status_box.error(f"Error at {i + 1}/{total} for {url}: {e}")

            progress.progress((i + 1) / total)

        status_box.success(f"Finished processing {len(results)}/{total}")
        st.session_state["results"] = results
        st.session_state["processed_file_name"] = uploaded_file.name

results = st.session_state.get("results", [])

if results:
    st.subheader("Processed Patents")
    st.caption("Click Open to view PDF + summary in the viewer page.")

    for i, item in enumerate(results):
        c1, c2 = st.columns([8, 1])
        c1.write(f"{i+1}. {item['url']}")
        if c2.button("Open", key=f"open_{i}"):
            st.session_state["selected_patent_index"] = i
            st.switch_page("pages/patent_viewer.py")

    result_df = pd.DataFrame(results)
    st.download_button(
        "Download Results",
        result_df.to_csv(index=False),
        file_name="summaries.csv",
    )
elif st.session_state["processed_file_name"]:
    st.info("No successful summaries were produced for the last run.")