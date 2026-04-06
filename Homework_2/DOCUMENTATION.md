# Word Pronunciation Reporter
## Multi-Agent + RAG + Function Calling Documentation

This system is an AI-powered reporting pipeline for vocabulary learning. You provide a target word, and the software gathers dictionary evidence, retrieves supporting learning notes, and produces a final learner-friendly report. The design combines three capabilities in one flow: multi-agent orchestration (different agents for retrieval, analysis, and reporting), RAG (retrieving local context from CSV and a local word bank), and tool/function calling (agent-triggered Python functions).

The core architecture is a 3-agent workflow in `Homework_2/word_multiagent_rag.py`. Agent 1 is the evidence collector and is instructed to call tools. Agent 2 is the learning analyst that transforms evidence into structured insights. Agent 3 is the final reporter that converts the analysis into polished markdown output for learners. This split keeps each step focused and makes debugging easier because you can inspect tool outputs, analysis text, and final report separately.

The system is retrieval-first by design. It prefers grounded evidence from tools before generating narrative content. To reduce instability from smaller local models, the workflow enforces minimum tool coverage (if a tool is missed, it runs it directly), deduplicates repeated tool calls, and passes a clean evidence packet to downstream agents.

---

## 1) System Architecture

### Agent Roles
- **Agent 1: Retrieval and Evidence Collector**
  - Purpose: gather all raw evidence for a target word.
  - Method: uses function calling with the `TOOLS` metadata.
  - Output: tool call outputs (dictionary JSON, pronunciation-note retrieval JSON, related-word retrieval JSON).

- **Agent 2: Learning Analyst**
  - Purpose: convert raw evidence into structured educational analysis.
  - Required sections:
    - Pronunciation Challenges
    - Meaning Snapshot
    - Related Vocabulary
    - Teaching Strategy
  - Constraint: should use provided evidence only.

- **Agent 3: AI Reporter**
  - Purpose: transform Agent 2 analysis into a learner-facing final report.
  - Required sections:
    1. Title
    2. Quick Summary
    3. Pronunciation Coaching
    4. Related Words to Practice
    5. Mini Study Plan

### Workflow Sequence
1. User provides a target word (CLI arg).
2. Agent 1 runs with tools enabled (`agent_run(..., tools=TOOLS, output="tools")`).
3. Tool outputs are normalized into a single evidence packet.
4. Agent 2 analyzes the evidence packet.
5. Agent 3 generates the final report from Agent 2 analysis (+ evidence as backup context).

---

## 2) RAG Data Source

The system uses two local retrieval sources:

- **CSV learning notes**: `rag_learning_notes.csv`
  - Used by `search_pronunciation_notes(query, top_k=5)`.
  - Retrieval method: keyword-overlap scoring across columns such as `pattern`, `keywords`, `when_to_use`, `memory_tip`, and `example_words`.
  - Return format: JSON list of matched rows with relevance score.
  - Behavior when no match: returns `[]` (empty evidence) to avoid injecting unrelated tips.

- **Local word bank**: provided by `word_list.get_all_words()`
  - Used by `search_local_word_bank(query, top_k=10)`.
  - Retrieval method: fuzzy match (`difflib.get_close_matches`) + prefix and length heuristics.
  - Return format: JSON list of related words with relationship labels (e.g., `spelling-similar`, `prefix/length-neighbor`).

---

## 3) Tool Functions

### `fetch_word_lookup`
- **Purpose**: fetch dictionary evidence for one word.
- **Parameters**:
  - `word` (string): target word.
- **Returns**: JSON string with:
  - `ok`, `word`, `pronunciations`, `definitions`, `audio_count`
  - or `{ "ok": false, "error": ... }`.

### `search_pronunciation_notes`
- **Purpose**: RAG retrieval from pronunciation-learning CSV notes.
- **Parameters**:
  - `query` (string): retrieval query (typically the target word).
  - `top_k` (integer, default `5`): max rows to return.
- **Returns**: JSON string list of relevant notes with scores.

### `search_local_word_bank`
- **Purpose**: retrieve lexical neighbors for compare-and-contrast learning.
- **Parameters**:
  - `query` (string): target word.
  - `top_k` (integer, default `10`): max related words.
- **Returns**: JSON string list of related words and relationship type.

### Tool Metadata
- Tool schemas are defined in `TOOLS` (OpenAI/Ollama style function metadata).
- Agent 1 uses these schemas to decide which functions to call and what arguments to pass.

---

## 4) Technical Details

### Runtime and Model
- Uses local Ollama chat endpoint through shared helper `agent_run` in `functions.py`.
- Default model resolves from `OLLAMA_MODEL` env var, fallback from `DEFAULT_MODEL`.
- Expected local endpoint: `http://localhost:11434`.

### API and Keys
- Dictionary lookup uses `api_client.get_word_data(...)`.
- `api_client` expects dictionary API configuration via env file(s), commonly:
  - `word.env`
  - `.env`
- If your API client includes fallback logic, the workflow still functions without primary API success.

### Python Packages
Install at least:
- `pandas`
- `requests`
- `python-dotenv`

(If you use the UI/report export pieces in related modules, also keep your full `Homework_1/word_reporter/requirements.txt` set.)

### File Structure Notes
Current `Homework_2/word_multiagent_rag.py` imports:
- `from api_client import get_word_data`
- `from functions import DEFAULT_MODEL, agent_run`
- `from word_list import get_all_words`

So `api_client.py`, `functions.py`, and `word_list.py` must be importable from your Python path (same folder or parent path). If they are still in `Homework_1/word_reporter`, either copy them into `Homework_2` or run with an adjusted `PYTHONPATH`.

---

## 5) Usage Instructions (Easy Setup)

### Step A: Open project root
```bash
cd /Users/williammanno/Documents/GitHub/sysen5381dsai
```

### Step B: Create/activate Python environment
```bash
python -m venv .venv
source .venv/bin/activate
```

### Step C: Install dependencies
If you want to reuse your existing requirements:
```bash
pip install -r Homework_1/word_reporter/requirements.txt
```
Or minimum set:
```bash
pip install pandas requests python-dotenv
```

### Step D: Configure API keys and model
1. Ensure Ollama is running:
```bash
ollama serve
```
2. Ensure your model exists (example):
```bash
ollama pull smollm2:1.7b
```
3. Add env values (in `word.env` or `.env`), for example:
```bash
OLLAMA_MODEL=smollm2:1.7b
WORD_PRONOUNCER_API_KEY=your_key_here
```

### Step E: Ensure shared modules are visible
If `Homework_2` does not contain `api_client.py`, `functions.py`, and `word_list.py`, either:
- copy them from `Homework_1/word_reporter`, or
- run with:
```bash
export PYTHONPATH="$PYTHONPATH:/Users/williammanno/Documents/GitHub/sysen5381dsai/Homework_1/word_reporter"
```

### Step F: Run the system
```bash
python Homework_2/word_multiagent_rag.py hello
```
or
```bash
cd Homework_2
python word_multiagent_rag.py pronunciation
```

### Step G: Validate function-calling occurred
In console output, confirm:
- `[Agent 1] Tool names called: ['fetch_word_lookup', 'search_pronunciation_notes', 'search_local_word_bank']`

If you see those tool names, your multi-agent + RAG + tool-calling pipeline is active.

---

## 6) Common Troubleshooting

- **Import error for `api_client` / `functions` / `word_list`**:
  - Fix `PYTHONPATH` or copy shared files into `Homework_2`.
- **Ollama connection errors**:
  - Start Ollama (`ollama serve`) and verify the model is pulled.
- **Empty RAG note results (`[]`)**:
  - This means no CSV rows matched the query; system continues with other evidence.
- **Weak model outputs**:
  - Try a stronger local model and keep the same workflow.

This documentation is intended to be practical and assignment-ready while remaining easy to run and extend.
