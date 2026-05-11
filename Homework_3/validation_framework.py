"""
Custom validation framework for Homework 3 (not LAB Likert scales).

Defines dimensional scores, benchmarks, and a deterministic composite outcome
computed from reviewer JSON so statistical analysis stays reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, MutableMapping, Sequence


@dataclass(frozen=True)
class Benchmarks:
    """
    Operational pass/fail gate for stakeholder acceptance of learner-facing copy.
    Tune these thresholds to reflect how strict fidelity must be vs. readability.
    """

    min_evidence_alignment_index: int = 72
    min_coverage_of_baseline_facets: int = 65
    max_mislearning_risk_ordinal: int = 1


PRIMARY_METRIC = "composite_outcome"


def summarize_framework() -> str:
    """Human-readable capsule for reports and logging."""
    b = Benchmarks()
    return (
        "Dimensions (validator supplies): evidence_alignment_index 0–100; "
        "coverage_of_baseline_facets 0–100; clarity_tier 1–4 (novice-friendly → terse expert); "
        "instructional_usefulness_band 1–7 (tangential → high-leverage tutoring); "
        "mislearning_risk_ordinal 0–3 (none → severe); thematic_tags list; qualitative_note ≤120 words.\n"
        f"Benchmark PASS requires: evidence_alignment_index ≥ {b.min_evidence_alignment_index}, "
        f"coverage ≥ {b.min_coverage_of_baseline_facets}, "
        f"mislearning_risk ≤ {b.max_mislearning_risk_ordinal}.\n"
        f"Outcome for statistics: `{PRIMARY_METRIC}` ∈ [0,100] computed in Python via `compute_composite()`."
    )


def summarize_framework_fast() -> str:
    """Short system prompt for fast QC mode (same pass bands as Benchmarks)."""
    b = Benchmarks()
    return (
        "Reply with JSON only. Compare report to baseline JSON. "
        f"Pass bands: evidence_alignment_index≥{b.min_evidence_alignment_index}, "
        f"coverage≥{b.min_coverage_of_baseline_facets}, mislearning_risk≤{b.max_mislearning_risk_ordinal}. "
        f"`{PRIMARY_METRIC}` is computed downstream in Python."
    )


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def compute_composite(row: Mapping[str, Any]) -> float:
    """
    Map custom dimensions onto a single 0–100 score for ANOVA/regression/t-tests.

    Weights prioritize fidelity to baseline JSON over stylistic flourish.
    """
    eai = float(row["evidence_alignment_index"])
    cov = float(row["coverage_of_baseline_facets"])
    clarity = float(row["clarity_tier"])
    iu = float(row["instructional_usefulness_band"])
    risk = float(row["mislearning_risk_ordinal"])
    clarity_0_1 = (clarity - 1.0) / 3.0
    iu_0_1 = (iu - 1.0) / 6.0
    # Penalize risk heavily: each step above 0 subtracts ~8 points before clip.
    raw = (
        0.40 * eai
        + 0.35 * cov
        + 0.12 * (100.0 * clarity_0_1)
        + 0.13 * (100.0 * iu_0_1)
        - 8.0 * risk
    )
    return _clip(raw, 0.0, 100.0)


def meets_benchmark(row: Mapping[str, Any]) -> bool:
    b = Benchmarks()
    return (
        int(row["evidence_alignment_index"]) >= b.min_evidence_alignment_index
        and int(row["coverage_of_baseline_facets"]) >= b.min_coverage_of_baseline_facets
        and int(row["mislearning_risk_ordinal"]) <= b.max_mislearning_risk_ordinal
    )


def parse_validator_json(raw: MutableMapping[str, Any]) -> Dict[str, Any]:
    """
    Normalize model output keys, coerce types/ranges, add composite + benchmark flag.
    """
    data = {str(k).lower().strip().replace("-", "_"): v for k, v in raw.items()}

    def req_int(key: str, lo: int, hi: int) -> int:
        if key not in data:
            raise ValueError(f"Missing required key {key!r}")
        v = int(round(float(data[key])))
        if v < lo or v > hi:
            raise ValueError(f"{key} must be between {lo} and {hi}, got {v}")
        return v

    tags = data.get("thematic_tags") or data.get("qualitative_codes") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    elif not isinstance(tags, Sequence):
        raise ValueError("thematic_tags must be a list or comma-separated string")
    else:
        tags = [str(t).strip() for t in tags if str(t).strip()]

    out: Dict[str, Any] = {
        "evidence_alignment_index": req_int("evidence_alignment_index", 0, 100),
        "coverage_of_baseline_facets": req_int("coverage_of_baseline_facets", 0, 100),
        "clarity_tier": req_int("clarity_tier", 1, 4),
        "instructional_usefulness_band": req_int("instructional_usefulness_band", 1, 7),
        "mislearning_risk_ordinal": req_int("mislearning_risk_ordinal", 0, 3),
        "thematic_tags": ";".join(tags[:12]),
        "qualitative_note": str(data.get("qualitative_note", data.get("reviewer_synopsis", "")))[
            :500
        ],
    }
    out["meets_benchmark_pass"] = meets_benchmark(out)
    out[PRIMARY_METRIC] = round(compute_composite(out), 3)
    return out

