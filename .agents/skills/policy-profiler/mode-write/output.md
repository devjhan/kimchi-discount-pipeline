# Mode A — Draft 작성

## 조건

- `_intake-{date}.json` 존재 + methods_manifest / profile schema read 가능
- cutoff_rules 가 화이트리스트 metric_path + 유효 type 만 사용

## 절차

1. `_intake-{date}.json` read → trigger + current_profile (null=신규, 있음=amendment)
2. `$EXTERNAL_SIGNAL_INTAKE_DIR/{ticker_dir}/*.md` evidence read (fact-only, G10)
3. `required_enrichments` 제안 (universe enricher registry 존재 name만)
4. `cutoff_rules` 제안 (methods_manifest 화이트리스트 metric_path만)
5. citations: G7 형식 — evidence 없는 임계값 지어내기 금지
6. `rationale_ko`: "왜 시장이 틀렸나" inverse question + falsifier 지향 (forbidden language 금지)
7. `_profile-draft-{date}.json` write (기존 파일 시 `.{N}.json` — G20)

## 산출

- `$POLICY_DRAFTS_DIR/{ticker_dir}/_profile-draft-{date}.json`

## 후속

draft 만족 시 `python -m domains.policy.main --commit-draft <draft>` (phase 3 결정론)
