# AI-Powered Word Pronunciation Reporter

Shiny for Python app that:

- **API integration**: Looks up words using the **Merriam-Webster Collegiate Dictionary API** (pronunciations and definitions). Uses `WORD_PRONOUNCER_API_KEY` from `word.env`.
- **Web interface**: Sidebar to enter a word, main area shows pronunciations and definitions.
- **AI reporting**: Uses **Ollama** (local or cloud) to generate an AI summary and writes it into a **Word document (.docx)** that you download. Structured data from the API → Ollama → narrative report.

## Setup

1. **API key**  
   Put your **Merriam-Webster** Collegiate Dictionary API key in `word.env` in the parent folder (`Homework 1/word.env`). Get a key at [dictionaryapi.com](https://dictionaryapi.com/register/index).

   ```
   WORD_PRONOUNCER_API_KEY=your-merriam-webster-api-key
   ```

2. **Python env**  
   From this directory:

   ```bash
   pip install -r requirements.txt
   ```

3. **Ollama (for AI report in docx)**  
   Add `ollama.env` (same folder as `word.env` or this directory) with your Ollama Cloud API key:

   ```
   OLLAMA_API_KEY=your-ollama-cloud-api-key
   ```

   Optional: `OLLAMA_MODEL=gemma3:latest`, `OLLAMA_TIMEOUT=300`.  
   If `OLLAMA_API_KEY` is not set, the app uses **local Ollama** (`ollama serve`, then e.g. `ollama pull gemma3:latest`).

## Run the app

From the repo root or `Homework 1`:

```bash
cd "Homework 1/word_reporter"
shiny run app.py
```

Or from `Homework 1`:

```bash
shiny run word_reporter/app.py
```

Then open the URL shown in the terminal (e.g. http://127.0.0.1:8000).

## Usage

1. Enter a word in the sidebar and click **Look up word**.
2. View pronunciations (phonetic spellings) and definitions in the main panel.
3. Click **Download AI report (.docx)** to get a Word document containing the word data and an Ollama-generated AI summary (pronunciation tips, meanings, follow-up suggestion). The first time you download, generation may take a minute while Ollama runs.

## Command-line scripts (query API + AI report)

- **word_good_query.python.py** — Query the Merriam-Webster API for one word (design query, implement request, document results). Run: `python word_good_query.python.py` (default word: "pronunciation") or `python word_good_query.python.py vocabulary`.
- **word_trends.py** — Query the API for several words, aggregate (part-of-speech, pronunciation counts, audio), build a summary for the LLM, call Ollama (local or cloud) to get a narrative report, then print the AI summary and fallback stats. Run: `python word_trends.py`. Requires `word.env` for the API; use `ollama.env` for Ollama Cloud or local Ollama.

## Files

- `app.py` — Shiny UI and server.
- `api_client.py` — Merriam-Webster API client; loads `word.env`, fetches pronunciations and definitions (falls back to Free Dictionary API if no key or on auth error).
- `ollama_client.py` — Loads `ollama.env` (and word.env, .env); calls Ollama (Cloud if `OLLAMA_API_KEY` set, else local) and builds the docx report (data + AI summary).
- `word_good_query.python.py` — Standalone script: query one word, document response.
- `word_trends.py` — Standalone script: query multiple words, aggregate, Ollama report.
- `requirements.txt` — Python dependencies.
