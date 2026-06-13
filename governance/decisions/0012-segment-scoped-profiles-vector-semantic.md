# ADR-0012 — Segment-scoped profile 계층 + 벡터 semantic 분류

`status: Accepted`
`date: 2026-06-12`
`refs: D-ARCH-1, D-ARCH-2, D-ARCH-4, 0004, 0006, 0008, domains/_shared/segment_registry/`

## Context

profile 계층이 두 극단만 존재했다 — per-ticker(`EnrichCutoffProfile`,
`governance/profiles/<ticker>/v<N>.yaml`) 와 whole-universe(screener `strategies/default.yaml`).
그 사이 **부분집합(sector 등 기준) 단위 profile** 이 없어, "지주사 가치주", "대형 우선주"
같은 부분집합에 enrich-cutoff 정책을 선언적으로 걸 방법이 없었다.

요구: 부분집합 기준을 (1) 선언적, (2) 계층적·합성적으로, (3) **rule-based(수치 속성)와
semantic-based(의미 분류)를 동급(co-equal)** 으로 구성. semantic 분류는 임베딩 **벡터**
유사도 기반.

## Decision

`domains/_shared/segment_registry/` 신규 공유 커널 (profile_registry 와 동급, bc-independent).

1. **Selector-only (1-b).** `segment` = *부분집합 selector* + *참조 정책(profile_ref)* +
   *명시적 merge_spec*. 멤버십과 정책 분리. selector leaf 는 `threshold`(선택 속성
   namespace, screener `metric_path` resolver 와 **분리** — 5-a)와 `semantic_similarity`
   (concept anchor cosine)가 동급. 합성은 `and|or|not`.
2. **Compositional merge, 명시적 (2-b/6-a).** 계층(parent) general→specific 정렬 +
   per-field 연산자(`required_enrichments: union|replace`, `cutoff_rules: and|or|replace`).
   동일 (depth, priority) 다중 매칭 → `MergeConflictError` (암묵 tie-break 금지).
3. **선언 SSoT = governance YAML (4-a).** `governance/segments/`, `governance/concepts/`
   (semantic anchor, 9-a manual SSoT), `governance/segment_profiles/`(named 정책).
4. **Semantic = 벡터 (10-a/11-b/12-a/13-a).** concept anchor 텍스트 + per-ticker 텍스트를
   원격 임베딩(`EmbeddingPort`, OpenAI-호환 `/embeddings`)으로 벡터화해 임베디드 벡터
   저장소(`sqlite-vec`, stdlib `sqlite3` 단일 파일)에 적재. 멤버십 = cosine ≥ threshold(or top-k).
5. **벡터 저장소 = telemetry (ADR-0008 정합).** 임베딩은 모델 버전 의존 → 동일 재생성
   불가 → *증거* → `telemetry/segments/vectors.sqlite`. scalar 선택 속성은 재생성 가능하나
   동일 파일 동거(13-a). `.cache/` 아님.
6. **ports & adapters (D-ARCH-4).** kernel 은 `EmbeddingPort` / `VectorIndexPort` Protocol
   에만 의존. concrete adapter(`infrastructure/embedding`, `infrastructure/vectorstore`)는
   primitive 만 반환하고 `domains` 를 import 하지 않는다(불변식 A). `_shared/adapters` 의
   `RemoteEmbeddingAdapter`(주입 transport) / `InMemoryVectorIndex` 가 계약을 구현.
7. **G8/G11 graceful degradation.** 임베딩 키 부재/오프라인 → semantic leaf UNKNOWN →
   3-값 논리상 비매칭 + warning. 의미 불명을 멤버로 *강제 생성하지 않는다*. 모든 semantic
   멤버십은 `EMBED@<ts>=<concept>:<score>` (G7 형식)으로 provenance 기록.
8. **소비는 opt-in flag.** screener/universe 가 `SegmentResolver.resolve(ticker)` 로 위임하되
   기본 OFF → 기존 동작 byte-parity. resolved 산출물은 `EnrichCutoffProfile` shape 재사용
   (ADR-0006).

## Consequences

- 신규 의존성: `sqlite-vec` (optional `semantic` extra, 고정 핀). 미설치 시 store 는 stdlib
  sqlite3 + brute-force cosine 로 정확 degrade (KR 특수상황 규모에 충분). 임베딩은 기존
  `requests`. client-server DB 미도입.
- bc-independence 는 `tests/architecture/test_segment_registry_purity.py` 가 고정.
- 벡터는 telemetry append → 모델 교체 시 재임베딩(text_hash/model staleness 키).
- 회사 텍스트의 제3자 임베딩 API 전송(10-a 사용자 결정) — 키는 `.env`, 본문/로그 미노출(G21).

## Alternatives considered

- **Segment-as-profile (1-a, 멤버십+정책 결합)** — 기각. selector-only 가 정책 재사용·분리
  관심사에 유리.
- **수기 label taxonomy 만 (벡터 없음)** — 기각. 사용자 핵심 요구가 벡터 기반 semantic 분류.
- **client-server 벡터DB(pgvector 등)** — 기각(제약). 임베디드(`sqlite-vec`)만.
- **벡터를 `.cache/`** — 기각. 모델 의존 재생성 불가 → telemetry 증거 (ADR-0008).

## Supersedes / Superseded-by

(없음)

## Implementation notes (2026-06-13)

설계 결정을 코드로 옮기며 확정/보강한 사항 (status: Accepted 유지):

- **벡터 저장소 = 일반 테이블 + `vec_distance_cosine` (vec0 미사용).** `sqlite-vec` 명세를
  실행 검증한 결과 `vec0` 가상테이블은 (a) 확장 미로드 시 `no such module: vec0` 로 *데이터
  판독 자체가 불가*, (b) 고정 차원 요구, (c) upsert/차원불일치 제약이 있다. 벡터는 telemetry
  의 *재생성 불가 증거*(결정 5)이므로 **항상 판독 가능**해야 한다 → raw float32 BLOB 를
  일반 테이블(`vectors`)에 보관하고, 유사도/KNN 은 명세가 1급으로 문서화한 "Manually with
  SQL scalar functions" 방식(`vec_distance_cosine`, `cosine_similarity = 1 - distance`)으로
  계산한다. 확장 미로드 시 동일 결과의 순수 Python cosine 으로 graceful fallback. 13-a 의
  정신("sqlite-vec 를 실제로 사용")을 충족하되 vec0 의 취약성을 회피. (`infrastructure/
  vectorstore/store.py`, `tests/unit/test_vector_store_sqlite.py` SQL↔Python parity 고정.)
- **소비 wiring 활성화 (opt-in, 기본 OFF parity).** screener/universe `main.py` 에
  `--use-segments` 추가 → `SegmentResolver.resolve(ticker)` 위임. screener 는 매칭 종목의
  cutoff 를 합성(미매칭 → 기존 default_rule), universe 는 required_enrichments 를 union.
  해소 실패(SegmentRegistryError/ProfileSchemaError)는 caution/graceful degrade.
- **벡터 인덱스 build entry.** `python -m domains.universe.segment_index_main` — universe
  trail 종목 + concept anchor 를 임베딩/scalar 적재. EMBEDDING_API_KEY 부재/dry-run →
  scalar 만 (rule-based 선택 계속).
- **DART "사업의 내용" source = best-effort.** `infrastructure.dart.fetch_business_content`
  + `DartTickerTextSource`(주입 fetch, 절대 raise 안 함). document.xml 본문 추출은 인코딩·
  포맷 비정형이라 **라이브 endpoint 미검증** — 합성 fixture 로 추출 로직만 고정. 운영 투입
  전 실제 보고서 검증 필요. 그 전까지는 `--texts-file` 수기 큐레이션이 1순위 source.
