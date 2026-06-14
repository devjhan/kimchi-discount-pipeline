# cutoff_rules Grammar — policy-profiler

`cutoff_rules`는 `screener` 패키지 `RuleFactory`가 소비 가능한 dict-tree 문법만 허용.

## metric_path 화이트리스트 (환각 차단 — 필수 참조)

- `governance/policy/methods_manifest.yaml` — **코드 SSoT 에서 생성되는** resolver metric_path /
  rule_type / op 화이트리스트 (ADR-0014). 생성: `python -m applications.gen_methods_manifest`.
  `test_methods_manifest_sync` arch test 가 코드↔파일 동기를 강제하므로 본 파일은 항상 실재·최신.
  (whitelist 실체는 `domains/screener/rules/resolver.py` / `factory.py` / `leaf.py` 코드이며,
  manifest 는 그 투영이다.)
- `domains/screener/.guidelines/01-rules.md` — Rule 트리 문법 (type/op/metric_path)
- `domains/screener/.guidelines/02-resolver.md` — resolver 소비 인터페이스
- `domains/_shared/profile_registry/schema.py` — `EnrichCutoffProfile` 필드 계약

> resolver가 소비 불가능한 path = 환각. ADR-0014 부터는 `python -m domains.policy.main --commit-draft`
> 가 strict validator(manifest 대조)로 commit 시점에 **결정론적으로 reject** 한다 (구: screener
> 로드 시점 silent caution). 본 스킬이 애초에 화이트리스트 밖 path/op/type 을 쓰지 않는 것이 1차 방어.

## 유효 type enum

`type` 필드는 다음 값만 허용 (manifest `rule_types`, RuleFactory dispatch SSoT):
`and` | `or` | `not` | `threshold` | `scoring` | `weighted_sum` | `signal_presence` | `profile_ref`

> per-ticker/segment cutoff 는 보통 `and`/`threshold`/`signal_presence` 로 충분.
> `scoring`/`weighted_sum` 은 가중 점수 합산이 필요한 고급 케이스용.

## 유효 op (threshold)

`threshold` 노드 `op` 는 `ge` | `le` | `gt` | `lt` | `eq` 만 (manifest `threshold_ops`).
**`ne` 는 cutoff 에서 불가** — selector(멤버십)에서만 합법. floor/ceiling 의미상 != 가 무의미.

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
5. `governance/policy/methods_manifest.yaml` (cutoff_rules 어휘 — 코드 SSoT 생성물, ADR-0014; whitelist 실체는 `domains/screener/rules/resolver.py` / `factory.py` / `leaf.py` 코드)
6. `domains/_shared/profile_registry/schema.py` (출력 shape)
7. `_intake-{date}.json` (trigger + 현 profile)
8. `$EXTERNAL_SIGNAL_INTAKE_DIR/{ticker_dir}/*.md` (evidence)
9. 본 SKILL.md

> `ticker_dir` = ticker의 `:` → `_` 치환 (예: `KR:005930` → `KR_005930`)
