# Output JSON Schema — stage2-quality-lens

경로: `$TRAIL_TODAY/02-quality-lens.json`

```json
{
  "schema": "stage2-quality-lens-v1",
  "generated_at": "...",
  "date": "2026-05-04",
  "stage2_helper_input": "$TRAIL_TODAY/02-quality-filter.json",
  "stats": {
    "total_evaluated": 12,
    "by_overall_lens_score": {"strong": 2, "neutral": 7, "weak": 3, "insufficient_evidence": 0}
  },
  "evaluations": [
    {
      "ticker": "KR:003550",
      "name": "LG",
      "helper_verdict": "pass",
      "lenses": {
        "moat": {
          "score": "strong",
          "rationale": "...",
          "evidence_citations": ["DART@2026-04-30={rcept_no:..., section:'사업의 내용'}"],
          "evidence_status": "complete"
        },
        "capital_allocation": { ... },
        "accounting_red_flags": { ... },
        "subsidiary_attractiveness": { ... }
      },
      "overall_lens_score": "strong",
      "lens_concerns_for_thesis": []
    }
  ],
  "warnings": []
}
```

## `overall_lens_score` enum

- `strong` | `neutral` | `weak` | `insufficient_evidence`
- 4 lens 중 1+ score=`weak` 이면 overall=`weak` (보수적 가산).
- 모든 lens score=`insufficient_evidence` 이면 overall=`insufficient_evidence`.
- `weak` lens는 Stage 4 thesis-auditor 입력의 `lens_concerns_for_thesis` 배열에 reference id로 전달 — Stage 4가 thesis edge_source 평가 시 추가 검증 사용.
