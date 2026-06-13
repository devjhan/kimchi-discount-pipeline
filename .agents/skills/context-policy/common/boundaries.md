# Boundary — 외부 연결점 단일 게이트 (invariant-D 전환 완료)

## 핵심 규칙

모든 외부 호출은 `_boundary.py` 위임 함수만. 예외 — `domains._shared.*` (profile_registry / audit) 직접 import 가능.

## 두 불변식

| 불변식 | 내용 | 상태 |
|---|---|---|
| **C** | `infrastructure.*` 는 `_boundary.py` 만 import | 🟢 GREEN (test 1건 예외 — allowlist) |
| **D** | `application/` · `domain/` 이 `_boundary` 직접 import 안 함 | 🟢 GREEN (전환 완료 2026-06-06) |

**D 전환 방식**: `application/commit.py` 의 유일 `_boundary` 의존(시계)을 `_shared.time.clock.now_kst` 로 치환. `domain/` 은 원래부터 pure.

## 현재 _boundary.py export

### 상수 / 예외
`KST` / `DartUnavailable`

### Path / time / citation
`resolve_path(alias, *, date=None)` (alias: `operations_audit` / `trail_today`) / `profiles_root() -> Path` / `drafts_dir() -> Path` / `now_kst()` / `now_iso_kst()` / `format_citation(source, ts, value)`

### Env / secret
`load_env(path=None)` / `secret_safe_log(msg, env)`

### Output (draft JSON vs commit YAML 구분)
- `write_output_safely(out_path, payload)` — G20 JSON (ephemeral draft)
- `write_profile_safely(out_path, payload)` — G20 YAML (governance/policy/profiles SSoT commit)

### DART API (intake)
`dart_has_key(env)` / `dart_iter_disclosures(api_key, *, bgn_de, end_de, **kw)`

## 절대 금지 / 올바름

```python
# ❌ infrastructure 직접 import (production)
from infrastructure.dart import client

# ✅ 올바름
from domains.policy import _boundary
registry = ProfileRegistry(root=_boundary.profiles_root())
_boundary.write_profile_safely(path, serde.to_dict(profile))   # commit (YAML)
_boundary.write_output_safely(draft_path, draft_payload)       # draft (JSON)
```

draft (JSON, ephemeral) 와 commit (YAML, governance SSoT) 의 writer 분리가 핵심 — phase2 가 draft 만 쓰고 commit 권한은 phase3 결정론 코드에만 (ADR-0003).

## 검증

```bash
grep -rn "from infrastructure\|import infrastructure" domains/policy/ --include="*.py" | grep -v _boundary.py
# → test 1건 (allowlist). production 0.
```
