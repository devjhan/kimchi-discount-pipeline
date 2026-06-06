# D-CFG — Config / Text 산출물 작성 컨벤션

YAML, JSON, `.env`, Markdown 등 *텍스트 데이터* 산출물의 표준. `$GOVERNANCE_DIR` 의 yaml 들 + `$TRAIL_TODAY/*.json` 산출물이 모범.

---

## D-CFG-1 — `$GOVERNANCE_DIR/*.yaml` 헤더는 `version:` + `description:` 강제

**근거**: governance yaml 은 SSoT. 어떤 schema/version 의 정의인지 본문 첫 5 줄 안에 명시되어야 다른 yaml / 코드와 cross-reference 가능. `$TOPOLOGY_PATH` 와 `$THRESHOLDS_PATH` 가 모범.

❌ 금지 (헤더 5 줄 내 둘 다 없음)
```yaml
paths:
  governance: "governance"
  ...
```

✅ 올바름
```yaml
version: "1.1"
description: "Investment Advisory Agent Workspace Topology — single source of truth for all directory aliases"

# --------------------------------------------------------------------------
# 모든 path 는 repo root 기준 상대경로.
# --------------------------------------------------------------------------
paths:
  ...
```

**Hook**: `block_anti_patterns.sh` (PreToolUse) — `$GOVERNANCE_DIR/*.yaml` 새 파일 Write 시 헤더 5 줄 내 `version:` / `description:` 둘 다 부재면 exit 2.

---

## D-CFG-2 — JSON 산출물 envelope 필수 필드

**근거**: `$TRAIL_TODAY/0X-*.json` 의 모든 stage 산출물은 cross-stage 인용 + audit. envelope 표준이 있어야 brief author / shadow portfolio / process audit 이 일관 read.

✅ 표준 envelope
```json
{
  "schema": "stage3-catalyst-v1",
  "generated_at": "2026-05-12T05:42:11+09:00",
  "date": "2026-05-12",
  "config_version": "thresholds-1.4",
  "warnings": [],
  "items": [ ... ]
}
```

필수 5 필드: `schema`, `generated_at` (ISO + KST), `date` (YYYY-MM-DD), `config_version`, `warnings` (빈 list OK).

❌ 금지: 위 5 필드 중 1 개라도 누락된 `$TRAIL_TODAY/*.json` write.

**Hook**: `lint_directives.sh` (PostToolUse, M1 dry-run) — `$TRAIL_TODAY/*.json` 경로 Write 시 envelope 필드 검사. 누락 시 audit log + (M2) additionalContext.

---

## D-CFG-3 — YAML 들여쓰기 2 칸, 탭 금지

**근거**: PyYAML 의 `safe_load` 는 들여쓰기 변동을 허용하지만, doctrine_lint / 사용자 vim diff 비교 시 노이즈. 모든 governance yaml + user_context yaml 은 2 칸 space 만.

❌ 금지: 들여쓰기 4 칸, 탭 사용, 같은 파일에서 2 / 4 칸 혼용.

✅ 올바름: 2 칸 space (기존 `$TOPOLOGY_PATH` 직역).

**Hook**: `lint_directives.sh` (PostToolUse, M2) — `.yaml` 새 작성 시 들여쓰기 검사.

---

## D-CFG-4 — Markdown 산출물의 숫자는 citation 의무

**근거**: G7 의 directive 평면 직역. brief / audit report 같은 markdown 산출물에 등장하는 모든 숫자는 helper 산출 인용 형식 `SRC@ISO_TS=VALUE` 또는 `omitted (reason)` 처리.

❌ 금지
```markdown
오늘 macro regime 은 mid-cycle (cash band 30%).
```

✅ 올바름
```markdown
오늘 macro regime 은 mid-cycle (cash band 30% — STAGE0@2026-05-12T05:30+09:00=mid).
```

**Hook**: `brief_citation_gate.sh` (기존, PostToolUse + Stop) — `daily-brief.md` 한정 검사.

---

## D-CFG-5 — `.env` / secret 파일은 본문 직접 인용 절대 금지

**근거**: `$ENV_PATH` 의 내용은 secret. doctrine 본문 / hook stderr / log 어디에도 `KIS_APP_KEY=PSxxxx` 같은 substring 직접 등장 안 됨. `secret_safe_log()` (infra/_common/utils) 가 redact 표준.

❌ 금지
```python
print(f"loaded KIS_APP_KEY={os.environ['KIS_APP_KEY']}")  # secret leak
```

✅ 올바름
```python
from infrastructure._common.utils import secret_safe_log
secret_safe_log("loaded KIS_APP_KEY", os.environ)  # KIS_APP_KEY 자동 redact
```

**Hook**: `pre_env_guard.sh` (기존, PreToolUse) — Read/Bash/Write/Edit 의 `$ENV_PATH` 직접 접근 차단.

---

## D-CFG-6 — Markdown forbidden language (G19 직역)

**근거**: brief / process audit / daily output 등 사람 눈에 가는 markdown 본문에 등장 시 자동 reject 되는 phrase 목록. 본 directive 는 G19 의 directive-tier 인용 — D-CFG-6 위반은 G19 위반과 동치.

❌ 금지 phrase (sample): `"should buy"`, `"guaranteed"`, `"no-brainer"`, `"alpha confirmed"`, `"outperformed the market"` (sample size 미충족 시).

전체 목록: `$SPECS_DIR/hard-guards.md` Section 3.

**Hook**: `brief_citation_gate.sh` (기존, PostToolUse + Stop) — `daily-brief.md` 한정.
