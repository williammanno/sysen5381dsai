# Word Pronunciation Reporter — Documentation

Brief documentation for the tool, API data summary, technical details, and usage instructions.

---

## Documentation (Tool Overview)

**Word Pronunciation Reporter** is a Shiny for Python app and set of scripts that:

- **Query a dictionary API** (Merriam-Webster Collegiate) to fetch pronunciations, definitions, and optional audio for English words.
- **Provide a web interface** to look up words, filter a word list by letter and length, pick random words, and listen to pronunciations.
- **Generate AI reports** via Ollama (local or cloud): you can download a Word document (.docx) containing the word data plus an AI-written summary (pronunciation tips, meanings, follow-up suggestion).

The tool also includes **standalone scripts** to query the API and produce AI summaries from the command line, without opening the app.

---

## Data Summary (API Data)

The app and scripts use a **normalized** shape for each word lookup. The table below describes the main fields returned by the API client (and used in the app).

### Top-level response (one word lookup)

| Column / field   | Data type | Description |
|------------------|-----------|-------------|
| `ok`             | boolean   | Whether the lookup succeeded. |
| `error`          | string    | Error message if `ok` is false (e.g. "No word provided.", "Invalid authentication credentials"). |
| `word`           | string    | The word that was looked up. |
| `pronunciations` | array     | List of pronunciation objects (see below). |
| `definitions`    | array     | List of definition objects (see below). |
| `audio`          | array     | List of audio objects with `fileUrl` (MP3 URL for playback). |
| `fetched_at`     | string    | Timestamp when data was fetched (e.g. "2025-02-22 14:30"). |

### Each item in `pronunciations`

| Column / field | Data type | Description |
|----------------|-----------|-------------|
| `raw`          | string    | Phonetic spelling (e.g. Merriam-Webster symbols or IPA). |
| `rawType`      | string    | Source or style (e.g. "Merriam-Webster", "syllables", "IPA"). |
| `seq`          | integer   | Order index of this pronunciation. |

### Each item in `definitions`

| Column / field  | Data type | Description |
|-----------------|-----------|-------------|
| `partOfSpeech`  | string    | Part of speech (e.g. "noun", "verb"). |
| `text`          | string    | Definition text. |

### Each item in `audio`

| Column / field | Data type | Description |
|----------------|-----------|-------------|
| `fileUrl`      | string    | URL of the pronunciation audio file (MP3). |

---

## Technical Details

### API keys

| Purpose              | Variable name               | Where to set it   |
|----------------------|-----------------------------|--------------------|
| Dictionary lookups   | `WORD_PRONOUNCER_API_KEY`   | `word.env` or `.env` |
| Ollama Cloud (optional) | `OLLAMA_API_KEY`        | `ollama.env` or `.env` |
| Local Ollama (optional) | `OLLAMA_MODEL`          | `ollama.env` or `.env` (default: `gemma3:latest`) |
| Local Ollama timeout | `OLLAMA_TIMEOUT`            | `ollama.env` or `.env` (default: `300` seconds) |

### API endpoints

| Purpose                    | Endpoint |
|----------------------------|----------|
| Merriam-Webster Collegiate | `https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}?key=YOUR_KEY` |
| Fallback (no key / on 401) | `https://api.dictionaryapi.dev/api/v2/entries/en/{word}` (no key) |
| Ollama Cloud (if key set)  | `https://ollama.com/api/chat` (POST, Bearer token) |
| Local Ollama               | `http://localhost:11434/api/generate` (POST) |

### Packages (from `requirements.txt`)

| Package        | Purpose |
|----------------|---------|
| `shiny`        | Web app (UI and server). |
| `pandas`       | Data handling (e.g. optional processing). |
| `requests`     | HTTP requests to dictionary and Ollama APIs. |
| `python-dotenv`| Load API keys from `word.env`, `ollama.env`, `.env`. |
| `python-docx`  | Generate Word (.docx) reports. |

### File structure

```
word_reporter/
├── app.py                      # Shiny app (UI + server)
├── api_client.py               # Dictionary API client (Merriam-Webster + fallback)
├── ollama_client.py            # Ollama client + docx report generation
├── word_list.py                # Word list for browse/filter/random
├── word_good_query.python.py   # Standalone: query one word, document response
├── word_trends.py              # Standalone: query multiple words, aggregate, Ollama report
├── requirements.txt            # Python dependencies
├── README.md                   # Project overview and quick start
└── DOCUMENTATION.md            # This file
```

**Environment files** (create in `word_reporter/` or parent folder):

- `word.env` — `WORD_PRONOUNCER_API_KEY=...` (Merriam-Webster key).
- `ollama.env` — `OLLAMA_API_KEY=...` (optional; for Ollama Cloud). Optional: `OLLAMA_MODEL`, `OLLAMA_TIMEOUT`.

---

## Usage Instructions

Follow these steps to install dependencies, set up API keys, and run the software.

### 1. Install dependencies

Open a terminal, go to the project folder, and install the required packages:

```bash
cd path/to/Homework_1/word_reporter
pip install -r requirements.txt
```

(Replace `path/to/Homework_1` with your actual path.)

### 2. Set up API keys

**Dictionary API (required for full features)**

1. Get a free API key from [dictionaryapi.com](https://dictionaryapi.com/register/index) (Merriam-Webster Collegiate).
2. Create a file named `word.env` in the `word_reporter` folder (or in the parent folder, e.g. `Homework_1`).
3. Add one line (no quotes, no spaces around `=`):

   ```
   WORD_PRONOUNCER_API_KEY=your-key-here
   ```

If you skip this, the app will use a free fallback API with fewer features.

**Ollama (optional, for AI report)**

- **Option A — Ollama Cloud:** Create `ollama.env` in the same place as `word.env` and add:
  ```
  OLLAMA_API_KEY=your-ollama-cloud-key
  ```
- **Option B — Local Ollama:** Install [Ollama](https://ollama.com), run `ollama serve`, then e.g. `ollama pull gemma3:latest`. No key needed; leave `OLLAMA_API_KEY` unset.

### 3. Run the app

From the `word_reporter` folder:

```bash
shiny run app.py
```

In the terminal you’ll see a URL (e.g. `http://127.0.0.1:8000`). Open that URL in your browser.

**In the app:**

1. Type a word and click **Look up word**, or use **Starting letter** / **Word length** and the word list, or click **Random word**.
2. View pronunciations and definitions; use the audio player if available.
3. **Save AI reports:** Use **Download full report (.docx)** for the complete report (word data + AI summary), or save the AI report only in multiple formats: **.txt**, **.md**, **.html**, or **.docx** (AI narrative only). The first save for a word may take a minute while Ollama runs; later formats for the same word use a cache.

### 4. Run the command-line scripts (optional)

From the `word_reporter` folder:

- **Query one word and print a short summary:**
  ```bash
  python word_good_query.python.py
  python word_good_query.python.py vocabulary
  ```

- **Query several words and print an AI report (and stats):**
  ```bash
  python word_trends.py
  ```

- **Generate a single-word docx report from the command line:**
  ```bash
  python ollama_client.py hello
  ```

All of these use `word.env` (and `ollama.env` for Ollama) from the current or parent directory.

---

## Quick reference

| Task                    | Command or action |
|-------------------------|-------------------|
| Install dependencies    | `pip install -r requirements.txt` |
| Run the Shiny app       | `shiny run app.py` then open the URL in a browser |
| Query one word (script) | `python word_good_query.python.py [word]` |
| Multi-word + AI report  | `python word_trends.py` |
| Single-word docx       | `python ollama_client.py [word]` |
| Dictionary API key      | In `word.env`: `WORD_PRONOUNCER_API_KEY=...` |
| Ollama Cloud key        | In `ollama.env`: `OLLAMA_API_KEY=...` |
