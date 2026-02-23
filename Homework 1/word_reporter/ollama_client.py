# ollama_client.py
# Call local Ollama (or Ollama Cloud if OLLAMA_API_KEY is set) to generate
# pronunciation/word insights. Pattern from 02_ollama.py and 03_ollama_cloud.py.

import os
import json
import requests

# Load word.env / .env for OLLAMA_API_KEY and OLLAMA_MODEL (same pattern as api_client)
from pathlib import Path
_here = Path(__file__).resolve().parent
for parent in [_here, _here.parent, _here.parent.parent]:
    for name in ("word.env", ".env"):
        env_file = parent / name
        if env_file.exists():
            from dotenv import load_dotenv
            load_dotenv(env_file)
            break
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
OLLAMA_PORT = 11434


def _build_summary_text(word_data):
    """Turn API result into a short JSON summary for the LLM."""
    if not word_data or not word_data.get("ok"):
        return json.dumps({"error": word_data.get("error", "No data")})
    word = word_data.get("word", "")
    prons = word_data.get("pronunciations", [])
    defs = word_data.get("definitions", [])
    audio = word_data.get("audio", [])
    summary = {
        "word": word,
        "pronunciation_count": len(prons),
        "pronunciations": [{"raw": p.get("raw"), "rawType": p.get("rawType"), "seq": p.get("seq")} for p in prons[:15]],
        "definition_count": len(defs),
        "definitions": [{"partOfSpeech": d.get("partOfSpeech"), "text": (d.get("text") or "")[:200]} for d in defs[:8]],
        "audio_count": len(audio),
    }
    return json.dumps(summary, indent=2)


def get_ollama_summary(word_data):
    """
    Generate a short, useful summary or pronunciation tip using Ollama.

    Prefers Ollama Cloud if OLLAMA_API_KEY is set; otherwise uses local Ollama.

    Parameters
    ----------
    word_data : dict
        Result from api_client.get_word_data() (must have word, pronunciations, definitions).

    Returns
    -------
    str or None
        AI-generated summary text, or None on failure.
    """
    summary_text = _build_summary_text(word_data)

    system_prompt = """You are a friendly language coach. Given pronunciation and definition data for a word, write a very brief report (2–4 short paragraphs or bullet points) that:
- Summarizes how to pronounce the word (use the provided phonetic spellings).
- Highlights one or two main meanings.
- Gives one simple tip for remembering the pronunciation or using the word.
Keep the tone helpful and concise. Use plain language."""

    user_prompt = f"Word data (JSON):\n\n{summary_text}\n\nWrite a short pronunciation and usage report for this word."

    if OLLAMA_API_KEY:
        url = "https://ollama.com/api/chat"
        headers = {
            "Authorization": f"Bearer {OLLAMA_API_KEY}",
            "Content-Type": "application/json",
        }
        body = {
            "model": "gpt-oss:20b-cloud",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
        }
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=OLLAMA_TIMEOUT)
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content")
        except requests.RequestException:
            return None

    # Local Ollama (generate API)
    url = f"http://localhost:{OLLAMA_PORT}/api/generate"
    body = {
        "model": OLLAMA_MODEL,
        "prompt": f"{system_prompt}\n\n---\n\n{user_prompt}",
        "stream": False,
    }
    try:
        resp = requests.post(url, json=body, timeout=OLLAMA_TIMEOUT)
        resp.raise_for_status()
        return resp.json().get("response")
    except requests.ConnectionError:
        return None
    except requests.RequestException:
        return None
