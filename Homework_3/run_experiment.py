#!/usr/bin/env python3
"""
Homework 3 — prompt experiment + AI validation + CSV for statistical analysis.

Experimental design:
  - Independent variable: report system prompt (A, B, C markdown files).
  - Stimuli: multiple words (dictionary API baselines); optional repeated QC draws.
  - Outcome: custom framework dimensions + computed `composite_outcome` (see validation_framework.py).

Inspired by LAB_quality_control/run_quality_control.py (Ollama transport, JSON QC).

Why it can take a long time:
  Each (word, prompt) uses ``1 + qc_reps`` Ollama calls (one generate + repeated JSON validator).
  Work is roughly ``len(words) × 3 prompts × (1 + qc_reps)`` sequential round-trips,
  plus model latency (often tens of seconds each on a laptop).

  Speed it up (defaults are already tuned for speed):
  - Fast QC is **on** by default (compact rubric + smaller validator context + low JSON token cap).
    Use ``--rigorous-qc`` for the full rubric and untruncated context.
  - ``--parallel 2`` (default): overlap (word,prompt) jobs. Set ``--parallel 1`` if Ollama flakes.
  - ``--qc-model llama3.2:3b`` — small model **only** for JSON validation while keeping a larger ``--model`` for reports.
  - ``python run_experiment.py --turbo`` — 3 words, parallel≥3, sleep 0.
  - ``export OLLAMA_GEN_NUM_PREDICT=384`` / ``OLLAMA_QC_NUM_PREDICT=256`` (see ``ollama_helpers.py``).

Usage:
  cd Homework_3
  pip install -r requirements.txt
  python run_experiment.py
  python run_experiment.py --quick
  python run_experiment.py --words hello ecology pronunciation --qc-reps 2
  python analyze_results.py
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Environment + word reporter imports (same pattern as LAB_quality_control)
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
WORD_REPORTER = REPO_ROOT / "Homework_1" / "word_reporter"

for parent in [WORD_REPORTER, REPO_ROOT, HERE]:
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

from ollama_helpers import extract_json_object, ollama_chat, select_backend  # noqa: E402
from validation_framework import (  # noqa: E402
    PRIMARY_METRIC,
    parse_validator_json,
    summarize_framework,
    summarize_framework_fast,
)

DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:latest")
PROMPTS_DIR = HERE / "prompts"

# Default word list for a fuller ANOVA-style dataset (slow on local Ollama).
FULL_WORD_LIST = [
    "hello",
    "pronunciation",
    "ecology",
    "ambiguous",
    "synthesis",
    "algorithm",
    "benevolent",
    "laconic",
    "ephemeral",
    "ontology",
    "quotient",
    "meticulous",
]
QUICK_WORD_LIST = ["hello", "ecology", "laconic"]

# Fast validator: cap context size (baseline JSON is usually small; reports can grow).
FAST_QC_BASELINE_CHARS = 3800
FAST_QC_REPORT_CHARS = 2400
RUBRIC_COMPACT = PROMPTS_DIR / "custom_validator_rubric_compact.md"
RUBRIC_FULL = PROMPTS_DIR / "custom_validator_rubric.md"


def _trunc_for_qc(text: str, max_chars: int) -> str:
    t = (text or "").strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 28] + "\n... [truncated for QC]"


def _maybe_sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def discover_report_prompts() -> List[Tuple[str, str, Path]]:
    """
    report_prompt_a.md → label 'A', etc. Expect files named report_prompt_<letter>.md
    """
    files = sorted(PROMPTS_DIR.glob("report_prompt_*.md"))
    if len(files) < 3:
        raise FileNotFoundError(
            f"Need at least three report_prompt_*.md under {PROMPTS_DIR} (A/B/C experiment)."
        )
    out: List[Tuple[str, str, Path]] = []
    for p in files:
        stem = p.stem  # report_prompt_a
        suffix = stem.rsplit("_", maxsplit=1)[-1]
        label = suffix.upper() if len(suffix) <= 2 else stem
        out.append((label, stem, p))
    return out


def generate_report(system_prompt: str, baseline_json: str, model: str) -> str:
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


def run_validator(
    baseline_json: str,
    report_text: str,
    rubric_text: str,
    framework_summary: str,
    model: str,
    *,
    fast_qc: bool,
    qc_num_predict: Optional[int] = None,
) -> Dict[str, Any]:
    if fast_qc:
        base_in = _trunc_for_qc(baseline_json, FAST_QC_BASELINE_CHARS)
        rep_in = _trunc_for_qc(report_text, FAST_QC_REPORT_CHARS)
        system = (
            "You are a QA reviewer. "
            f"{summarize_framework_fast()}\n"
            "Return only the JSON object described in the user rubric."
        )
        user = (
            f"{rubric_text}\n\n---\n\n"
            "**Baseline JSON (authoritative):**\n\n"
            f"```json\n{base_in}\n```\n\n"
            "**Generated report:**\n\n"
            f"{rep_in}\n"
        )
    else:
        base_in = baseline_json
        rep_in = report_text
        system = (
            "You are an independent QA reviewer executing a coursework validation framework.\n"
            f"{framework_summary}\n\n"
            "Respond with a single JSON object exactly as instructed in the user message rubric."
        )
        user = (
            f"{rubric_text}\n\n---\n\n"
            "**Baseline JSON (authoritative):**\n\n"
            f"```json\n{base_in}\n```\n\n"
            "**Generated report:**\n\n"
            f"{rep_in}\n"
        )
    raw = ollama_chat(
        model,
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        format_json=True,
        num_predict=qc_num_predict,
    )
    payload = json.loads(extract_json_object(raw))
    return parse_validator_json(payload)


def run_word_prompt_cell(
    word: str,
    label: str,
    prompt_path: Path,
    baseline: str,
    system_prompt: str,
    gen_model: str,
    qc_model: str,
    rubric_text: str,
    framework_summary: str,
    fast_qc: bool,
    qc_reps: int,
    sleep_s: float,
    qc_num_predict: Optional[int],
) -> List[Dict[str, Any]]:
    out_rows: List[Dict[str, Any]] = []
    print(f"Generate word={word!r} prompt={label} ({prompt_path.stem}) ...", flush=True)
    try:
        report = generate_report(system_prompt, baseline, gen_model)
        gen_err = ""
    except Exception as e:
        gen_err = str(e)
        report = ""

    _maybe_sleep(sleep_s)

    mode = "fast" if fast_qc else "rigorous"
    if gen_err:
        for rep in range(max(1, qc_reps)):
            out_rows.append(
                _error_row(
                    word,
                    label,
                    prompt_path,
                    gen_model,
                    qc_model,
                    mode,
                    baseline,
                    gen_err,
                    rep,
                )
            )
        return out_rows

    for rep in range(max(1, qc_reps)):
        print(
            f"  Validator word={word!r} prompt={label} rep={rep + 1}/{qc_reps} (qc_model={qc_model!r}) ...",
            flush=True,
        )
        try:
            qc = run_validator(
                baseline,
                report,
                rubric_text,
                framework_summary,
                qc_model,
                fast_qc=fast_qc,
                qc_num_predict=qc_num_predict,
            )
            qc_err = ""
        except Exception as e:
            qc_err = str(e)
            qc = None
        out_rows.append(
            _success_row(
                word,
                label,
                prompt_path,
                gen_model,
                qc_model,
                mode,
                baseline,
                report,
                qc,
                qc_err,
                rep,
            )
        )
        _maybe_sleep(sleep_s)
    return out_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Homework 3: generate reports (prompts A/B/C) and AI-validate against custom rubric."
    )
    parser.add_argument(
        "--words",
        nargs="+",
        default=None,
        metavar="WORD",
        help="Words for dictionary baseline. Default: 12-word list; use --quick for 3 words.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Short smoke run: 3 words, no sleep between Ollama calls.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="Ollama model for report generation (validator defaults to this unless --qc-model).",
    )
    parser.add_argument("--out", default=str(HERE / "results" / "hw3_experiment.csv"))
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.15,
        help="Pause between Ollama calls (seconds). Use 0 to go as fast as the model allows.",
    )
    parser.add_argument(
        "--qc-reps",
        type=int,
        default=1,
        help="Repeated independent validator calls per report (increases n for ANOVA).",
    )
    parser.add_argument(
        "--rigorous-qc",
        action="store_true",
        help="Full rubric + full context to the validator (slower). Default is fast QC.",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=2,
        metavar="N",
        help="Run up to N (word,prompt) jobs concurrently. Use 1 if Ollama errors under load.",
    )
    parser.add_argument(
        "--qc-model",
        default=None,
        metavar="MODEL",
        help="Ollama model for JSON validator only (default: same as --model). Env: OLLAMA_QC_MODEL.",
    )
    parser.add_argument(
        "--qc-num-predict",
        type=int,
        default=None,
        metavar="N",
        help="Max new tokens for validator JSON only (default: OLLAMA_QC_NUM_PREDICT / built-in cap).",
    )
    parser.add_argument(
        "--turbo",
        action="store_true",
        help="Fastest preset: 3 words, fast QC, parallel=3, sleep=0 (overridable; see --help).",
    )
    args = parser.parse_args()

    if args.words is not None:
        word_list = [w.strip() for w in args.words if w.strip()]
    elif args.quick or args.turbo:
        word_list = list(QUICK_WORD_LIST)
    else:
        word_list = list(FULL_WORD_LIST)

    parallel = max(1, int(args.parallel))
    if args.turbo and "--parallel" not in sys.argv:
        parallel = max(parallel, 3)

    sleep_s = 0.0 if (args.quick or args.turbo) else float(args.sleep)
    if args.turbo:
        sleep_s = 0.0

    fast_qc = not args.rigorous_qc
    rubric_path = RUBRIC_COMPACT if fast_qc else RUBRIC_FULL
    if not rubric_path.exists():
        raise FileNotFoundError(f"Missing {rubric_path}")
    rubric_text = load_text(rubric_path)

    framework_summary = summarize_framework()

    report_prompts = discover_report_prompts()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    select_backend(args.model)

    gen_model = args.model
    qc_model = (args.qc_model or os.getenv("OLLAMA_QC_MODEL") or "").strip() or gen_model

    n_prompts = len(report_prompts)
    qr = max(1, args.qc_reps)
    est_calls = len(word_list) * n_prompts * (1 + qr)
    print(
        f"Running {len(word_list)} words × {n_prompts} prompts × {qr} QC rep(s); "
        f"~{est_calls} Ollama calls; parallel={parallel}; "
        f"validator={'fast' if fast_qc else 'rigorous'}; qc_model={qc_model!r}.",
        file=sys.stderr,
    )

    word_baselines: Dict[str, str] = {}
    for word in word_list:
        data = get_word_data(word)
        if not data.get("ok"):
            print(f"[skip] {word}: {data.get('error', 'no data')}", file=sys.stderr)
            continue
        word_baselines[word] = _build_summary_for_llm(data)

    if not word_baselines:
        print("No baselines — check words/API keys.", file=sys.stderr)
        raise SystemExit(2)

    prompt_body: Dict[str, Tuple[str, Path]] = {
        label: (load_text(pth), pth) for label, _stem, pth in report_prompts
    }

    tasks: List[Tuple[str, str, Path, str, str]] = []
    for w, baseline in word_baselines.items():
        for label, _stem, pth in report_prompts:
            sp, _ = prompt_body[label]
            tasks.append((w, label, pth, baseline, sp))

    rows: List[Dict[str, Any]] = []

    def _one(t: Tuple[str, str, Path, str, str]) -> List[Dict[str, Any]]:
        w, label, pth, baseline, sp = t
        return run_word_prompt_cell(
            w,
            label,
            pth,
            baseline,
            sp,
            gen_model,
            qc_model,
            rubric_text,
            framework_summary,
            fast_qc,
            args.qc_reps,
            sleep_s,
            args.qc_num_predict,
        )

    if parallel <= 1:
        for t in tasks:
            rows.extend(_one(t))
    else:
        with ThreadPoolExecutor(max_workers=min(parallel, len(tasks))) as ex:
            futs = [ex.submit(_one, t) for t in tasks]
            for fut in as_completed(futs):
                rows.extend(fut.result())

    rows.sort(key=lambda r: (r["word"], r["prompt_label"], int(r.get("qc_rep", 0))))

    if not rows:
        print("No rows — check words/API keys.", file=sys.stderr)
        raise SystemExit(2)

    fieldnames = list(rows[0].keys())
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} rows → {out_path}")
    if Path(out_path).resolve() == (HERE / "results" / "hw3_experiment.csv").resolve():
        print("Run: python analyze_results.py")
    else:
        print(f"Run: python analyze_results.py --csv {out_path}")


def _error_row(
    word: str,
    label: str,
    prompt_path: Path,
    gen_model: str,
    qc_model: str,
    validator_mode: str,
    baseline: str,
    gen_err: str,
    rep: int,
) -> Dict[str, Any]:
    base = _base_row(word, label, prompt_path, gen_model, qc_model, validator_mode, baseline, rep)
    base.update(
        {
            "report_text": "",
            "generate_error": gen_err,
            "qc_error": "",
            "evidence_alignment_index": "",
            "coverage_of_baseline_facets": "",
            "clarity_tier": "",
            "instructional_usefulness_band": "",
            "mislearning_risk_ordinal": "",
            "thematic_tags": "",
            "qualitative_note": "",
            "meets_benchmark_pass": "",
            PRIMARY_METRIC: "",
        }
    )
    return base


def _success_row(
    word: str,
    label: str,
    prompt_path: Path,
    gen_model: str,
    qc_model: str,
    validator_mode: str,
    baseline: str,
    report: str,
    qc: Optional[Dict[str, Any]],
    qc_err: str,
    rep: int,
) -> Dict[str, Any]:
    base = _base_row(word, label, prompt_path, gen_model, qc_model, validator_mode, baseline, rep)
    if qc is None:
        base.update(
            {
                "report_text": report,
                "generate_error": "",
                "qc_error": qc_err,
                "evidence_alignment_index": "",
                "coverage_of_baseline_facets": "",
                "clarity_tier": "",
                "instructional_usefulness_band": "",
                "mislearning_risk_ordinal": "",
                "thematic_tags": "",
                "qualitative_note": "",
                "meets_benchmark_pass": "",
                PRIMARY_METRIC: "",
            }
        )
    else:
        base.update(
            {
                "report_text": report,
                "generate_error": "",
                "qc_error": qc_err,
                "evidence_alignment_index": qc["evidence_alignment_index"],
                "coverage_of_baseline_facets": qc["coverage_of_baseline_facets"],
                "clarity_tier": qc["clarity_tier"],
                "instructional_usefulness_band": qc["instructional_usefulness_band"],
                "mislearning_risk_ordinal": qc["mislearning_risk_ordinal"],
                "thematic_tags": qc["thematic_tags"],
                "qualitative_note": qc["qualitative_note"],
                "meets_benchmark_pass": qc["meets_benchmark_pass"],
                PRIMARY_METRIC: qc[PRIMARY_METRIC],
            }
        )
    return base


def _base_row(
    word: str,
    label: str,
    prompt_path: Path,
    gen_model: str,
    qc_model: str,
    validator_mode: str,
    baseline: str,
    rep: int,
) -> Dict[str, Any]:
    return {
        "word": word,
        "prompt_label": label,
        "prompt_file": str(prompt_path.relative_to(HERE)),
        "qc_rep": rep,
        "model": gen_model,
        "qc_model": qc_model,
        "validator_mode": validator_mode,
        "baseline_json_chars": len(baseline),
    }


if __name__ == "__main__":
    main()
