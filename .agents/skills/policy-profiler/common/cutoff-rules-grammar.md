# cutoff_rules Grammar — policy-profiler

`cutoff_rules`는 `screener` 패키지 `RuleFactory`가 소비 가능한 dict-tree 문법만 허용.

## metric_path 화이트리스트 (환각 차단 — 필수 참조)

- `governance/policy/global/methods_manifest.yaml` — resolver metric_path 화이트리스트 참조 경로 (whitelist 실체는 `domains/screener/rules/resolver.py` / `methods.py` 코드에 있음)
- `domains/screener/.guidelines/01-rules.md` — Rule 트리 문법 (type/op/metric_path)
- `domains/screener/.guidelines/02-resolver.md` — resolver 소비 인터페이스
- `domains/_shared/profile_registry/schema.py` — `EnrichCutoffProfile` 필드 계약

> resolver가 소비 불가능한 path = 환각 → phase 3가 screener 로드 시 caution으로 격리되지만, 본 스킬이 애초에 화이트리스트 밖 path를 쓰지 않는 것이 1차 방어.

## 유효 type enum

`type` 필드는 다음 값만 허용: `and` | `or` | `not` | `threshold` | `signal_presence` | `profile_ref`

## Reference contract for cutoff_rules writing

- `metric_path`는 methods_manifest 화이트리스트 경로만
- `type`은 유효 enum 값만
- 모든 수치 임계에 G7 citation (`{SOURCE}@{ts}={value}`)
- evidence 없는 임계값 지어내기 금지

## Source of Truth Hierarchy

1. 사용자 명시적 결정
2. `AGENTS.md` (5 철학)
3. `$AXIOMS_DIR/**/*.md`
4. `$SPECS_DIR/hard-guards.md`
5. `governance/policy/global/methods_manifest.yaml` (cutoff_rules 어휘 — whitelist 실체는 `domains/screener/rules/resolver.py` / `methods.py` 코드)
6. `domains/_shared/profile_registry/schema.py` (출력 shape)
7. `_intake-{date}.json` (trigger + 현 profile)
8. `$EXTERNAL_SIGNALS_DIR/{ticker_dir}/*.md` (evidence)
9. 본 SKILL.md

> `ticker_dir` = ticker의 `:` → `_` 치환 (예: `KR:005930` → `KR_005930`)
