"""
Ollama transport selection and chat wrappers (adapted from LAB_quality_control/run_quality_control.py).
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import requests

OLLAMA_HOST = os.getenv("OLLAMA_HOST")
if OLLAMA_HOST:
    OLLAMA_BASE = OLLAMA_HOST.rstrip("/")
else:
    _port = int(os.getenv("OLLAMA_PORT", "11434"))
    OLLAMA_BASE = f"http://127.0.0.1:{_port}"

CHAT_URL = f"{OLLAMA_BASE}/api/chat"
GENERATE_URL = f"{OLLAMA_BASE}/api/generate"
OPENAI_CHAT_URL = f"{OLLAMA_BASE}/v1/chat/completions"
TAGS_URL = f"{OLLAMA_BASE}/api/tags"

REQUEST_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))
# Backend probe only: first inference can load a large model for a long time; keep probe tiny + patient.
PROBE_TIMEOUT = int(os.getenv("OLLAMA_PROBE_TIMEOUT", "180"))

_legacy_np = os.getenv("OLLAMA_NUM_PREDICT")
# Generation: shorter default = faster reports. QC uses a separate (smaller) cap for JSON-only replies.
_GEN_NUM = max(128, min(int(os.getenv("OLLAMA_GEN_NUM_PREDICT", _legacy_np or "512")), 8192))
_QC_NUM = max(96, min(int(os.getenv("OLLAMA_QC_NUM_PREDICT", _legacy_np or "384")), 4096))

_LLM_BACKEND: Optional[str] = None


def _pick_light_probe_model(names: List[str], requested: str) -> str:
    """
    Use the smallest-looking local model for the connectivity probe so cold start
    finishes within PROBE_TIMEOUT. Actual runs still use --model from the caller.
    """
    if not names:
        return requested

    def tier(n: str) -> int:
        s = n.lower()
        if "135m" in s or "360m" in s:
            return 0
        if "270m" in s or "560m" in s:
            return 1
        if "1.7b" in s:
            return 2
        if "3b" in s or "2b" in s:
            return 3
        if "7b" in s or "8b" in s:
            return 5
        if "llava" in s or "vision" in s:
            return 90
        return 50

    return sorted(names, key=lambda n: (tier(n), len(n), n.lower()))[0]


def _messages_to_generate_prompt(messages: List[Dict[str, str]]) -> str:
    parts: List[str] = []
    for m in messages:
        role = (m.get("role") or "user").upper()
        content = (m.get("content") or "").strip()
        parts.append(f"{role}:\n{content}")
    return "\n\n---\n\n".join(parts)


def ollama_generate(model: str, prompt: str, format_json: bool = False, num_predict: Optional[int] = None) -> str:
    cap = num_predict if num_predict is not None else _GEN_NUM
    cap = max(32, min(cap, 8192))
    body: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": cap},
    }
    if format_json:
        body["format"] = "json"
    r = requests.post(GENERATE_URL, json=body, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if data.get("error"):
        raise RuntimeError(f"Ollama generate error: {data.get('error')}")
    out = (data.get("response") or "").strip()
    if not out:
        raise RuntimeError(f"Ollama generate returned no response field: {data!r}")
    return out


def ollama_openai_v1_chat(
    model: str,
    messages: List[Dict[str, str]],
    format_json: bool = False,
    num_predict: Optional[int] = None,
) -> str:
    cap = num_predict if num_predict is not None else _GEN_NUM
    cap = max(32, min(cap, 8192))
    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "max_tokens": cap,
    }
    if format_json:
        body["format"] = "json"
    r = requests.post(OPENAI_CHAT_URL, json=body, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(f"Ollama OpenAI chat error: {data.get('error')}")
    choices = data.get("choices") if isinstance(data, dict) else None
    if not choices:
        raise RuntimeError(f"OpenAI-compat response missing choices: {data!r}")
    content = (choices[0].get("message") or {}).get("content")
    if not content:
        raise RuntimeError(f"OpenAI-compat response missing content: {data!r}")
    return str(content).strip()


def _native_chat(
    model: str,
    messages: List[Dict[str, str]],
    format_json: bool,
    num_predict: Optional[int] = None,
) -> str:
    cap = num_predict if num_predict is not None else _GEN_NUM
    cap = max(32, min(cap, 8192))
    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": cap},
    }
    if format_json:
        body["format"] = "json"
    r = requests.post(CHAT_URL, json=body, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(f"Ollama chat error: {data.get('error')}")
    content = (data.get("message") or {}).get("content")
    if not content:
        raise RuntimeError(f"Ollama returned no message content: {data!r}")
    return content.strip()


def select_backend(requested_model: str) -> str:
    global _LLM_BACKEND
    if _LLM_BACKEND:
        return _LLM_BACKEND

    try:
        tr = requests.get(TAGS_URL, timeout=10)
        tr.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(
            f"Cannot reach Ollama at {OLLAMA_BASE} (GET {TAGS_URL} failed: {e}).\n"
            "Fix: start the Ollama app or run `ollama serve`, then retry.\n"
            "If Ollama uses another host/port, set OLLAMA_HOST (e.g. http://127.0.0.1:11434) "
            "or OLLAMA_PORT."
        ) from e
    try:
        tags = tr.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"{TAGS_URL} did not return JSON. Another app may be using this port — "
            "set OLLAMA_HOST to your real Ollama base URL."
        ) from e
    if "models" not in tags:
        raise RuntimeError(f"{TAGS_URL} JSON has no 'models' key.")

    names: List[str] = []
    for m in tags.get("models") or []:
        n = m.get("name") or m.get("model")
        if n:
            names.append(n)
    probe_model = _pick_light_probe_model(names, requested_model)

    msg = [{"role": "user", "content": "Reply with only: ok"}]
    candidates: List[Tuple[str, str, Dict[str, Any]]] = [
        (
            "chat",
            CHAT_URL,
            {
                "model": probe_model,
                "messages": msg,
                "stream": False,
                "options": {"num_predict": 12},
            },
        ),
        (
            "generate",
            GENERATE_URL,
            {
                "model": probe_model,
                "prompt": "Reply with only: ok",
                "stream": False,
                "options": {"num_predict": 12},
            },
        ),
        (
            "openai_v1",
            OPENAI_CHAT_URL,
            {
                "model": probe_model,
                "messages": msg,
                "stream": False,
                "max_tokens": 12,
            },
        ),
    ]
    probe_lines: List[str] = []
    for name, url, body in candidates:
        try:
            resp = requests.post(url, json=body, timeout=PROBE_TIMEOUT)
        except requests.RequestException as e:
            probe_lines.append(f"  - {name} POST {url}\n    request error: {e}")
            continue
        snippet = (resp.text or "")[:240].replace("\n", " ")
        if resp.status_code in (404, 405) or not resp.ok:
            probe_lines.append(f"  - {name} POST {url}\n    HTTP {resp.status_code}: {snippet}")
            continue
        try:
            data = resp.json()
        except json.JSONDecodeError:
            probe_lines.append(f"  - {name} POST {url}\n    HTTP {resp.status_code}, body not JSON: {snippet}")
            continue
        if isinstance(data, dict) and data.get("error"):
            probe_lines.append(f"  - {name} POST {url}\n    API error: {data.get('error')}")
            continue
        _LLM_BACKEND = name
        return name

    hint_models = ", ".join(names[:8]) if names else "(none listed)"
    raise RuntimeError(
        "No working Ollama inference POST endpoint.\n"
        f"Base URL in use: {OLLAMA_BASE!r}  (override with OLLAMA_HOST or OLLAMA_PORT)\n"
        f"Connectivity probe model: {probe_model!r}  (lightest local pick for speed; "
        f"your --model is separate; models seen: {hint_models})\n"
        f"Probe read timeout: {PROBE_TIMEOUT}s  (set OLLAMA_PROBE_TIMEOUT to wait longer on slow CPU loads)\n"
        "Probe results:\n"
        + "\n".join(probe_lines)
        + "\n\nTypical fixes:\n"
        "  • Read timeouts often mean the model is still loading — wait and retry, or "
        "`export OLLAMA_PROBE_TIMEOUT=300`.\n"
        "  • Use a smaller `--model` (e.g. llama3.2:3b) if your machine struggles with gemma3.\n"
        "  • Open Ollama Desktop (macOS) or run `ollama serve`; `ollama pull <model>` if missing.\n"
        "  • If another process uses 11434, set OLLAMA_HOST to the real Ollama URL."
    )


def ollama_chat(
    model: str,
    messages: List[Dict[str, str]],
    format_json: bool = False,
    num_predict: Optional[int] = None,
) -> str:
    if not _LLM_BACKEND:
        raise RuntimeError("select_backend() must run before ollama_chat().")
    cap = num_predict
    if cap is None and format_json:
        cap = _QC_NUM
    if _LLM_BACKEND == "chat":
        return _native_chat(model, messages, format_json, num_predict=cap)
    if _LLM_BACKEND == "generate":
        return ollama_generate(
            model,
            _messages_to_generate_prompt(messages),
            format_json=format_json,
            num_predict=cap,
        )
    if _LLM_BACKEND == "openai_v1":
        return ollama_openai_v1_chat(model, messages, format_json, num_predict=cap)
    raise RuntimeError(f"Unknown backend: {_LLM_BACKEND}")


def extract_json_object(text: str) -> str:
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", t)
    if fence:
        t = fence.group(1).strip()
    m = re.search(r"\{[\s\S]*\}", t)
    if m:
        return m.group(0)
    return t
