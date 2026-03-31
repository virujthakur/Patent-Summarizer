import hashlib
import json
import os
import re
import time
from pathlib import Path

import fitz  # PyMuPDF
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

DATA_ROOT = Path("data") / "patents"


def normalize_url(url):
    return str(url).strip()


def patent_id_from_url(url):
    digest = hashlib.sha1(normalize_url(url).encode("utf-8")).hexdigest()[:12]
    return f"pat_{digest}"


def get_patent_dir(patent_id):
    patent_dir = DATA_ROOT / patent_id
    patent_dir.mkdir(parents=True, exist_ok=True)
    return patent_dir


def patent_paths(patent_id):
    patent_dir = get_patent_dir(patent_id)
    return {
        "dir": str(patent_dir),
        "pdf": str(patent_dir / "document.pdf"),
        "text": str(patent_dir / "document.txt"),
        "summary": str(patent_dir / "summary.txt"),
        "chunks": str(patent_dir / "chunks.json"),
        "index": str(patent_dir / "index.json"),
        "meta": str(patent_dir / "metadata.json"),
    }


def save_text_file(path, content):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def read_text_file(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def download_pdf(url, filename):
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    with open(filename, "wb") as handle:
        handle.write(response.content)


def extract_text(pdf_path):
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


def _simple_embed(text):
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    vec = {}
    for token in tokens:
        vec[token] = vec.get(token, 0.0) + 1.0
    return vec


def _cosine_sparse(a_vec, b_vec):
    if not a_vec or not b_vec:
        return 0.0
    dot = 0.0
    for token, a_val in a_vec.items():
        dot += a_val * b_vec.get(token, 0.0)
    a_norm = sum(v * v for v in a_vec.values()) ** 0.5
    b_norm = sum(v * v for v in b_vec.values()) ** 0.5
    if a_norm == 0.0 or b_norm == 0.0:
        return 0.0
    return dot / (a_norm * b_norm)


def build_retrieval_index(text, index_path, chunks_path):
    chunks = chunk_text(text)
    embeddings = [_simple_embed(chunk) for chunk in chunks]
    with open(chunks_path, "w", encoding="utf-8") as handle:
        json.dump(chunks, handle, ensure_ascii=True, indent=2)
    with open(index_path, "w", encoding="utf-8") as handle:
        json.dump(embeddings, handle, ensure_ascii=True)
    return chunks, embeddings


def ensure_retrieval_index(text, index_path, chunks_path):
    if os.path.exists(index_path) and os.path.exists(chunks_path):
        with open(chunks_path, "r", encoding="utf-8") as handle:
            chunks = json.load(handle)
        with open(index_path, "r", encoding="utf-8") as handle:
            embeddings = json.load(handle)
        return chunks, embeddings
    return build_retrieval_index(text, index_path, chunks_path)


def retrieve_chunks(question, chunks, embeddings, top_k=4):
    query_vec = _simple_embed(question)
    scored = []
    for idx, emb in enumerate(embeddings):
        scored.append((idx, _cosine_sparse(query_vec, emb)))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    selected = [chunks[idx] for idx, score in scored[:top_k] if score > 0]
    if not selected:
        selected = chunks[: min(top_k, len(chunks))]
    return selected


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


def chat_with_patent(question, patent_text, index_path, chunks_path, history=None, model="llama3:8b"):
    history = history or []
    chunks, embeddings = ensure_retrieval_index(patent_text, index_path, chunks_path)
    relevant_chunks = retrieve_chunks(question, chunks, embeddings, top_k=4)

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