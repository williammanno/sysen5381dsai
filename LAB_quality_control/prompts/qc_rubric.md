# Quality control criteria (aligned with dsai `02_ai_quality_control.R`)

Evaluate the **AI-generated report** against the **original data** (baseline JSON). The baseline is authoritative: the report must not contradict it or add unsupported claims.

## Boolean

- **accurate**: `true` if no part of the report misinterprets the baseline data; `false` if any misinterpretation, contradiction, or invented fact.

## Likert scales (1–5)

- **accuracy**: 1 = many problems interpreting the data vs. 5 = no misinterpretation of the data.
- **clarity**: 1 = confusing writing style vs. 5 = clear and precise.
- **relevance**: 1 = irrelevant commentary vs. 5 = relevant commentary about the data.

Use these **exact** key names (all lowercase): `accurate`, `accuracy`, `clarity`, `relevance`, `details`.

Return **only** valid JSON in this exact shape (integers 1–5, boolean for accurate):

```json
{
  "accurate": true,
  "accuracy": 5,
  "clarity": 5,
  "relevance": 5,
  "details": "0–80 word explanation referencing baseline vs. report."
}
```
