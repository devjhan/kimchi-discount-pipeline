"""Shadow portfolio state store — load + atomic in-place update.

state 파일 (``$AUDIT_DIR/shadow-portfolio/state.json``) 은 *append-update* 되는 living
accumulator (일별 immutable trail 산출물과 다름). 따라서 G20 ``.{N}.json`` suffix 가
아니라 같은 파일을 atomic replace (tmp write → os.replace) 로 갱신한다. daily_snapshots /
quarterly_history 는 누적만 되고 과거 history 를 잃지 않는다 (append-only spirit).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from domains.audit_integrity import _boundary
from domains.audit_integrity.domain.state import ShadowPortfolioState


def state_path() -> Path:
    return _boundary.resolve_path("shadow_state")


def load_state() -> ShadowPortfolioState | None:
    """state 파일 load. 미존재 시 None (caller 가 --init 안내)."""
    p = state_path()
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as f:
        return ShadowPortfolioState.from_dict(json.load(f))


def save_state(state: ShadowPortfolioState) -> Path:
    """state 를 같은 파일에 atomic replace (tmp → os.replace)."""
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)
    return p
