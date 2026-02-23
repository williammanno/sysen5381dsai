# AI-Powered Word Pronunciation Reporter

Shiny for Python app that:

- **API integration**: Looks up words using the **Merriam-Webster Collegiate Dictionary API** (pronunciations and definitions). Uses `WORD_PRONOUNCER_API_KEY` from `word.env`.
- **Web interface**: Sidebar to enter a word, main area shows pronunciations and definitions.
- **AI reporting**: Uses **Ollama** (local or cloud) to generate short pronunciation and usage reports from the fetched data.

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

3. **Ollama (for AI summaries)**  
   - **Local**: Install [Ollama](https://ollama.com), run `ollama serve`, and pull a model (e.g. `ollama pull llama3.2:3b`). Optional: set `OLLAMA_MODEL` and `OLLAMA_TIMEOUT` in `word.env` or `.env`.
   - **Cloud**: Set `OLLAMA_API_KEY` in `.env` to use Ollama Cloud instead.

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
3. Click **Generate AI summary** to get an Ollama-generated short report with pronunciation tips and usage.

## Files

- `app.py` — Shiny UI and server.
- `api_client.py` — Merriam-Webster API client; loads `word.env`, fetches pronunciations and definitions (falls back to Free Dictionary API if no key or on auth error).
- `ollama_client.py` — Calls local Ollama or Ollama Cloud to generate the AI report.
- `requirements.txt` — Python dependencies.
