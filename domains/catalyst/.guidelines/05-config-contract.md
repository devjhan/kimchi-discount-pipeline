# Config — Schema + Version YAML

## 공통 헤더 (D-CFG-1 준수)

```yaml
schema: "catalyst-detectors-v1"
version: 1
description: "한 줄 한국어 설명"
last_updated: "YYYY-MM-DD"
```

`block_anti_patterns/D-CFG-1` hook 이 `schema` / `description` / `version` 부재 시 Write 차단.
`main.py` 는 `detectors_cfg.get("version", "unknown")` → envelope `config_version`,
`_boundary.config_path("detectors.yaml")` → envelope `config_path`.

## 파일 카탈로그

| 파일 | schema | 역할 | 로더 |
|---|---|---|---|
| `detectors.yaml` | `catalyst-detectors-v1` | 활성 detector 목록 + per-detector spec (threshold/lookback/enable); 구 `governance/thresholds.yaml:catalyst.*` 흡수 | `_boundary.load_detectors_config()` |

**Sub-config / `_ref` 패턴 없음** — catalyst config 는 `detectors.yaml` 단일 inline.
(universe 는 `items_ref` / `subsidiaries_map_ref` / `pairs_ref` 로 외부화하지만 catalyst 는
detector spec 이 작아 분리 불필요.)

## detector spec 패턴

`detectors.yaml.detectors[]` 의 한 entry:

```yaml
- type: "type_name"      # DETECTOR_TYPES 에 등록된 키 (필수)
  name: "instance_name"  # 인스턴스 식별자 — warning / audit 에 표기 (필수)
  enabled: true          # false 면 build 되되 orchestrator 가 skip
  # ... type-specific spec (from_spec() 파싱 — 01-detectors.md 참조)
```

`build_detector` 가 `type` / `name` 키 부재 시 `ValueError` → main.py config_build blocking.

## 실행 순서 = 리스트 순서 (byte-parity 고정)

`detectors:` 리스트 순서가 detector 실행 순서이고, `augment_d_type_into_primary` 의 ticker
grouping 이 insertion order 에 의존한다. `catalysts` 출력의 byte-호환을 위해 현재 순서
(`treasury → spin_off → activist → index → earnings → nav`) 를 고정 — 변경 시
`test_catalyst_golden.py` 회귀. 순서 변경이 필요하면 golden fixture 동시 갱신.

## thresholds.yaml 와의 책임 분리

- `governance/thresholds.yaml` — cross-cutting 정량 임계값 (sizing / statistics /
  forbidden_language / macro 등) — 여러 stage 가 read 하는 systemic config
- `domains/catalyst/config/detectors.yaml` — **stage 3 catalyst 전용** detector 목록 + spec
  — catalyst BC 가 단독 read. 구 `thresholds.yaml:catalyst.*` 는 본 파일로 이전 완료.

## schema bump 규약

- backward-incompatible 변경 (필드 삭제 / 의미 변경 / type 변경) → `catalyst-detectors-v1` → `v2`
- additive (옵셔널 필드 / 새 detector entry) → `version` 만 bump
- 출력 envelope schema (`investment-stage3-catalyst-events-v1`) 는 payload shape 변경 시 bump

## 신규 config 파일 추가 절차

1. `config/{filename}.yaml` 신설 — 공통 헤더 + 본문
2. `_boundary.py` 에 로더 추가 (또는 일반 로더 사용)
3. 본 문서 카탈로그 표 갱신
4. (필요 시) 패키지 `AGENTS.md` 갱신
