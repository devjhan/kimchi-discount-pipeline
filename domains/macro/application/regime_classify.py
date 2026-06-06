"""classify_regime + detect_regime_shift — Stage 0 의 deterministic 분류 로직.

원래 ``domains/risk_engine/macro_regime.py:263-391`` 의 classify_regime +
detect_regime_shift 를 본 모듈로 이전. config 입력 schema 변경: legacy 는
thresholds.yaml.macro.* 를 받았으나 신규는 config/regimes.yaml 의 ``thresholds`` /
``cash_band`` / ``regime_shift_alert`` 키를 directly 받음 (macro. 접두 제거).

IO 책임 (외부 감사 2026-05-17 명시):
- ``classify_regime`` — pure function (config + indicators dict in, RegimeResult out).
- ``detect_regime_shift`` — *단방향 file read* (과거 trail 의 ``00-macro-regime.json``)
  를 ``_boundary.resolve_path`` 통과해 수행. application layer 의 IO 는 일반적으로
  anti-pattern 이나, 본 함수는 (a) read-only, (b) boundary 통과, (c) 이전 trail
  파일이 단순 환경 read 이라 별도 service 추출 가치가 낮음 — 실용적 타협.
  향후 backtest harness 도입 시 ``previous_regime_loader`` 같은 작은 callable
  로 추출 검토.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Mapping

from domains.macro import _boundary
from domains.macro.domain.regime import IndicatorResult, RegimeResult
from domains.macro.signals.factory import SIGNALS  # import 가 4 signal 등록 트리거

_SEVERITY: dict[str, int] = {
    "early_cycle": 0,
    "mid_cycle": 1,
    "late_cycle": 2,
    "crisis": 3,
}


def classify_regime(
    indicators: Mapping[str, IndicatorResult],
    cfg: Mapping[str, Any],
) -> RegimeResult:
    """indicator 들의 vote 합산 → max-severity regime label.

    각 indicator 의 vote 로직은 해당 Signal 클래스 (``signals/{name}.py``) 가
    소유한다 — 본 함수는 registry 로 Signal 을 조회해 ``vote`` 를 호출하고
    aggregation (max-severity) 만 수행. crisis > late_cycle > mid_cycle >
    early_cycle. vote 없는 (None) indicator 는 skip — 전부 skip 이면 unknown.

    indicators dict 의 순서대로 vote 를 수집하므로 votes/rationale 순서는
    main 이 넘기는 signal 순서 (= config ``signals:`` 순서) 를 보존한다.
    """
    thresholds = cfg.get("thresholds") or {}
    votes: list[str] = []
    rationale: list[str] = []

    for name, result in indicators.items():
        if result is None:
            continue
        sig_cls = SIGNALS.get(name)
        if sig_cls is None:
            continue  # 등록 안 된 indicator 이름 → vote skip
        voted = sig_cls().vote(result, thresholds)
        if voted is not None:
            regime_vote, why = voted
            votes.append(regime_vote)
            rationale.append(why)

    if not votes:
        return RegimeResult(
            regime="unknown",
            rationale=tuple(rationale),
            votes=(),
            vote_summary={},
        )

    chosen = max(votes, key=lambda r: _SEVERITY.get(r, 0))
    summary: dict[str, int] = {}
    for v in votes:
        summary[v] = summary.get(v, 0) + 1
    return RegimeResult(
        regime=chosen,
        rationale=tuple(rationale),
        votes=tuple(votes),
        vote_summary=summary,
    )


def detect_regime_shift(
    current_date: str,
    current_regime: str,
    cfg: Mapping[str, Any],
) -> dict[str, Any]:
    """이전 cron run 의 regime 과 비교해 consecutive_days_in_current 계산.

    require_consecutive_days 충족 시 alert=True. legacy 와 동일 동작.
    """
    require = int(
        (cfg.get("regime_shift_alert") or {}).get("require_consecutive_days", 3)
    )
    cur_dt = datetime.strptime(current_date, "%Y-%m-%d")
    consecutive = 1
    previous_regime: str | None = None
    for back in range(1, require + 5):
        prev_dt = cur_dt - timedelta(days=back)
        prev_path = (
            _boundary.resolve_path("trail_today", date=prev_dt.strftime("%Y-%m-%d"))
            / "00-macro-regime.json"
        )
        if not prev_path.exists():
            continue
        try:
            with prev_path.open("r", encoding="utf-8") as f:
                prev = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        prev_regime = (prev.get("regime_decision") or {}).get("regime")
        if previous_regime is None:
            previous_regime = prev_regime
        if prev_regime == current_regime:
            consecutive += 1
        else:
            break
    alert = consecutive >= require and previous_regime != current_regime
    return {
        "previous_regime": previous_regime,
        "consecutive_days_in_current": consecutive,
        "require_consecutive_days": require,
        "alert": alert,
    }
