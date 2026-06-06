"""PositionsStore — 보유 포지션 thesis.json 의 read/commit 어댑터.

``profile_registry.ProfileRegistry`` 와 동형: ``root: Path`` 는 caller(risk_engine 의
``_boundary.positions_root()``)가 주입, ``commit`` 의 writer 도 주입(``write_output_safely``).
본 패키지는 ``infrastructure`` 를 import 하지 않는다 — JSON 읽기는 stdlib ``json`` 만.

저장 레이아웃: ``<root>/<ticker_dir>/thesis.json`` (``KR:003550`` → ``KR_003550/thesis.json``).
profile_registry 와 달리 thesis 는 monotonic ``vN`` 이력이 아니라 종목당 단일 *현재*
thesis.json — 일별 이력은 ``drift-/expiry-/balance-{date}`` sidecar 가 보존(README §2).

``load_open*`` 은 risk_engine 의 3개 중복 로더(``load_open_positions`` /
``load_open_thesis`` / ``load_event_trigger_positions``)를 단일 대체한다. graceful skip
(corrupt JSON / status!=open)은 기존 로더 거동을 byte 단위로 보존.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from domains._shared.positions_store import serde
from domains._shared.positions_store.errors import PositionSchemaError
from domains._shared.positions_store.schema import PositionThesis

THESIS_FILENAME = "thesis.json"


@dataclass(frozen=True)
class PositionsStore:
    """thesis.json read + injected-writer commit. root 는 caller 가 주입."""

    root: Path

    # --- read ---------------------------------------------------------------

    def load_open_raw(
        self, *, category: str | None = None
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """``{ticker}/thesis.json`` 전부 load → 원시 dict 리스트 + warnings.

        risk_engine 3 로더의 단일 대체(dict passthrough — 호출부 ``.get()`` 접근 유지).
        - sorted iterdir, 비-디렉토리/thesis.json 부재 skip
        - JSONDecodeError/OSError → warning + continue (기존 graceful skip 보존)
        - ``status`` 가 set 이고 != "open" 이면 skip
        - ``category`` 지정 시 falsifier.category 불일치 skip (5c 용 "event_trigger")
        """
        out: list[dict[str, Any]] = []
        warnings: list[str] = []
        if not self.root.exists():
            return out, warnings
        for sub in sorted(self.root.iterdir()):
            if not sub.is_dir():
                continue
            thesis_path = sub / THESIS_FILENAME
            if not thesis_path.exists():
                continue
            try:
                with thesis_path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                warnings.append(f"thesis.json parse fail: {thesis_path} — {exc}")
                continue
            if data.get("status") and data.get("status") != "open":
                continue
            if category is not None:
                cat = (data.get("thesis") or {}).get("falsifier", {}).get("category")
                if cat != category:
                    continue
            out.append(data)
        return out, warnings

    def load_open(
        self, *, category: str | None = None
    ) -> tuple[list[PositionThesis], list[str]]:
        """``load_open_raw`` + serde 검증 → 타입드 PositionThesis 리스트.

        손상 schema 는 raise 대신 warning + skip (raw 로더의 graceful tolerance 와 일치).
        """
        raw, warnings = self.load_open_raw(category=category)
        out: list[PositionThesis] = []
        for data in raw:
            try:
                out.append(serde.from_dict(data))
            except PositionSchemaError as exc:
                warnings.append(f"thesis schema invalid: {data.get('ticker', '?')} — {exc}")
        return out, warnings

    def load_one(self, ticker: str) -> PositionThesis | None:
        """단일 ticker 의 현재 thesis. 미존재 → None. 손상 → PositionSchemaError."""
        path = self.thesis_path(ticker)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as f:
            return serde.from_dict(json.load(f))

    def has_open_thesis(self, ticker: str) -> bool:
        """``{ticker}/thesis.json`` 이 존재하고 status 가 open 인가(멱등 가드용).

        손상/파싱 실패는 'open 아님'(False)으로 — caller 가 clobber 판단 전 안전측.
        """
        path = self.thesis_path(ticker)
        if not path.exists():
            return False
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return False
        status = data.get("status")
        return (not status) or status == "open"

    # --- write --------------------------------------------------------------

    def commit(
        self,
        thesis: PositionThesis,
        *,
        writer: Callable[[Path, Any], Path],
    ) -> Path:
        """``{ticker}/thesis.json`` write. writer(consumer 의 write_output_safely) 주입."""
        return writer(self.thesis_path(thesis.ticker), serde.to_dict(thesis))

    # --- path ---------------------------------------------------------------

    def thesis_path(self, ticker: str) -> Path:
        return self.root / _ticker_dir(ticker) / THESIS_FILENAME


def _ticker_dir(ticker: str) -> str:
    """"KR:003550" → "KR_003550" (콜론/슬래시는 디렉토리명에 부적합).

    risk_engine 의 기존 writer 컨벤션(``falsifier_proximity._write_drift_md`` 등)과 일치 —
    drift-/expiry-{date} sidecar 와 같은 디렉토리에 안착.
    """
    return ticker.replace(":", "_").replace("/", "_")
