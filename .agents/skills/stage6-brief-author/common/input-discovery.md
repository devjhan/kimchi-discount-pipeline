# Input Discovery — Stage 6 Input Sources & Pre-flight Validation

Daily brief 작성을 위해 Stage 0~5 + positions의 산출물을 우선순위로 수집한다. input 누락은 fatal이 아님 — 가능한 섹션만으로 brief 작성. 모든 input 누락 시에만 즉시 중단 (Mode C).

---

## Inputs Table (priority order)

| 우선순위 | 경로 | 누락 시 |
|---|---|---|
| 1 | `$TRAIL_TODAY/00-macro-regime.json` | brief의 macro 섹션 omit + warning |
| 2 | `$TRAIL_TODAY/00-macro-regime-narrative.md` (옵션) | 본문 narrative 자체 작성 (regime label만) |
| 3 | `$TRAIL_TODAY/01-universe.json` | universe 섹션 omit |
| 4 | `$TRAIL_TODAY/02-quality-filter.json` | quality 섹션 omit |
| 5 | `$TRAIL_TODAY/02-quality-lens.json` (옵션) | 정성 lens 섹션 omit |
| 6 | `$TRAIL_TODAY/03-catalyst-events.json` | catalyst 섹션 omit |
| 7 | `$TRAIL_TODAY/04-thesis-candidates.json` | thesis 섹션 omit |
| 8 | `$TRAIL_TODAY/05-sizing-recommendation.json` | 사이즈 섹션 omit (G12 사용자 portfolio context 미입력 시 자연스럽게 omit) |
| 9 | `$POSITIONS_DIR/{ticker}/drift-{date}.md` (per held position) | 보유 포지션 drift 섹션 skip |
| 10 | `$TRAIL_TODAY/event-trigger-status-{date}.json` (옵션) | event_trigger falsifier 소섹션 omit |
| 11 | `$POSITIONS_DIR/_summary-{date}.json` (옵션, positions_sync 산출) | Holdings Snapshot 섹션 omit (KIS 정책 비활성/계좌 미설정 시 자연스럽게 omit) |

---

## Pre-flight: Input Validation

brief 본문 작성 전 반드시 `validate_stage_inputs()` 를 호출해 input stage 산출물을 검사한다.

### validate_stage_inputs 호출

```bash
python3 - <<'PY'
import os, json
from pathlib import Path
from domains._shared.brief_gate.validators import validate_stage_inputs
trail = Path(os.environ["TRAIL_TODAY"])
merged, vio = validate_stage_inputs(trail)
print(json.dumps({"violations": vio, "stage_count": sum(1 for v in merged.values() if v)}, ensure_ascii=False, indent=2))
PY
```

검사 항목:
- G7 envelope: 모든 숫자에 source citation 있는지
- Stage 5 cap_violations: sizing guard 위반 검출
- Schema mismatch: 각 stage 산출물의 schema valid 여부

violations 가 있으면 본문 'Pipeline Health' 섹션에 violation list 첨부.

### brief_citation_gate.sh Hook

본 skill의 brief 작성 후 `PostToolUse`/`Stop` hook (`brief_citation_gate.sh`) 가 독립적으로:
1. 동일한 `validate_stage_inputs` validator 호출
2. 본문 unsourced number 정규식 검사
3. forbidden wording substring 검사

수행 후 violation 시 block + LLM rewrite 강제. 본 skill은 hook 차단을 만나면 violation list를 그대로 본문에 반영해 재시도한다.
