# Self-Validation — policy-profiler

draft write 직전 MANDATORY 체크리스트:

1. `_intake-{date}.json` 의 trigger/current_profile 을 읽었는가?
2. cutoff_rules 의 모든 `metric_path` 가 methods_manifest 화이트리스트 안인가?
3. cutoff_rules 의 모든 `type` 이 유효 enum (and/or/not/threshold/signal_presence/profile_ref) 인가?
4. 모든 수치 임계에 G7 citation 이 붙었는가? (지어낸 숫자 0)
5. `required_enrichments` 가 universe enricher registry 에 존재하는 name 인가?
6. drift/version/provenance/commit 을 본 스킬이 계산/수행하지 *않았는가*? (F-10)
7. `rationale_ko` 에 forbidden language (should buy/sell, guaranteed, alpha confirmed 등) 없는가?
8. 출력 경로가 `_profile-draft-{date}.json` (또는 `.{N}.json`) 인가?
9. secret env 값 노출 없는가?

NO 하나라도 있으면 중단 + 누락 보고.
