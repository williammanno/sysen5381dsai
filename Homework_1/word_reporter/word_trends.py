# word_trends.py
# Word API data: fetch multiple words, aggregate, and use Ollama to summarize.
# Builds on word_good_query.python.py.

import json
import os
import requests
from collections import defaultdict
from dotenv import load_dotenv

# --- Load env (word API + optional Ollama Cloud) ---
if os.path.exists("word.env"):
    load_dotenv("word.env")
elif os.path.exists("../word.env"):
    load_dotenv("../word.env")
else:
    print("word.env not found. Set WORD_PRONOUNCER_API_KEY in word.env or in your environment.")

if os.path.exists("ollama.env"):
    load_dotenv("ollama.env")
elif os.path.exists("../ollama.env"):
    load_dotenv("../ollama.env")
load_dotenv()

# Use api_client for consistent MW + fallback behavior
from api_client import get_word_data

WORD_PRONOUNCER_API_KEY = os.getenv("WORD_PRONOUNCER_API_KEY")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")

# --- 1. Fetch word data (multiple words) ---

# Words to query (can be expanded or read from a file)
WORDS_TO_QUERY = [
    "pronunciation", "definition", "language", "vocabulary", "dictionary",
    "example", "sentence", "grammar", "phonetic", "syllable",
]

results = []
for word in WORDS_TO_QUERY:
    res = get_word_data(word)
    if res.get("ok"):
        results.append(res)
    else:
        print(f"  Skip '{word}': {res.get('error', 'unknown')}")

if not results:
    print("No word data returned. Cannot build report.")
    exit(0)

# --- 2. Extract and aggregate ---

part_of_speech_counts = defaultdict(int)
pronunciation_counts = []
words_with_audio = 0
definition_counts = []
word_list = []

for r in results:
    word = r.get("word", "")
    word_list.append(word)
    prons = r.get("pronunciations", [])
    defs = r.get("definitions", [])
    audio = r.get("audio", [])
    pronunciation_counts.append(len(prons))
    definition_counts.append(len(defs))
    if audio:
        words_with_audio += 1
    for d in defs:
        pos = (d.get("partOfSpeech") or "").strip()
        if pos:
            part_of_speech_counts[pos] += 1

# Top parts of speech, words by pron count, etc.
top_pos = sorted(part_of_speech_counts.items(), key=lambda x: -x[1])[:10]
words_by_prons = sorted(
    [(r.get("word"), len(r.get("pronunciations", []))) for r in results],
    key=lambda x: -x[1],
)[:10]

# --- 3. Build a short summary for the LLM (fewer tokens = faster, less timeout) ---

summary_for_llm = {
    "total_words_queried": len(results),
    "words": word_list,
    "part_of_speech_distribution": [{"pos": pos, "count": c} for pos, c in top_pos],
    "pronunciation_counts_per_word": [{"word": w, "pron_count": c} for w, c in words_by_prons],
    "words_with_audio": words_with_audio,
    "total_pronunciations": sum(pronunciation_counts),
    "total_definitions": sum(definition_counts),
    "sample_definitions": [],
}
# Add one sample definition per word (first def only)
for r in results[:5]:
    defs = r.get("definitions", [])
    if defs:
        d = defs[0]
        summary_for_llm["sample_definitions"].append({
            "word": r.get("word"),
            "partOfSpeech": d.get("partOfSpeech"),
            "text": (d.get("text") or "")[:100],
        })

summary_text = json.dumps(summary_for_llm, indent=2)

# --- 4. Call Ollama (local or cloud) to get narrative summary ---

SYSTEM_PROMPT = """You are a data analyst. Summarize the dictionary/word API query results using bullet points. Include:
- What words were looked up and how many had pronunciations and definitions
- Part-of-speech distribution (nouns, verbs, etc.) if present
- Note on which words have audio pronunciation available
- One or two observations about the data (e.g., common patterns, useful for learners)
- One follow-up suggestion (e.g., try more words, focus on a part of speech)
Be concise; use numbers. Format as bullet points for easy reading."""

USER_PROMPT = f"Word API query summary ({len(results)} words):\n\n{summary_text}\n\nWrite a brief report in bullet points."

print("\n🚀 Fetching word data and asking Ollama for report...\n")

output = None
llm_response = None

if OLLAMA_API_KEY:
    print("Using Ollama Cloud (OLLAMA_API_KEY is set).")
    url = "https://ollama.com/api/chat"
    headers = {
        "Authorization": f"Bearer {OLLAMA_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": "gpt-oss:20b-cloud",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT},
        ],
        "stream": False,
    }
    try:
        llm_response = requests.post(url, headers=headers, json=body, timeout=120)
        llm_response.raise_for_status()
        output = llm_response.json()["message"]["content"]
    except requests.RequestException as e:
        print("Ollama Cloud request failed:", e)
        if llm_response is not None and getattr(llm_response, "text", None):
            print("Response body:", llm_response.text[:500])
        output = None
else:
    LOCAL_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:latest")
    print(f"Using local Ollama (model: {LOCAL_MODEL}).")
    PORT = 11434
    url = f"http://localhost:{PORT}/api/generate"
    body = {
        "model": LOCAL_MODEL,
        "prompt": f"{SYSTEM_PROMPT}\n\n---\n\n{USER_PROMPT}",
        "stream": False,
    }
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))
    try:
        llm_response = requests.post(url, json=body, timeout=OLLAMA_TIMEOUT)
        llm_response.raise_for_status()
        output = llm_response.json().get("response", "")
    except requests.ConnectionError as e:
        print("Local Ollama connection failed. Is Ollama running?")
        print("  → Start it with: ollama serve")
        print("  → Then pull a model: ollama pull gemma3:latest")
        print("  Error:", e)
        output = None
    except requests.Timeout as e:
        print("Local Ollama timed out (model too slow or still loading).")
        print("  → Use a smaller/faster model: set OLLAMA_MODEL=llama3.2:3b in ollama.env")
        print("  → Or increase wait: set OLLAMA_TIMEOUT=600 in ollama.env")
        print("  Error:", e)
        output = None
    except requests.RequestException as e:
        print("Local Ollama request failed:", e)
        if llm_response is not None:
            try:
                err = llm_response.json()
                if "error" in err:
                    print("  Model error:", err["error"])
            except Exception:
                if getattr(llm_response, "text", None):
                    print("  Response:", llm_response.text[:300])
        if "404" in str(e):
            print("  → If Ollama is running, try: ollama pull gemma3:latest")
        print("  → Or set OLLAMA_MODEL=llama3.2:3b (smaller, faster) in ollama.env")
        output = None

# --- 5. Print results ---

print("=" * 60)
print("WORD API QUERY REPORT")
print("(Based on", len(results), "words from Merriam-Webster Collegiate / fallback API)")
print("=" * 60)

if output:
    print("\n📝 OLLAMA SUMMARY (AI report on query data)\n")
    print(output)
    print("\n" + "=" * 60)
else:
    print("\n⚠️ Could not get Ollama summary. Showing aggregated stats only.\n")
    print("📚 WORDS QUERIED")
    print("-" * 40)
    print("  " + ", ".join(word_list))
    print("\n📊 PART OF SPEECH (count)")
    print("-" * 40)
    for pos, count in top_pos:
        print(f"  • {pos}: {count}")
    print("\n🔤 PRONUNCIATIONS PER WORD (top 10)")
    print("-" * 40)
    for w, c in words_by_prons:
        print(f"  • {w}: {c}")
    print("\n📋 SUMMARY")
    print("-" * 40)
    print(f"  • Words with data: {len(results)}")
    print(f"  • Total pronunciations: {sum(pronunciation_counts)}")
    print(f"  • Total definitions: {sum(definition_counts)}")
    print(f"  • Words with audio: {words_with_audio}")
    print("=" * 60)

print("\n✅ Done.\n")
