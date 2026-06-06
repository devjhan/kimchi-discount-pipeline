# Boundary — 외부 연결점 단일 게이트 + 미전환 잔여

## 핵심 규칙

policy 의 다른 모듈이 `infrastructure.*` / `os.environ` 에 직접 접근하면 boundary 우회.
모든 외부 호출은 `_boundary.py` 위임 함수만. 예외 — `domains._shared.*` (profile_registry /
audit) 직접 import 가능.

## 두 불변식의 현재 상태 (중요)

| 불변식 | 내용 | policy 상태 |
|---|---|---|
| **C** | `infrastructure.*` 는 `_boundary.py` 만 import | 🟢 GREEN (production; test 1건 예외) |
| **D** | `application/` · `domain/` 이 `_boundary` 직접 import 안 함 | 🔴 **RED — 미전환** |

**C**: `grep -rn "from infrastructure" domains/policy/ --include="*.py" | grep -v _boundary.py`
는 test 1건만 (`tests/unit/test_commit.py:12 from infrastructure._common.utils import
write_yaml_safely`). boundary-gate fitness test 는 production layer 만 walk → C GREEN.

**D 가 RED 인 이유:** `application/commit.py` 가 `_boundary` 직접 import
(`:19 from domains.policy import _boundary`, `:67 _boundary.now_iso_kst()`,
`:75 _boundary.now_kst()`); `audit/log.py:11` 도. `domain/` 은 import 안 함 (pure).
**`ports/llm.py` (PolicyEngine) 가 Wave-5 port reference template 임에도**, path/time/clock/output
관심사는 아직 port 주입 미전환 → application 이 `_boundary` 직접 도달.

근거 / 추적: **ADR-0005** ("미전환 잔여: macro/policy/risk_engine") + **D-ARCH-4**.
`tests/architecture/test_boundary_gate.py` 가 policy 를 `_D_UNCONVERTED` xfail(strict=False) 로
추적 — 전환 시 자동 green (`governance/decisions/0005-boundary-ports-and-adapters.md`).

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

## 전환 시 (D → GREEN)

application 의 path/time/output `_boundary` 직접 의존을 typed port 주입으로 치환, composition
root (`main`) 에서 wire. `ports/llm.PolicyEngine` 가 이미 그 패턴 — 나머지 관심사 확장 후
`_D_UNCONVERTED` 에서 `policy` 제거.
