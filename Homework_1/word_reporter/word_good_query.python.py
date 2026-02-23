# word_good_query.python.py
# Merriam-Webster Collegiate Dictionary API: single-word lookup with documented query and results.

# STAGE 1: DESIGN QUERY
# API name:     Merriam-Webster Collegiate Dictionary API (dictionaryapi.com)
# Endpoint:     https://www.dictionaryapi.com/api/v3/references/collegiate/json/{word}
# Query type:   Single-word lookup returning pronunciations, definitions, and optional audio.
#
# Planned parameters:
#   - key:  Required; loaded from word.env (WORD_PRONOUNCER_API_KEY).
#   - word: Path parameter; the word to look up (e.g. "pronunciation").


import os
import sys
import requests
from dotenv import load_dotenv

if os.path.exists("word.env"):
    load_dotenv("word.env")
elif os.path.exists("../word.env"):
    load_dotenv("../word.env")
else:
    print("word.env not found. Set WORD_PRONOUNCER_API_KEY in word.env or in your environment.")

API_KEY = (os.getenv("WORD_PRONOUNCER_API_KEY") or "").strip()
BASE_URL = "https://www.dictionaryapi.com/api/v3/references/collegiate/json"

# STAGE 2: IMPLEMENT QUERY

# Word to query: from command line or default
word = (sys.argv[1] if len(sys.argv) > 1 else "pronunciation").strip()
if not word:
    word = "pronunciation"

encoded_word = requests.utils.quote(word, safe="")
url = f"{BASE_URL}/{encoded_word}"
params = {"key": API_KEY}

try:
    response = requests.get(url, params=params, timeout=15)
except requests.RequestException as e:
    print("Request failed:", e)
    raise

if response.status_code == 401:
    print("HTTP 401: Invalid authentication credentials. Check WORD_PRONOUNCER_API_KEY in word.env.")
    response.raise_for_status()

if not response.ok:
    print("HTTP status:", response.status_code)
    print("Response text (first 500 chars):", (response.text[:500] if response.text else "(empty)"))
    response.raise_for_status()

data = response.json()

# If word not found, API returns a list of suggestion strings (not entry objects)
if isinstance(data, list) and data and isinstance(data[0], str):
    print("QUERY SUMMARY")
    print("  Status:", response.status_code, "| Word not found. Suggestions:", data[:10])
    print("  Try one of the suggested spellings.")
    sys.exit(0)

if not isinstance(data, list) or not data:
    print("No data returned.")
    sys.exit(0)

# STAGE 3: DOCUMENT RESULTS
# Expected data structure (Merriam-Webster Collegiate JSON):
#   - data is a list of entry objects.
#   - Each entry: meta (id, uuid, stems, ...), hwi (headword info: hw, prs), fl (part of speech), shortdef (list of strings), def (full), etc.
#   - hwi.prs = list of pronunciations: each has "mw" (phonetic) and optionally "sound" (audio file id).
#   - shortdef = short definition strings for quick display.

entries = data
num_entries = len(entries)
first = entries[0]


def _pronunciation_list(entry, max_items=5):
    """Extract pronunciation strings from entry."""
    hwi = entry.get("hwi") or {}
    prs = hwi.get("prs") or []
    return [pr.get("mw", "").strip() for pr in prs[:max_items] if (pr.get("mw") or "").strip()]


def _shortdef_list(entry, max_items=5):
    """Extract short definitions from entry."""
    shortdef = entry.get("shortdef") or []
    return [d if isinstance(d, str) else str(d) for d in shortdef[:max_items]]


# --- Summary (compact) ---
print("QUERY SUMMARY")
print("  Status:", response.status_code, "| Word:", word, "| Entries returned:", num_entries)
print("")

# --- Table: pronunciations and definitions for first entry ---
prons = _pronunciation_list(first)
shortdefs = _shortdef_list(first)
fl = (first.get("fl") or "").strip()

print("FIRST ENTRY (headword)")
print("  part of speech:", fl or "—")
print("  pronunciations:", prons if prons else "—")
print("  short definitions:")
for i, d in enumerate(shortdefs, 1):
    print(f"    {i}. {d[:80]}{'...' if len(d) > 80 else ''}")
print("")

# --- One example record (key fields only, compact) ---
print("EXAMPLE RECORD (raw keys)")
print("  meta.id:", first.get("meta", {}).get("id"))
print("  hwi.hw:", (first.get("hwi") or {}).get("hw"))
print("  hwi.prs count:", len((first.get("hwi") or {}).get("prs") or []))
print("  fl:", first.get("fl"))
print("  shortdef count:", len(first.get("shortdef") or []))
print("")
print("✅ Done.")
