# Config — committed profile artifact (local config 없음)

policy 는 **`config/*.yaml` 이 없다** (universe 의 self-contained config 와 대조). tunable 은
CLI flag + 모듈 상수뿐:

| "config" | 위치 | 값 | 역할 | 로더 |
|---|---|---|---|---|
| `--drift-threshold` | `main.py` argparse | 0.5 (`_DEFAULT_DRIFT_THRESHOLD`) | drift 상대 변동 한계 | argparse |
| `DRIFT_BLOCKS_COMMIT` | `domain/commit_gate.py` | `False` | warn↔block 단일 토글 | 모듈 상수 |
| `SCHEMA_VERSION` | `_shared/profile_registry/schema.py` | `"enrich-cutoff-profile-v1"` | profile schema gate | 모듈 상수 |
| `DART_API_KEY` | `.env` | (secret) | DART intake auth | `_boundary.load_env` |

## committed artifact schema (`governance/profiles/.../v{N}.yaml`)

policy 가 소유하는 유일한 YAML "config" (= `serde.to_dict` 산출):

| on-disk key | dataclass field | 비고 |
|---|---|---|
| `schema` | `schema_version` | `enrich-cutoff-profile-v1` 고정 |
| `version` | `profile_version` | ticker 별 monotonic int ≥ 1 |
| `description` | `description` | D-CFG-1 헤더 미러 |
| `ticker` | `ticker` | `KR:NNNNNN` |
| `required_enrichments` | `required_enrichments` | enricher name 리스트 |
| `cutoff_rules` | `cutoff_rules` | screener Rule dict-tree, `type` 키 필수 |
| `provenance.committed_at` | `Provenance.committed_at` | iso kst |
| `provenance.committed_by` | `Provenance.committed_by` | `policy` \| `manual` \| `regression-fixture` |
| `provenance.trigger` | `Provenance.trigger` | `filing:rcept_no=...` \| `news:...` \| `manual` |
| `provenance.citations` | `Provenance.citations` | G7 리스트 `DART@<iso>=<value>` |
| `provenance.rationale_ko` | `Provenance.rationale_ko` | 1줄 한국어 의도 |

layout: `<root>/<ticker_dir>/v<N>.yaml`. `_boundary.write_profile_safely` (G20) → 절대 overwrite
안 함, 새 version 은 새 파일.

## D-CFG-1 공통 헤더

on-disk 포맷이 `schema` / `version` / `description` 을 top-level 에 두는 것은 config-header lint
**D-CFG-1** 충족 위함 (serde.py / schema.py docstring 명시). `EnrichCutoffProfile.description`
필드가 on-disk `description` 미러용으로 존재.

## schema bump 규약

`SCHEMA_VERSION = "enrich-cutoff-profile-v1"`. docstring (schema.py): "bump => serde.from_dict 가
마이그레이션 게이트로 reject. 호환 깨질 때만 올림." 즉 문자열 bump 시 미매칭 profile 전부
`serde.from_dict` 가 reject (migration gate). `__post_init__` 과 `from_dict` 둘 다
`schema_version == SCHEMA_VERSION` hard-gate.

## consumer 측 read (참고)

- universe — `required_enrichments` 사용 (`--use-profile-registry` flip 후; 현재 default OFF)
- screener — `cutoff_rules` 사용; completeness gate 가 `required_enrichments` 역참조
  (누락 시 `verdict="caution"`)
- 둘 다 `ProfileRegistry.load_latest` 로 *읽기*만 — policy 동기 호출 안 함 (out-of-band).
