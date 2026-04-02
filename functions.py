import hashlib
import os
import re
import time
from functools import lru_cache

import fitz  # PyMuPDF
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")


def normalize_url(url):
    return str(url).strip()


def patent_id_from_url(url):
    digest = hashlib.sha1(normalize_url(url).encode("utf-8")).hexdigest()[:12]
    return f"pat_{digest}"


def download_pdf(url, filename=None):
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    pdf_bytes = response.content
    if filename:
        with open(filename, "wb") as handle:
            handle.write(pdf_bytes)
    return pdf_bytes


def extract_text(pdf_path=None, pdf_bytes=None):
    if pdf_bytes is not None:
        with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
            pages = [page.get_text() for page in doc]
        return "\n".join(pages).strip()

    if not pdf_path:
        raise ValueError("Either pdf_path or pdf_bytes must be provided")

    with fitz.open(pdf_path) as doc:
        pages = [page.get_text() for page in doc]
    return "\n".join(pages).strip()


def chunk_text(text, chunk_size=1400, overlap=220):
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []

    chunks = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(text), step):
        chunk = text[start : start + chunk_size]
        if chunk:
            chunks.append(chunk)
        if start + chunk_size >= len(text):
            break
    return chunks


@lru_cache(maxsize=1)
def get_embedding_model():
    # Lazy import avoids loading heavy transformer stacks during app startup.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(EMBEDDING_MODEL_NAME)


def embed_texts_dense(texts):
    if not texts:
        return []

    vectors = get_embedding_model().encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vectors.tolist()


def embed_text_dense(text):
    vectors = embed_texts_dense([text])
    return vectors[0] if vectors else []


def build_retrieval_payload(text):
    chunks = chunk_text(text)
    embeddings = embed_texts_dense(chunks)
    return chunks, embeddings


def chat_ollama(messages, model="llama3:8b", temperature=0.1, top_p=0.9):
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature, "top_p": top_p},
        },
        timeout=240,
    )
    response.raise_for_status()
    data = response.json()
    return data["message"]["content"]


def summarize_text(text, model="llama3:8b"):
    system_rules = """
You are a patent analyst.
Write exactly one paragraph with 6 to 8 sentences.
Cover:
1. Problem in prior art
2. Core solution and mechanism
3. Main advantage over prior art
Use clear, non-jargon language where possible.
Do not use headings or bullet points.
"""

    example_output = """
This invention addresses discomfort and performance issues caused by the initial intensity spike in IPL light pulses. Prior designs used bulky inductors to smooth current, increasing cost and size. The invention places an electronic switch in series with the lamp and controls it at high frequency to shape current delivery. By rapidly toggling the switch, the controller converts the spike into a more uniform block-like pulse. This provides more stable light output while preserving treatment effectiveness. It also reduces component size and complexity compared with inductor-heavy designs.
"""

    messages = [
        {"role": "system", "content": system_rules},
        {"role": "assistant", "content": example_output},
        {
            "role": "user",
            "content": (
                "Summarize the following patent in the same style and format.\n\n"
                f"Patent text:\n{text}"
            ),
        },
    ]

    return chat_ollama(messages, model=model, temperature=0.1)


def chat_with_patent(
    question,
    patent_text,
    history=None,
    model="llama3:8b",
    retrieved_chunks=None,
):
    history = history or []
    if retrieved_chunks is None:
        fallback_chunks = chunk_text(patent_text)
        relevant_chunks = fallback_chunks[:4]
    else:
        relevant_chunks = retrieved_chunks

    context = "\n\n".join(
        [f"Excerpt {idx + 1}:\n{chunk}" for idx, chunk in enumerate(relevant_chunks)]
    )

    system_message = {
        "role": "system",
        "content": (
            "You are a patent assistant. Answer only using the provided patent excerpts. "
            "If the answer is not present in the excerpts, say you do not have enough context."
        ),
    }

    history_messages = []
    for item in history[-8:]:
        history_messages.append({"role": item["role"], "content": item["content"]})

    messages = [
        system_message,
        {
            "role": "user",
            "content": (
                f"Patent excerpts:\n{context}\n\n"
                f"Question: {question}\n"
                "Provide a concise answer and mention which excerpt numbers were used."
            ),
        },
    ]

    # Keep the latest interaction context after the system instruction.
    if history_messages:
        messages = [system_message] + history_messages + messages[1:]

    answer = chat_ollama(messages, model=model, temperature=0.0, top_p=0.85)
    return answer, relevant_chunks


def get_pdf_link(url):
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=options)
    try:
        driver.get(url)
        time.sleep(3)

        links = driver.find_elements(By.XPATH, "//a")
        for link in links:
            text = (link.text or "").lower()
            href = link.get_attribute("href") or ""
            if href and "pdf" in (text + href).lower():
                return href

        button = driver.find_element(By.XPATH, "//*[contains(translate(text(), 'pdf', 'PDF'), 'PDF')]")
        button.click()
        time.sleep(1)
        driver.switch_to.window(driver.window_handles[-1])
        return driver.current_url
    finally:
        driver.quit()