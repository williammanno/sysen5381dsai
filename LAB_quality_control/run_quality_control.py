#!/usr/bin/env python3
"""
LAB quality control: compare two report-generation prompts from markdown files
using Ollama (local). Metrics follow dsai 09_text_analysis/02_ai_quality_control.R
(accuracy, clarity, relevance Likert + accurate boolean), graded against the
same baseline JSON the Shiny app feeds to the LLM (ollama_client._build_summary_for_llm).

Workflow extracted from: Homework_1/word_reporter (app.py -> ollama_client.get_report_text).

Usage:
  cd LAB_quality_control
  python run_quality_control.py
  python run_quality_control.py --words hello pronunciation ecology
  python run_quality_control.py --model llama3.2:3b --out results/qc_run.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# -----------------------------------------------------------------------------
# Paths & imports from Word Reporter (Shiny) package
# -----------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
WORD_REPORTER = REPO_ROOT / "Homework_1" / "word_reporter"

for parent in [WORD_REPORTER, REPO_ROOT]:
    for name in ("word.env", "ollama.env", ".env"):
        p = parent / name
        if p.exists():
            from dotenv import load_dotenv

            load_dotenv(p)
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

if str(WORD_REPORTER) not in sys.path:
    sys.path.insert(0, str(WORD_REPORTER))

from api_client import get_word_data  # noqa: E402
from ollama_client import _build_summary_for_llm  # noqa: E402

PROMPTS_DIR = HERE / "prompts"

# Match word_reporter/ollama_client.py: local Ollama uses 127.0.0.1 to avoid IPv6 surprises.
# Set OLLAMA_HOST=http://127.0.0.1:11434 or use OLLAMA_PORT with default host.
_ollama_host = os.getenv("OLLAMA_HOST")
if _ollama_host:
    OLLAMA_BASE = _ollama_host.rstrip("/")
else:
    _port = int(os.getenv("OLLAMA_PORT", "11434"))
    OLLAMA_BASE = f"http://127.0.0.1:{_port}"

CHAT_URL = f"{OLLAMA_BASE}/api/chat"
GENERATE_URL = f"{OLLAMA_BASE}/api/generate"
OPENAI_CHAT_URL = f"{OLLAMA_BASE}/v1/chat/completions"
TAGS_URL = f"{OLLAMA_BASE}/api/tags"

DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:latest")
REQUEST_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))

# Set once by select_backend(): "chat" | "generate" | "openai_v1"
_LLM_BACKEND: Optional[str] = None


def _messages_to_generate_prompt(messages: List[Dict[str, str]]) -> str:
    """Flatten chat messages into one prompt (same idea as ollama_client local path)."""
    parts: List[str] = []
    for m in messages:
        role = (m.get("role") or "user").upper()
        content = (m.get("content") or "").strip()
        parts.append(f"{role}:\n{content}")
    return "\n\n---\n\n".join(parts)


def ollama_generate(
    model: str,
    prompt: str,
    format_json: bool = False,
) -> str:
    body: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 2048},
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
) -> str:
    """
    OpenAI-compatible endpoint (Ollama exposes this even when /api/chat path differs).
    See: https://github.com/ollama/ollama/blob/main/docs/openai.md
    """
    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
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


def _native_chat(model: str, messages: List[Dict[str, str]], format_json: bool) -> str:
    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {"num_predict": 2048},
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
    """
    Pick the first working transport. Native /api/chat and /api/generate can 404 on
    some installs or proxies; /v1/chat/completions is the OpenAI-compatible route.
    """
    global _LLM_BACKEND
    if _LLM_BACKEND:
        return _LLM_BACKEND

    tr = requests.get(TAGS_URL, timeout=10)
    tr.raise_for_status()
    try:
        tags = tr.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"{TAGS_URL} did not return JSON. Another app may be using this port — "
            "set OLLAMA_HOST to your real Ollama base URL (e.g. http://127.0.0.1:11434)."
        ) from e
    if "models" not in tags:
        raise RuntimeError(
            f"{TAGS_URL} JSON has no 'models' key (not an Ollama tags response). "
            f"Keys: {list(tags.keys())[:20]}. Fix OLLAMA_HOST / port."
        )

    names: List[str] = []
    for m in tags.get("models") or []:
        n = m.get("name") or m.get("model")
        if n:
            names.append(n)
    probe_model = requested_model if requested_model in names else (names[0] if names else requested_model)
    if requested_model not in names and names:
        print(
            f"Note: model {requested_model!r} not in `ollama list`; probing endpoints with {probe_model!r}. "
            f"Run: ollama pull {requested_model}",
            file=sys.stderr,
        )

    msg = [{"role": "user", "content": "ping"}]
    candidates: List[Tuple[str, str, Dict[str, Any]]] = [
        ("chat", CHAT_URL, {"model": probe_model, "messages": msg, "stream": False}),
        ("generate", GENERATE_URL, {"model": probe_model, "prompt": "ping", "stream": False}),
        ("openai_v1", OPENAI_CHAT_URL, {"model": probe_model, "messages": msg, "stream": False}),
    ]
    for name, url, body in candidates:
        try:
            resp = requests.post(url, json=body, timeout=60)
        except requests.RequestException:
            continue
        if resp.status_code in (404, 405):
            continue
        _LLM_BACKEND = name
        print(f"Using Ollama transport: {name} → {url}", file=sys.stderr)
        return name

    raise RuntimeError(
        "No working Ollama inference endpoint found (all returned 404/405). Tried:\n"
        f"  - {CHAT_URL}\n  - {GENERATE_URL}\n  - {OPENAI_CHAT_URL}\n"
        "Confirm `ollama serve` is running and `curl -s "
        f"{OLLAMA_BASE}/api/tags` shows JSON with a `models` list."
    )


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def discover_report_prompts() -> List[Tuple[str, Path]]:
    """Load report_prompt_*.md sorted by filename (e.g. a, b)."""
    files = sorted(PROMPTS_DIR.glob("report_prompt_*.md"))
    if not files:
        raise FileNotFoundError(
            f"No report_prompt_*.md under {PROMPTS_DIR}. Add at least two markdown prompts."
        )
    out: List[Tuple[str, Path]] = []
    for p in files:
        stem = p.stem  # report_prompt_a
        out.append((stem, p))
    return out


def ollama_chat(
    model: str,
    messages: List[Dict[str, str]],
    format_json: bool = False,
) -> str:
    if not _LLM_BACKEND:
        raise RuntimeError("Internal error: select_backend() must run before ollama_chat().")
    if _LLM_BACKEND == "chat":
        return _native_chat(model, messages, format_json)
    if _LLM_BACKEND == "generate":
        return ollama_generate(
            model, _messages_to_generate_prompt(messages), format_json=format_json
        )
    if _LLM_BACKEND == "openai_v1":
        return ollama_openai_v1_chat(model, messages, format_json)
    raise RuntimeError(f"Unknown backend: {_LLM_BACKEND}")


def generate_report(system_prompt: str, baseline_json: str, model: str) -> str:
    """Mirror Shiny flow: system = coach prompt file; user = JSON + task."""
    user = (
        f"Word data (JSON):\n\n{baseline_json}\n\n"
        "Follow your system instructions and produce the learner-facing report now."
    )
    return ollama_chat(
        model,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user},
        ],
        format_json=False,
    )


def build_qc_user_message(baseline_json: str, report_text: str, rubric_text: str) -> str:
    return (
        f"{rubric_text}\n\n"
        "---\n\n"
        "**Original data (baseline — authoritative):**\n\n"
        f"```json\n{baseline_json}\n```\n\n"
        "**AI-generated report to evaluate:**\n\n"
        f"{report_text}\n"
    )


def parse_qc_json(raw: str) -> Dict[str, Any]:
    text = raw.strip()
    # Strip ```json ... ``` if present
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence:
        text = fence.group(1).strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        text = m.group(0)
    data = json.loads(text)
    # Models sometimes use different key casing
    data = {str(k).lower().strip(): v for k, v in data.items()}
    for key in ("accuracy", "clarity", "relevance"):
        if key not in data:
            raise ValueError(f"Missing key {key} in QC JSON: keys seen={list(data.keys())}")
        v = int(float(data[key]))
        if v < 1 or v > 5:
            raise ValueError(f"{key} must be 1–5, got {v}")
    if "accurate" not in data:
        raise ValueError("Missing accurate in QC JSON")
    av = data["accurate"]
    if isinstance(av, str):
        data["accurate"] = av.strip().lower() in ("true", "1", "yes")
    else:
        data["accurate"] = bool(av)
    data["accuracy"] = int(data["accuracy"])
    data["clarity"] = int(data["clarity"])
    data["relevance"] = int(data["relevance"])
    data["details"] = str(data.get("details", ""))[:500]
    return data


def run_qc(
    baseline_json: str,
    report_text: str,
    rubric_text: str,
    model: str,
) -> Dict[str, Any]:
    system = (
        "You are a quality control validator. "
        "You must compare the report to the baseline JSON only. "
        "Respond with a single JSON object as specified in the user message rubric—no other text."
    )
    user = build_qc_user_message(baseline_json, report_text, rubric_text)
    raw = ollama_chat(
        model,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        format_json=True,
    )
    return parse_qc_json(raw)


def main() -> None:
    parser = argparse.ArgumentParser(description="A/B report prompts + Ollama QC vs baseline JSON.")
    parser.add_argument(
        "--words",
        nargs="+",
        default=["hello", "pronunciation"],
        help="Words to fetch via get_word_data (same as app).",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model for generate + QC.")
    parser.add_argument(
        "--out",
        default=str(HERE / "results" / "qc_results.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.5,
        help="Seconds between Ollama calls to reduce load.",
    )
    args = parser.parse_args()

    rubric_path = PROMPTS_DIR / "qc_rubric.md"
    if not rubric_path.exists():
        raise FileNotFoundError(f"Missing {rubric_path}")
    rubric_text = load_text(rubric_path)

    report_prompts = discover_report_prompts()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []

    # Reachability + identity check + pick /api/chat vs /api/generate vs /v1/chat/completions
    try:
        select_backend(args.model)
    except Exception as e:
        print(str(e), file=sys.stderr)
        print(
            f"Could not connect to Ollama at {OLLAMA_BASE}. "
            "Start Ollama Desktop or run `ollama serve`, then `ollama pull <model>`.",
            file=sys.stderr,
        )
        raise SystemExit(1) from e

    for word in args.words:
        word = word.strip()
        if not word:
            continue
        data = get_word_data(word)
        if not data.get("ok"):
            print(f"[skip] {word}: {data.get('error', 'no data')}", file=sys.stderr)
            continue
        baseline = _build_summary_for_llm(data)

        for prompt_id, prompt_path in report_prompts:
            system_prompt = load_text(prompt_path)
            print(f"Generating: word={word!r} prompt={prompt_id} ...")
            try:
                report = generate_report(system_prompt, baseline, args.model)
            except Exception as e:
                print(f"  generate error: {e}", file=sys.stderr)
                rows.append(
                    {
                        "word": word,
                        "prompt_id": prompt_id,
                        "prompt_file": str(prompt_path.relative_to(HERE)),
                        "model": args.model,
                        "baseline_json_chars": len(baseline),
                        "report_text": "",
                        "generate_error": str(e),
                        "accurate": "",
                        "accuracy": "",
                        "clarity": "",
                        "relevance": "",
                        "details": "",
                        "qc_error": "",
                    }
                )
                time.sleep(args.sleep)
                continue

            time.sleep(args.sleep)
            print(f"  QC: word={word!r} prompt={prompt_id} ...")
            try:
                qc = run_qc(baseline, report, rubric_text, args.model)
                qc_err = ""
            except Exception as e:
                qc_err = str(e)
                qc = None

            rows.append(
                {
                    "word": word,
                    "prompt_id": prompt_id,
                    "prompt_file": str(prompt_path.relative_to(HERE)),
                    "model": args.model,
                    "baseline_json_chars": len(baseline),
                    "report_text": report,
                    "generate_error": "",
                    "accurate": qc["accurate"] if qc else "",
                    "accuracy": qc["accuracy"] if qc else "",
                    "clarity": qc["clarity"] if qc else "",
                    "relevance": qc["relevance"] if qc else "",
                    "details": qc["details"] if qc else "",
                    "qc_error": qc_err,
                }
            )
            time.sleep(args.sleep)

    if not rows:
        print("No rows to write. Check words and API keys (word.env).", file=sys.stderr)
        raise SystemExit(2)

    fieldnames = list(rows[0].keys())
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} row(s) to {out_path}")

    # Console summary: mean Likert by prompt_id
    from collections import defaultdict

    sums: Dict[str, List[float]] = defaultdict(list)
    for r in rows:
        if r.get("generate_error") or r.get("qc_error"):
            continue
        pid = str(r["prompt_id"])
        for m in ("accuracy", "clarity", "relevance"):
            if isinstance(r.get(m), int):
                sums[f"{pid}_{m}"].append(float(r[m]))

    print("\nMean Likert (1–5) by prompt (successful QC only):")
    for key in sorted(sums.keys()):
        vals = sums[key]
        if vals:
            print(f"  {key}: {sum(vals) / len(vals):.2f} (n={len(vals)})")


if __name__ == "__main__":
    main()
