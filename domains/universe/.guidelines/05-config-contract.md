# Config — Schema + Version YAML, Sub-config 분리

## 공통 헤더 (D-CFG-1 준수)

모든 config YAML 은 다음 4 필드 필수:

```yaml
schema: "universe-{kind}-v{N}"
version: N
description: "한 줄 한국어 설명"
last_updated: "YYYY-MM-DD"
```

`block_anti_patterns/D-CFG-1` hook 이 `schema` / `description` / `version` 부재 시 Write 차단.

## 파일 카탈로그 (Run 6 시점)

| 파일 | schema | 역할 | 로더 |
|---|---|---|---|
| `sources.yaml` | `universe-sources-v1` | 활성 source 목록 (6 entry) | `_boundary.load_sources_config()` |
| `enrichers.yaml` | `universe-enrichers-v1` | 활성 enricher 목록 (2 entry) | `_boundary.load_enrichers_config()` |
| `manual_additions.yaml` | `universe-manual-additions-v1` | LiteralListSource items | `_boundary.load_sub_config("manual_additions.yaml")` |
| `subsidiaries.yaml` | `universe-subsidiaries-v1` | 지주사 자회사 SSoT (NavDiscount + HoldingCompanySource 공유) | `_boundary.load_sub_config("subsidiaries.yaml")` |
| `preferred_pairs.yaml` | `universe-preferred-pairs-v1` | 우선주 페어 SSoT (PreferredShareSeedSource + SpreadZScore 공유) | `_boundary.load_sub_config("preferred_pairs.yaml")` |
| `exclusions.yaml` | `universe-exclusions-v1` | ticker 단위 제외 set | `_boundary.load_sub_config("exclusions.yaml")` |

## Sub-config 분리 원칙

큰 데이터 mapping (subsidiaries, preferred_pairs, manual_additions, exclusions) 은 별도 yaml 로 분리. 메인 config (sources.yaml / enrichers.yaml) 는 `xxx_ref: "filename.yaml"` 형식으로 참조.

근거:
1. 메인 config 가독성 + diff noise 감소
2. 사용자 data 갱신 (subsidiaries 추가, manual_additions 등) 시 메인 manifest 미수정
3. 데이터 SSoT 가 source / enricher 양쪽 모두에서 같은 파일을 read (e.g., subsidiaries.yaml — HoldingCompanySource + NavDiscountEnricher 공유)

`_boundary.load_sub_config(filename)` 는 path traversal 방어:
```python
if "/" in filename or ".." in filename:
    raise ValueError(...)
```

## thresholds.yaml 와의 책임 분리

- `governance/thresholds.yaml` — **cross-cutting 정량 임계값** (sizing, statistics, forbidden_language, macro, catalyst 등) — 여러 stage 가 참조하는 systemic config
- `domains/universe/config/*.yaml` — **stage 1 universe 전용 데이터** (sources / enrichers / manual SSoT) — universe bounded context 가 단독 read

drift 방지: thresholds.yaml 의 `universe` 키는 2026-05-17 (Run 5 완료) 시점 완전 제거. universe 관련 config 는 자동으로 본 패키지에 한정.

## Config 변경 시 schema bump 규약

- backward-incompatible 변경 (필드 삭제 / 의미 변경 / type 변경) → `schema: universe-{kind}-v1` → `v2`
- additive 변경 (옵셔널 필드 추가) → `version` 만 bump (1 → 2)
- 새 source / enricher entry 추가는 `version` bump (실 사례: sources.yaml v1 → v2 (Run 3) → v3 (Run 5))

## Source spec 패턴

`sources.yaml.sources[]` 의 한 entry:

```yaml
- type: "type_name"        # SOURCE_TYPES 에 등록된 키
  name: "instance_name"    # 인스턴스 식별자 (warning / audit log 에 표기)
  source_category: "..."   # emit 하는 UniverseEntry 의 source_category
  # ... type-specific 필드 (from_spec() 가 파싱)
```

공통 옵셔널:
- `items_ref` / `subsidiaries_map_ref` / `pairs_ref` — 외부 yaml 참조 (`_boundary.load_sub_config` 로 로드)

## Enricher spec 패턴

`enrichers.yaml.enrichers[]` 의 한 entry:

```yaml
- type: "type_name"            # ENRICHER_TYPES 에 등록된 키
  name: "instance_name"        # 인스턴스 식별자
  applies_to: ["source_cat_1", "source_cat_2"]  # frozenset 으로 변환됨
  # ... type-specific 필드
```

## 신규 config 파일 추가 절차

1. `config/{filename}.yaml` 신설 — 공통 헤더 + 본문
2. `_boundary.py` 에 dedicated 로더 추가 (자주 사용되는 경우) 또는 `load_sub_config` 일반 로더 사용
3. 본 문서 (`05-config-contract.md`) 의 카탈로그 표 갱신
4. (필요 시) `README.md` 외부 연결점 표 갱신
