# Patent Studio

A beautiful, locally-hosted patent analysis and Q&A application built with Streamlit and Ollama. Upload patent links from Excel, download full documents, auto-summarize them, and chat with individual patents using retrieval-augmented generation (RAG).

## Features

- **📊 Excel Batch Ingestion**: Upload an Excel file with a list of patent URLs (requires `url` column)
- **📥 Auto-Download & Extract**: Automatically fetch PDF documents from patent links and extract full text
- **✨ AI Summarization**: Generate concise patent summaries using local Ollama LLM (supports any Ollama model)
- **💬 Patent Q&A Chat**: Ask questions about individual patents; responses are grounded in the patent text using semantic retrieval
- **📁 Local Storage**: All downloaded PDFs, extracted text, and indexes stored locally in `data/patents/` folder
- **⬇️ Export Options**: Download summaries as CSV or all PDFs as ZIP archive
- **🎨 Beautiful UI**: Modern gradient background, top navigation, tabbed patent workspace
- **🔄 Patent Switching**: Easy dropdown navigation between processed patents
- **🚫 No Sidebar**: Clean interface with top navigation bar and prominent back button

## Project Structure

```
Patent Summarizer/
├── app.py                      # Main Streamlit app (upload, process, view results)
├── functions.py               # Core utilities (download, extract, summarize, chat, retrieval)
├── pages/
│   └── patent_viewer.py      # Patent workspace (PDF, Summary, Chat tabs)
├── .streamlit/
│   └── config.toml           # Streamlit configuration
├── data/
│   └── patents/              # Local storage for processed patents
│       └── pat_[hash]/       # Per-patent folder
│           ├── document.pdf
│           ├── document.txt
│           ├── summary.txt
│           ├── chunks.json
│           └── index.json
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Installation

### Prerequisites

- **Python 3.9+** (this project uses 3.13.12)
- **Ollama** installed and running locally on `localhost:11434`
  - Download from: https://ollama.ai
  - Default model: `llama3:8b` (see configuration below)

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd "Patent Summarizer"
   ```

2. **Create and activate a Python virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Ollama (optional):**
   - The app uses `llama3:8b` by default
   - To use a different model, change the default in the UI or modify `functions.py`
   - Ensure your chosen model is pulled: `ollama pull <model-name>`

5. **Start Ollama** (in a separate terminal):
   ```bash
   ollama serve
   ```

6. **Run the app:**
   ```bash
   streamlit run app.py
   ```
   The app will open at `http://localhost:8501`

## Usage

### Step 1: Upload Patents

1. Go to the main **Patent Studio** page
2. Upload an Excel file with a `url` column containing patent links
3. (Optional) Change Ollama model name
4. (Optional) Check "Reprocess existing" to re-download/re-summarize existing patents
5. Click **Process Patents**

**Example Excel structure:**
```
| url                                              |
|--------------------------------------------------|
| https://patents.google.com/patent/US10000001B2  |
| https://patents.google.com/patent/US10000002B2  |
```

### Step 2: View Processing Results

- ✅ Successful patents appear in the "Processed Patents" list with status (cached/done)
- ❌ Failed URLs are shown in the "Failed URLs" table with error messages
- Download summaries as CSV or all PDFs as ZIP

### Step 3: Open Patent Workspace

1. Click **Open** next to any patent in the list
2. In the patent workspace, use the **top navigation** dropdown to switch between patents
3. Three tabs available:
   - **PDF**: View the full patent document
   - **Summary**: Read the AI-generated summary
   - **Chat**: Ask questions about the patent

### Step 4: Chat with Patents

1. Go to the **Chat** tab
2. Type a question (e.g., "What problem does this patent solve?")
3. The system retrieves relevant patent excerpts and uses Ollama to generate an answer
4. You can expand "Retrieved context" to see which excerpts were used
5. Click **Clear chat** to reset conversation for the current patent

## Architecture

### Data Flow

```
Excel Upload
    ↓
URL Normalization & Deduplication
    ↓
Patent Link Extraction (Selenium)
    ↓
PDF Download & Local Storage
    ↓
Text Extraction (PyMuPDF)
    ↓
AI Summarization (Ollama)
    ↓
Persistent Local Artifacts
```

### Chat/Retrieval Pipeline

```
User Question
    ↓
Text Chunking (with overlap)
    ↓
Sparse Vector Embedding (token-based)
    ↓
Semantic Retrieval (top-4 chunks)
    ↓
Prompt Composition (system + context + history)
    ↓
Ollama LLM Response
```

### Key Functions

**[functions.py](functions.py)**
- `download_pdf(url, filename)` - Download PDF from URL
- `extract_text(pdf_path)` - Extract text using PyMuPDF
- `summarize_text(text, model)` - Generate summary via Ollama
- `chunk_text(text, chunk_size, overlap)` - Split text into overlapping chunks
- `ensure_retrieval_index(text, index_path, chunks_path)` - Build or load semantic index
- `retrieve_chunks(question, chunks, embeddings, top_k)` - Find relevant chunks
- `chat_with_patent(question, patent_text, ...)` - Full RAG chat flow
- `get_pdf_link(url)` - Extract PDF link from patent page (Selenium)

**[app.py](app.py)**
- `check_ollama()` - Health check for Ollama connectivity
- `parse_urls_from_excel(file_obj)` - Validate and normalize Excel input
- `process_patent_url(url, model_name, force_reprocess)` - Single patent pipeline
- `create_pdf_zip(results)` - Export PDFs as ZIP

**[pages/patent_viewer.py](pages/patent_viewer.py)**
- Top navigation (back button, patent dropdown, model selector)
- PDF viewing (native Streamlit PDF viewer)
- Summary display
- Chat interface with per-patent history

## Configuration

### Ollama Model

Change the default model in the UI on the main page, or modify in [functions.py](functions.py):

```python
def summarize_text(text, model="llama3:8b"):  # Change here
    ...
```

Available models: https://ollama.ai/library

### Streamlit Settings

[.streamlit/config.toml](.streamlit/config.toml):
```toml
[client]
toolbarMode = "minimal"
```

This hides the Streamlit toolbar and Deploy button for a cleaner UI.

### Temperature & Parameters

- **Summarization**: `temperature=0.1` (factual, concise)
- **Chat**: `temperature=0.0` (precise Q&A), `top_p=0.85` (focused output)

## Local Storage

All artifacts are stored in `data/patents/{patent_id}/`:
- `document.pdf` - Original PDF file
- `document.txt` - Extracted patent text
- `summary.txt` - AI-generated summary
- `chunks.json` - Text chunks for retrieval
- `index.json` - Sparse vector embeddings
- `metadata.json` - Processing metadata (if added in future)

Patent IDs are deterministic (SHA1 hash of URL), so re-running with the same patents reuses cached artifacts.

## Troubleshooting

### "Ollama is not reachable at localhost:11434"
- Ensure Ollama is running: `ollama serve` in a separate terminal
- Check it's accessible: `curl http://localhost:11434/api/tags`

### "Excel must contain a 'url' column"
- Make sure your uploaded Excel file has a column named exactly `url`
- Whitespace and case-sensitivity matter

### PDF shows blank or doesn't load
- Refresh the page (Ctrl+R or Cmd+R)
- Check that the PDF file exists locally in `data/patents/{patent_id}/document.pdf`

### Chat responses are slow
- Ollama inference takes time (depends on model size and hardware)
- Look for the "Thinking over patent context..." spinner
- Consider using a smaller/faster model if available

### Sidebar appears on reload
- This should not happen with the latest build
- If it does, clear browser cache or hard refresh (Ctrl+Shift+R)

## Dependencies

| Package | Purpose |
|---------|---------|
| `streamlit` | Web UI framework |
| `streamlit[pdf]` | PDF rendering component |
| `pandas` | Excel/CSV data handling |
| `requests` | HTTP downloads |
| `pymupdf` | PDF text extraction |
| `openpyxl` | Excel backend |
| `selenium` | Browser automation for link extraction |

## Known Limitations

1. **Patent Link Extraction**: Selenium-based scraping is fragile; some patent sites may block or change structure
2. **Sparse Embeddings**: Uses token-overlap similarity, not semantic embeddings (no ML model needed locally, but less accurate than dense embeddings)
3. **Single-User**: No authentication; designed for local/personal use
4. **No Database**: Relies on file storage; metadata not indexed
5. **Token Limits**: Very large patents may exceed Ollama's context window

## Future Enhancements

- [ ] Support for dense embeddings (sentence-transformers)
- [ ] Patent database/SQLite storage for metadata queries
- [ ] Batch comparison across multiple patents
- [ ] Export chat conversations
- [ ] Multi-user authentication
- [ ] Cloud Ollama support
- [ ] REST API for programmatic access

## License

[Specify your license here, e.g., MIT, Apache 2.0]

## Contributing

Contributions welcome! Please:
1. Test locally before submitting
2. Follow PEP 8 style guidelines
3. Update README for new features
4. Add error handling and validation

## Support

For issues or questions:
- Check the [Troubleshooting](#troubleshooting) section
- Review Ollama docs: https://ollama.ai/docs
- Check Streamlit docs: https://docs.streamlit.io

---

**Built with ❤️ using Streamlit + Ollama**
