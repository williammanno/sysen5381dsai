# api_client.py
# Word Pronouncer API client (Merriam-Webster Collegiate with Free Dictionary fallback)
# Loads WORD_PRONOUNCER_API_KEY from word.env. Pairs with app.py (Shiny reporter).

import os
from pathlib import Path

import requests

# Load API key from word.env (current dir or project root)
_here = Path(__file__).resolve().parent
for parent in [_here, _here.parent, _here.parent.parent]:
    for name in ("word.env", ".env"):
        env_file = parent / name
        if env_file.exists():
            from dotenv import load_dotenv
            load_dotenv(env_file)
            break

# Merriam-Webster Collegiate Dictionary API (per dictionaryapi.com: key as query param ?key=)
MW_COLLEGIATE_URL = "https://www.dictionaryapi.com/api/v3/references/collegiate/json"
FREE_DICT_URL = "https://api.dictionaryapi.dev/api/v2/entries/en"

# Limit to most relevant: first entry's pronunciations/definitions/audio
MAX_PRONUNCIATIONS = 3
MAX_DEFINITIONS = 5
MAX_AUDIO = 2


def get_api_key():
    """Return WORD_PRONOUNCER_API_KEY from environment (stripped)."""
    return (os.getenv("WORD_PRONOUNCER_API_KEY") or "").strip()


def _parse_mw_entry(entry):
    """Convert one Merriam-Webster entry to our shape (pronunciations, definitions)."""
    pronunciations = []
    hwi = entry.get("hwi") or {}
    for i, pr in enumerate((hwi.get("prs") or [])):
        mw = (pr.get("mw") or "").strip()
        if mw:
            pronunciations.append({"raw": mw, "rawType": "Merriam-Webster", "seq": i})
    if not pronunciations and hwi.get("hw"):
        hw = (hwi.get("hw") or "").strip()
        if hw:
            pronunciations.append({"raw": hw, "rawType": "syllables", "seq": 0})

    definitions = []
    fl = (entry.get("fl") or "").strip()
    shortdef = entry.get("shortdef") or []
    for d in shortdef[:MAX_DEFINITIONS]:
        text = (d if isinstance(d, str) else str(d)).strip()
        if text:
            definitions.append({"partOfSpeech": fl, "text": text})

    return pronunciations, definitions


def _fetch_merriam_webster(word, key, timeout):
    """
    Fetch from Merriam-Webster Collegiate API.
    Returns (ok, pronunciations, definitions, audio_list, error_message).
    """
    # URL format per dictionaryapi.com: .../collegiate/json/{word}?key=YOUR_API_KEY
    encoded_word = requests.utils.quote(word, safe="")
    url = f"{MW_COLLEGIATE_URL}/{encoded_word}"
    try:
        resp = requests.get(url, params={"key": key}, timeout=timeout)
    except requests.RequestException as e:
        return False, [], [], [], str(e)

    if resp.status_code == 401:
        return False, [], [], [], "Invalid authentication credentials"
    if not resp.ok:
        return False, [], [], [], f"HTTP {resp.status_code}: {(resp.text or '')[:200]}"

    try:
        data = resp.json()
    except Exception as e:
        return False, [], [], [], str(e)

    # If word not found, API returns a list of suggestion strings (not objects)
    if isinstance(data, list) and data and isinstance(data[0], str):
        return False, [], [], [], "Word not found (try a suggestion)"

    if not isinstance(data, list) or not data:
        return False, [], [], [], "No data"

    # Use first entry only for most relevant pronunciations/definitions/audio
    all_prons = []
    all_defs = []
    audio_list = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        prons, defs = _parse_mw_entry(entry)
        all_prons.extend(prons)
        all_defs.extend(defs)
        hwi = entry.get("hwi") or {}
        for pr in (hwi.get("prs") or []):
            sound = pr.get("sound") or {}
            aud = sound.get("audio")
            if aud:
                if aud.startswith("bix"):
                    subdir = "bix"
                elif aud.startswith("gg"):
                    subdir = "gg"
                elif aud[0:1].isdigit() or (aud and not aud[0].isalpha()):
                    subdir = "number"
                else:
                    subdir = aud[0]
                audio_list.append({"fileUrl": f"https://media.merriam-webster.com/audio/prons/en/us/mp3/{subdir}/{aud}.mp3"})
        # Only first entry so we show the most relevant headword
        break

    return True, all_prons[:MAX_PRONUNCIATIONS], all_defs[:MAX_DEFINITIONS], audio_list[:MAX_AUDIO], None


def _parse_free_dict_entry(entry):
    """Convert Free Dictionary API entry to our shape (pronunciations, definitions)."""
    pronunciations = []
    for p in entry.get("phonetics", []):
        text = (p.get("text") or "").strip()
        if text:
            pronunciations.append({"raw": text, "rawType": "IPA", "seq": len(pronunciations)})
    definitions = []
    for m in entry.get("meanings", []):
        pos = (m.get("partOfSpeech") or "").strip()
        for d in m.get("definitions", [])[:2]:
            defn = (d.get("definition") or "").strip()
            if defn:
                definitions.append({"partOfSpeech": pos, "text": defn})
    return pronunciations, definitions


def _fetch_free_dict(word, timeout):
    """Fetch from Free Dictionary API (no key). Returns (ok, pronunciations, definitions, error)."""
    encoded = requests.utils.quote(word, safe="")
    url = f"{FREE_DICT_URL}/{encoded}"
    try:
        resp = requests.get(url, timeout=timeout)
    except requests.RequestException as e:
        return False, [], [], str(e)
    if resp.status_code == 404:
        return False, [], [], "Word not found"
    if not resp.ok:
        return False, [], [], f"HTTP {resp.status_code}: {(resp.text or '')[:200]}"
    try:
        data = resp.json()
    except Exception as e:
        return False, [], [], str(e)
    if not isinstance(data, list) or not data:
        return False, [], [], "No data"
    all_prons = []
    all_defs = []
    for entry in data:
        p, d = _parse_free_dict_entry(entry)
        all_prons.extend(p)
        all_defs.extend(d)
    return True, all_prons, all_defs, None


def get_word_data(word, api_key=None, timeout=15):
    """
    Fetch pronunciations and definitions. Uses Merriam-Webster Collegiate API when
    WORD_PRONOUNCER_API_KEY is set; on 401 or no key, falls back to Free Dictionary API.
    """
    word = (word or "").strip()
    if not word:
        return {"ok": False, "error": "No word provided."}

    key = (api_key or get_api_key()).strip()

    if key:
        ok, prons, defs, audio, err = _fetch_merriam_webster(word, key, timeout)
        if ok:
            return {
                "ok": True,
                "word": word,
                "pronunciations": prons,
                "definitions": defs,
                "audio": audio,
            }
        if err and ("401" in err or "Invalid authentication" in (err or "") or "credentials" in (err or "").lower()):
            ok2, prons2, defs2, err2 = _fetch_free_dict(word, timeout)
            if ok2:
                return {
                    "ok": True,
                    "word": word,
                    "pronunciations": prons2[:MAX_PRONUNCIATIONS],
                    "definitions": defs2[:MAX_DEFINITIONS],
                    "audio": [],
                }
            return {"ok": False, "error": f"Merriam-Webster: {err}. Fallback: {err2 or 'failed'}."}
        return {"ok": False, "error": err}

    ok, prons, defs, err = _fetch_free_dict(word, timeout)
    if ok:
        return {
            "ok": True,
            "word": word,
            "pronunciations": prons[:MAX_PRONUNCIATIONS],
            "definitions": defs[:MAX_DEFINITIONS],
            "audio": [],
        }
    return {"ok": False, "error": err or "Lookup failed."}
