# Config — Schema + Version YAML, Sub-config 분리

## 공통 헤더 (D-CFG-1 준수)

```yaml
schema: "universe-{kind}-v{N}"
version: N
description: "한 줄 한국어 설명"
last_updated: "YYYY-MM-DD"
```

## 파일 카탈로그

| 파일 | schema | 역할 | 로더 |
|---|---|---|---|
| `sources.yaml` | `universe-sources-v1` | 활성 source 목록 (6 entry) | `_boundary.load_sources_config()` |
| `enrichers.yaml` | `universe-enrichers-v1` | 활성 enricher 목록 (2 entry) | `_boundary.load_enrichers_config()` |
| `manual_additions.yaml` | `universe-manual-additions-v1` | LiteralListSource items | `_boundary.load_sub_config()` |
| `subsidiaries.yaml` | `universe-subsidiaries-v1` | 지주사 자회사 SSoT | `_boundary.load_sub_config()` |
| `preferred_pairs.yaml` | `universe-preferred-pairs-v1` | 우선주 페어 SSoT | `_boundary.load_sub_config()` |
| `exclusions.yaml` | `universe-exclusions-v1` | ticker 단위 제외 set | `_boundary.load_sub_config()` |

## Sub-config 분리 원칙

큰 데이터 mapping 은 별도 yaml 로 분리. 메인 config 는 `xxx_ref: "filename.yaml"` 형식으로 참조. 근거: ① 메인 config 가독성 ② diff noise 감소 ③ 데이터 SSoT 가 source/enricher 양쪽 공유.

`_boundary.load_sub_config(filename)` 은 path traversal 방어 (`"/"` / `".."` 거부).

## Source spec 패턴

```yaml
- type: "type_name"        # SOURCE_TYPES registered key
  name: "instance_name"    # 식별자
  source_category: "..."   # emit 하는 UniverseEntry 의 source_category
  # ... type-specific 필드 (from_spec() 파싱)
```

## Enricher spec 패턴

```yaml
- type: "type_name"        # ENRICHER_TYPES registered key
  name: "instance_name"    # 식별자
  applies_to: ["source_cat_1", "source_cat_2"]
  # ... type-specific 필드
```

## thresholds.yaml 와의 책임 분리

- `governance/thresholds.yaml` — cross-cutting (sizing, statistics, forbidden_language, macro, catalyst)
- `domains/universe/config/*.yaml` — stage 1 전용 데이터

## Schema bump 규약

- backward-incompatible → `v1` → `v2`
- additive (옵셔널 필드 추가) → `version` 만 bump
- 새 source/enricher entry 추가는 `version` bump
