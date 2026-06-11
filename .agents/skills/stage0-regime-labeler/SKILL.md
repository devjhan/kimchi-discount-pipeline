---
name: stage0-regime-labeler
description: Investment 파이프라인 Stage 0의 옵셔널 LLM narrative labeler. stage0-macro-regime.py helper가 산출한 deterministic regime 분류(early/mid/late/crisis/unknown)에 자연어 narrative와 cycle context를 부여한다. helper의 numeric 분류는 절대 변경하지 않고, 보조 narrative만 추가 산출 ($TRAIL_TODAY/00-macro-regime-narrative.md). 사이즈/매매 권고 일체 금지.

---

# stage0-regime-labeler — Macro Regime Narrative Labeler

Stage 0 helper가 산출한 정량 regime 분류에 자연어 narrative context를 부여하는 보조 skill. helper의 deterministic 분류는 **절대 변경하지 않으며**, read-only로 인용만 한다.

## 선행 읽기

### 공통
1. `common/input-output.md` — 입력 산출물 + output artifact schema
2. `common/forbidden-language.md` — 금지 wording 목록
3. `common/self-validation.md` — 산출 전 MANDATORY 체크리스트

### 분기
- `mode-write/output.md` — 정상 narrative 작성 조건·절차
- `mode-skip/output.md` — indicator 부재 시 narrative 보류 조건
- `mode-block/output.md` — helper 산출물 누락 시 차단 조건·응답

## 핵심 불변식

1. **helper numeric 분류 불변** — `regime_decision`, `cash_band`, `indicators` 필드 변경 금지, 그대로 인용
2. **정량 재계산 금지 (G6)** — helper 미산출 숫자 / 새 forecast / 시장 view 추가 금지
3. **recommendation 금지** — "should buy/sell", 매매 권고, 사이즈 논의 일체 금지

## 산출물

- `$TRAIL_TODAY/00-macro-regime-narrative.md`

## Out of Scope

- regime classification 변경 (helper 책임) / portfolio sizing (Stage 5) / ticker-specific recommendation (Stage 4/5) / 미래 forecast·시장 timing (전체 시스템 방침)
