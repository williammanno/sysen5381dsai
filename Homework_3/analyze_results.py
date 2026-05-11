#!/usr/bin/env python3
"""
Statistical analysis for Homework 3 experiment CSV.

- One-way ANOVA on composite_outcome across prompt_label (A/B/C).
- Pairwise Welch t-tests with Bonferroni adjustment.
- OLS-style multiple regression with prompt dummies (reference = alphabetically first label).

Usage:
  cd Homework_3 && python analyze_results.py
  python analyze_results.py --csv results/hw3_experiment.csv
  python analyze_results.py --csv path/to/other.csv --text-out results/stats_summary.txt
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Tuple

import numpy as np
from scipy import stats as st

from validation_framework import PRIMARY_METRIC

HERE = Path(__file__).resolve().parent
DEFAULT_RESULTS_CSV = HERE / "results" / "hw3_experiment.csv"


def load_scores(path: Path) -> Tuple[np.ndarray, List[str], Dict[str, List[float]], List[MutableMapping[str, str]]]:
    composites: List[float] = []
    labels: List[str] = []
    by_prompt: Dict[str, List[float]] = defaultdict(list)
    raw_rows: List[MutableMapping[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_rows.append(row)
            comp = row.get(PRIMARY_METRIC, "")
            lbl = row.get("prompt_label", "").strip().upper()
            if comp == "" or lbl == "":
                continue
            try:
                y = float(comp)
            except ValueError:
                continue
            if math.isnan(y):
                continue
            composites.append(y)
            labels.append(lbl)
            by_prompt[lbl].append(y)
    return np.asarray(composites, dtype=float), labels, dict(by_prompt), raw_rows


def one_way_anova(groups: Mapping[str, Sequence[float]]) -> Tuple[float, float]:
    arrays = [np.asarray(vals, dtype=float) for vals in groups.values() if len(vals) > 1]
    if len(arrays) < 2:
        return float("nan"), float("nan")
    f_stat, p_value = st.f_oneway(*arrays)
    return float(f_stat), float(p_value)


def pairwise_welch(groups: Mapping[str, Sequence[float]], keys: List[str]) -> List[Tuple[str, str, float, float]]:
    pairs: List[Tuple[str, str, float, float]] = []
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            a = np.asarray(groups.get(keys[i], []), dtype=float)
            b = np.asarray(groups.get(keys[j], []), dtype=float)
            if a.size < 2 or b.size < 2:
                continue
            tw = st.ttest_ind(a, b, equal_var=False, nan_policy="omit")
            pairs.append((keys[i], keys[j], float(tw.statistic), float(tw.pvalue)))
    return pairs


def bonferroni_adjust(pvals: Iterable[float], m: int) -> List[float]:
    return [min(1.0, float(p) * m) for p in pvals]


def ols_dummy_regression(y: np.ndarray, prompt_labels: List[str]) -> Dict[str, Any]:
    """
    y ~ 1 + I(B) + I(C) + ... with first sorted label as reference category.
    Returns R^2, coef dict, and sigma hat.
    """
    if y.size == 0:
        return {}
    uniq = sorted(set(prompt_labels))
    if len(uniq) < 2:
        return {"note": "Need ≥2 prompt levels for regression."}
    ref = uniq[0]
    k = len(uniq) - 1
    n = y.size
    X = np.ones((n, 1 + k), dtype=float)
    col = 1
    active: List[str] = []
    for label in uniq[1:]:
        X[:, col] = np.array([1.0 if pl == label else 0.0 for pl in prompt_labels], dtype=float)
        active.append(label)
        col += 1
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(n - X.shape[1], 1)
    rss = float(resid.T @ resid)
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - rss / tss if tss > 0 else 0.0
    sigma2 = rss / dof
    cov = sigma2 * np.linalg.inv(X.T @ X)
    se = np.sqrt(np.clip(np.diag(cov), 0.0, np.inf))
    t_stats = beta / se
    p_vals = 2.0 * (1.0 - st.t.cdf(np.abs(t_stats), df=dof))

    out: Dict[str, Any] = {
        "n": float(n),
        "r_squared": float(r2),
        "sigma_hat": float(math.sqrt(sigma2)),
        "reference_prompt": ref,
        f"beta_intercept": float(beta[0]),
        f"se_intercept": float(se[0]),
        f"t_intercept": float(t_stats[0]),
        f"p_intercept": float(p_vals[0]),
    }
    for i, lbl in enumerate(active, start=1):
        out[f"beta_vs_{ref}_{lbl}"] = float(beta[i])
        out[f"se_vs_{ref}_{lbl}"] = float(se[i])
        out[f"t_vs_{ref}_{lbl}"] = float(t_stats[i])
        out[f"p_vs_{ref}_{lbl}"] = float(p_vals[i])
    return out


def qualitative_tag_summary(rows: List[Mapping[str, str]], top_n: int = 12) -> str:
    by_prompt_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        lbl = (row.get("prompt_label") or "").strip().upper()
        blob = row.get("thematic_tags", "") or ""
        if not lbl or not blob.strip():
            continue
        for tag in [t.strip() for t in blob.split(";") if t.strip()]:
            by_prompt_counts[lbl][tag] += 1
    lines: List[str] = []
    for lbl in sorted(by_prompt_counts.keys()):
        lines.append(f"[{lbl}] thematic tag counts (truncated)")
        for tag, c in by_prompt_counts[lbl].most_common(top_n):
            lines.append(f"  {tag}: {c}")
    return "\n".join(lines)


def summarize(path: Path) -> str:
    y, lbls, by_prompt, raw_rows = load_scores(path)
    keys = sorted(by_prompt.keys())
    lines = [
        "Homework 3 — Statistical analysis summary",
        f"CSV: {path}",
        f"Rows with numeric {PRIMARY_METRIC}: {y.size}",
        "",
        "Per-prompt counts and means:",
    ]
    for k in keys:
        arr = np.asarray(by_prompt[k], dtype=float)
        lines.append(f"  {k}: n={arr.size}, mean={arr.mean():.3f}, sd={arr.std(ddof=1):.3f}")

    lines.append("")
    f_val, p_ova = one_way_anova(by_prompt)
    lines.append(f"One-way ANOVA on {PRIMARY_METRIC}: F={f_val:.5f}, p={p_ova:.5g}")

    pairs = pairwise_welch(by_prompt, keys)
    m = len(pairs) if pairs else 1
    lines.append("")
    lines.append(f"Pairwise Welch t-tests (Bonferroni multiplier m={m}):")
    adj = bonferroni_adjust((p for _, _, _, p in pairs), m=m) if pairs else []
    for (la, lb, tstat, raw_p), pb in zip(pairs, adj):
        lines.append(
            f"  {la} vs {lb}: t={tstat:+.4f}, p_raw={raw_p:.5g}, p_bonf={pb:.5g}"
        )

    lines.append("")
    lines.append("OLS dummy regression (reference = first sorted prompt label):")
    reg = ols_dummy_regression(y, lbls)
    for rk, rv in sorted(reg.items(), key=lambda kv: kv[0]):
        if isinstance(rv, float):
            lines.append(f"  {rk}: {rv:.6g}")
        else:
            lines.append(f"  {rk}: {rv}")

    lines.append("")
    lines.append("Qualitative tag rollup (AI reviewer coding):")
    lines.append(qualitative_tag_summary(raw_rows))

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--csv",
        default=str(DEFAULT_RESULTS_CSV),
        help=f"Path to experiment CSV (default: {DEFAULT_RESULTS_CSV})",
    )
    ap.add_argument("--text-out", default="", help="Optional path to write summary text")
    args = ap.parse_args()
    p = Path(args.csv).expanduser()
    if not p.is_file():
        raise SystemExit(
            f"CSV not found: {p}\n"
            "Run `python run_experiment.py` first, or pass an existing file: "
            "`python analyze_results.py --csv path/to/your.csv`"
        )
    text = summarize(p)
    print(text)
    if args.text_out:
        outp = Path(args.text_out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(text + "\n", encoding="utf-8")
        print(f"\nWrote summary → {outp}")


if __name__ == "__main__":
    main()
