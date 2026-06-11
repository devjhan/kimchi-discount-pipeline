# Config — Schema + Version YAML

## 공통 헤더 (D-CFG-1 준수)

```yaml
schema: "catalyst-detectors-v1"
version: 1
description: "한 줄 한국어 설명"
last_updated: "YYYY-MM-DD"
```

## 파일 카탈로그

| 파일 | schema | 역할 | 로더 |
|---|---|---|---|
| `detectors.yaml` | `catalyst-detectors-v1` | 활성 detector 목록 + per-detector spec | `_boundary.load_detectors_config()` |

**Sub-config / `_ref` 패턴 없음** — catalyst config 는 `detectors.yaml` 단일 inline.

## Detector spec 패턴

```yaml
- type: "type_name"      # DETECTOR_TYPES 에 등록된 키 (필수)
  name: "instance_name"  # 인스턴스 식별자 (필수)
  enabled: true          # false 면 build 되되 orchestrator 가 skip
  # ... type-specific spec (from_spec() 파싱)
```

`build_detector` 가 `type` / `name` 키 부재 시 `ValueError` → config_build blocking.

## 실행 순서 = 리스트 순서 (byte-parity 고정)

`detectors:` 리스트 순서가 detector 실행 순서이고, `augment_d_type_into_primary` 의 ticker grouping 이 insertion order 에 의존. 현재 순서 (`treasury → spin_off → activist → index → earnings → nav`) 를 고정 — 변경 시 `test_catalyst_golden.py` 회귀.

## thresholds.yaml 와의 책임 분리

- `governance/thresholds.yaml` — cross-cutting (sizing / statistics / forbidden_language / macro)
- `domains/catalyst/config/detectors.yaml` — **stage 3 전용** detector 목록 + spec

## schema bump 규약

- backward-incompatible → `catalyst-detectors-v1` → `v2`
- additive (옵셔널 필드 / 새 detector entry) → `version` 만 bump
- 출력 envelope schema (`investment-stage3-catalyst-events-v1`) 는 payload shape 변경 시 bump
