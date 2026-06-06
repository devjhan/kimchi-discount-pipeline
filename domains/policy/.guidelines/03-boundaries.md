# Boundary — 외부 연결점 단일 게이트 (invariant-D 전환 완료)

## 핵심 규칙

policy 의 다른 모듈이 `infrastructure.*` / `os.environ` 에 직접 접근하면 boundary 우회.
모든 외부 호출은 `_boundary.py` 위임 함수만. 예외 — `domains._shared.*` (profile_registry /
audit) 직접 import 가능.

## 두 불변식의 현재 상태

| 불변식 | 내용 | policy 상태 |
|---|---|---|
| **C** | `infrastructure.*` 는 `_boundary.py` 만 import | 🟢 GREEN (production; test 1건 예외) |
| **D** | `application/` · `domain/` 이 `_boundary` 직접 import 안 함 | 🟢 **GREEN (전환 완료 2026-06-06)** |

**C**: `grep -rn "from infrastructure" domains/policy/ --include="*.py" | grep -v _boundary.py`
는 test 1건만 (`tests/unit/test_commit.py:12 from infrastructure._common.utils import
write_yaml_safely`). boundary-gate fitness test 는 production layer 만 walk → C GREEN.

**D 전환 방식:** `application/commit.py` 의 유일 `_boundary` 의존은 시계
(`now_iso_kst` / `now_kst`) 뿐이었다. 이를 `domains._shared.time.clock.now_kst` (커널,
`_boundary` 비의존) 로 치환 — `committed_at = now_kst().isoformat(timespec="seconds")`
(= `_utils.now_iso_kst()` byte-동일). injection 불요, signature/test 변경 0. `domain/` 은
원래부터 pure. (`audit/log.py` 의 `_boundary` import 은 invariant-D 범위 밖 — audit/ 레이어.)

근거 / 추적: **ADR-0005** + **D-ARCH-4**.
`tests/architecture/test_boundary_gate.py::test_application_domain_does_not_import_boundary[policy]`
가 이제 hard-assert 로 통과 (`_D_UNCONVERTED` 비었음).

## 검증

```bash
grep -rn "from infrastructure\|import infrastructure" domains/policy/ --include="*.py" | grep -v _boundary.py
# → test 1건 (accepted exception). production 0.
# 불변식: 스킬(LLM)은 commit 안 함 — drift/version 은 commit_gate.py 결정론
```

## 현재 export 함수 (`_boundary.py`)

### 상수 / 예외 re-export
- `KST` / `DartUnavailable`

### Path / time / citation
- `resolve_path(alias, *, date=None)` (alias: `operations_audit` / `trail_today`)
- `profiles_root() -> Path` (registry root 주입), `drafts_dir() -> Path`
- `now_kst()`, `now_iso_kst()`, `format_citation(source, ts, value)`

### Env / secret
- `load_env(path=None)`, `secret_safe_log(msg, env)`

### Output (draft JSON vs commit YAML 구분)
- `write_output_safely(out_path, payload) -> Path` — G20 JSON (ephemeral draft)
- `write_profile_safely(out_path, payload) -> Path` — G20 YAML (governance/profiles SSoT commit)

### DART API (intake)
- `dart_has_key(env)`, `dart_iter_disclosures(api_key, *, bgn_de, end_de, **kw)`

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

draft (JSON, ephemeral) 와 commit (YAML, governance SSoT) 의 writer 가 분리된 것이 핵심 —
phase2 가 draft 만 쓰고 commit 권한은 phase3 결정론 코드에만 (ADR-0003).

## 전환 완료 (D → GREEN, 2026-06-06)

application 의 유일 `_boundary` 의존(시계)을 `_shared.time.clock` 커널로 치환해 invariant-D
GREEN 달성. `ports/llm.PolicyEngine` 는 LLM seam 의 port 주입 reference 로 존속. policy 는
시계 외 path/output 관심사를 application 에서 쓰지 않아 (commit 은 `writer`/`registry` 주입,
intake 는 main.py 책임) 추가 port 추출 불요.
