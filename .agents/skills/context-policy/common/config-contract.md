# Config — committed profile artifact (local config 없음)

policy 는 **`config/*.yaml` 이 없다**. tunable 은 CLI flag + 모듈 상수뿐.

## Tunable

| "config" | 위치 | 값 | 역할 |
|---|---|---|---|
| `--drift-threshold` | `main.py` argparse | 0.5 | drift 상대 변동 한계 |
| `DRIFT_BLOCKS_COMMIT` | `domain/commit_gate.py` | `False` | warn↔block 단일 토글 |
| `SCHEMA_VERSION` | `_shared/profile_registry/schema.py` | `"enrich-cutoff-profile-v1"` | profile schema gate |
| `DART_API_KEY` | `.env` | (secret) | DART intake auth |

## Committed artifact schema

policy 가 소유하는 유일한 YAML "config" (= `governance/profiles/{ticker_dir}/v{N}.yaml`):

| on-disk key | dataclass field | 비고 |
|---|---|---|
| `schema` | `schema_version` | `enrich-cutoff-profile-v1` 고정 |
| `version` | `profile_version` | ticker 별 monotonic int ≥ 1 |
| `description` | `description` | D-CFG-1 헤더 미러 |
| `ticker` | `ticker` | `KR:NNNNNN` |
| `required_enrichments` | `required_enrichments` | enricher name 리스트 |
| `cutoff_rules` | `cutoff_rules` | screener Rule dict-tree, `type` 키 필수 |
| `provenance.*` | `Provenance.*` | committed_at / committed_by / trigger / citations / rationale_ko |

## D-CFG-1 공통 헤더

on-disk 포맷이 `schema` / `version` / `description` 을 top-level 에 두는 것은 config-header lint D-CFG-1 충족.

## Schema bump 규약

`SCHEMA_VERSION` 문자열 bump 시 미매칭 profile 전부 `serde.from_dict` 가 reject (migration gate). 호환 깔 때만 올림.

## Consumer 측 read (참고)

- universe — `required_enrichments` (`--use-profile-registry` flip 후; 현재 default OFF)
- screener — `cutoff_rules`; completeness gate 가 `required_enrichments` 역참조 (누락 시 `verdict="caution"`)
- 둘 다 `ProfileRegistry.load_latest` 로 읽기만 — policy 동기 호출 안 함 (out-of-band).
