# Validator (compact) — same JSON contract as full rubric

Baseline JSON is authoritative. Score the report; no contradictions or invented facts.

**Scales**

- `evidence_alignment_index` 0–100 (claims trace to baseline; 72+ is “pass band” in code)
- `coverage_of_baseline_facets` 0–100 (facets surfaced; 65+ pass band)
- `clarity_tier` 1–4 (1=opaque … 4=clear)
- `instructional_usefulness_band` 1–7 (1=low … 7=high leverage)
- `mislearning_risk_ordinal` 0–3 (0=none … 3=severe; ≤1 pass band)

**Tags** — pick 3–6 from:
`FAITHFUL_PHON`, `PRON_GAPS`, `DEF_INCOMPLETE`, `HALLUCINATION`, `OVERCONFIDENT`, `JARGON_HEAVY`, `NOVICE_FRIENDLY`, `ACTIONABLE_COACH`, `STRUCTURED_FORMAT`, `RAMBLING`, `SCOPE_TRIM`, `TONE_CALIBRATION_OK`

`qualitative_note`: ≤80 words, cite baseline vs report.

Return **only** JSON:

```json
{
  "evidence_alignment_index": 0,
  "coverage_of_baseline_facets": 0,
  "clarity_tier": 1,
  "instructional_usefulness_band": 1,
  "mislearning_risk_ordinal": 0,
  "thematic_tags": ["NOVICE_FRIENDLY"],
  "qualitative_note": "..."
}
```
