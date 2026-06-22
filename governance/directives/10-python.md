# D-PY — Python 작성 컨벤션

`$DOMAINS_DIR`, `$INFRA_COMMON_DIR`, infra clients, `$HOOKS_DIR` 의 모든 `.py` 파일이 따라야 할 작성 컨벤션. 기존 helper (`$INFRA_COMMON_DIR/utils.py`, `$RISK_ENGINE_DIR/sizing.py`) 가 모범.

---

## D-PY-1 — 모든 `.py` 헤더에 `from __future__ import annotations`

**근거**: typing forward reference (`dict[str, Any]` literal syntax) 가 Python 3.9 / 3.10 환경에서 일관되게 작동. 기존 도메인 helper 100% 이 라인을 가짐.

❌ 금지
```python
"""utils.py — common helpers."""
from typing import Any
def foo(x: dict[str, Any]) -> str: ...
```

✅ 올바름
```python
"""utils.py — common helpers."""
from __future__ import annotations
from typing import Any
def foo(x: dict[str, Any]) -> str: ...
```

**Hook** (ADR-0010으로 파기: `block_anti_patterns.sh`): → 대체: ruff check + 수동 리뷰.

---

## D-PY-2 — public 함수 서명에 타입 힌트 의무

**근거**: 도메인 코드는 hook / skill / 다른 도메인 helper 가 cross-call. 타입 힌트는 단순 IDE 편의가 아니라 API 계약.

❌ 금지
```python
def fetch_macro(country, lookback_days):
    ...
```

✅ 올바름
```python
def fetch_macro(country: str, lookback_days: int) -> dict[str, Any]:
    ...
```

예외: `_underscore_prefix` private helper 는 inline 추론이 명확하면 생략 허용. test fixture 도 예외.

**Hook** (ADR-0010으로 파기: `lint_directives.sh`): → 대체: ruff check.

---

## D-PY-3 — `except Exception` 은 `# noqa: BLE001` 또는 명시 catch

**근거**: bare `except Exception` 은 KeyboardInterrupt 외 모든 에러를 삼키므로 디버깅 악화. 의도적 graceful degrade 이면 noqa 코멘트로 의도 명시 — 외부 API fetch 실패 / optional yaml 결측을 흡수하는 패턴이 모범 (`safe_http_json` / `_load_yaml_optional`).

❌ 금지
```python
try:
    data = fetch_dart(corp_code)
except Exception:
    return None
```

✅ 올바름
```python
try:
    data = fetch_dart(corp_code)
except Exception as exc:  # noqa: BLE001 — DART 의 4xx/5xx 모두 graceful degrade
    logger.warning("dart_fetch_failed corp=%s err=%s", corp_code, exc)
    return None
```

또는 명시 catch
```python
try:
    data = fetch_dart(corp_code)
except (HTTPError, JSONDecodeError) as exc:
    ...
```

**Hook** (ADR-0010으로 파기: `lint_directives.sh`): → 대체: ruff check.

---

## D-PY-4 — import 순서: future → stdlib → third-party → local

**근거**: `isort` 와 동일 규약. 그룹마다 1 빈 줄. 기존 helper 가 일관되게 따르므로 새 파일도 동형 유지.

✅ 올바름
```python
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml
import requests

from infrastructure._common.utils import secret_safe_log, trail_dir
from domains.universe.main import main
```

**Hook** (ADR-0010으로 파기: `lint_directives.sh`): → 대체: ruff/isort.

---

## D-PY-5 — 함수/모듈 docstring: 1~3 줄 한국어, 부재 허용 안 됨

**근거**: 본 시스템은 다국어 의도(혹은 모호한 영어)로 인한 misinterpretation 리스크 큼 (특수상황 도메인 + 한국 IPS 컨텍스트). 한국어 1 줄 docstring 으로 의도 명시.

❌ 금지
```python
def scan_buyback_catalyst(...) -> dict[str, Any]:
    return ...  # docstring 없음
```

✅ 올바름
```python
def scan_buyback_catalyst(
    universe_path: Path,
    lookback_days: int,
) -> dict[str, Any]:
    """자사주 소각 공시 (DART) 를 lookback_days 안에서 scan."""
    ...
```

예외: 1 줄 lambda / `_underscore_prefix` private + 인라인 trivial → docstring 생략 가능.

**Hook** (ADR-0010으로 파기: `lint_directives.sh`): → 대체: ruff check.

---

## D-PY-6 — fatal 에러는 `SystemExit`, recoverable 은 tuple `(data, err)` 반환

**근거**: helper 의 caller (skill / hook / domain) 에서 일관된 에러 처리. fatal (config missing, env var unset) 은 `raise SystemExit` 로 즉시 종료, recoverable (DART rate-limit, 단일 ticker 결측) 은 tuple 반환으로 caller 가 결정.

✅ fatal 패턴
```python
env_path = REPO_ROOT / ".env"          # REPO_ROOT: infrastructure._common.utils
if not env_path.exists():
    raise SystemExit(f"[ERROR] .env not found: {env_path}")
```

✅ recoverable 패턴
```python
def fetch_macro_breadth(date: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return (data, None) on success, (None, error_msg) on graceful failure."""
    try:
        return _do_fetch(date), None
    except HTTPError as exc:
        return None, f"http_error: {exc}"
```

**Hook**: `inject_only` — code review 시 인용.

---

## D-PY-7 — 새 모듈은 `if __name__ == "__main__":` 진입점이 있어야 CLI 실행 가능

**근거**: 모든 stage helper 는 `python -m domains.universe.main` 같은 CLI 직접 실행을 보장. cron / debug / smoke test 시 entry point 가 일관.

✅ 올바름
```python
def main() -> int:
    """CLI 진입점."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    ...
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

예외: `_underscore_prefix` 시작하는 private helper module (e.g., `_brief_citation_gate.py`) 은 hook wrapper 가 호출하므로 main 부재 OK.

**Hook**: `inject_only`.
