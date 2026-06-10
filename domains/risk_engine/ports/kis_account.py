"""KisAccountPort — KIS 계좌 read-only 6 게이트웨이 (순수 typing, infra import 0).

**type-level G9c (4번째 구조 가드).** 본 Protocol surface 에는 order / submit / cancel
류 메서드가 *존재하지 않는다* — 따라서 본 port 를 통한 매매 호출은 타입상 표현 불가능.
G9 의 기존 3중 방어(① `_boundary` 가 order endpoint 미노출 ② `infrastructure/kis/client`
        의 `KisAutoTradeBlocked` ③ `governance/runtime-policy.yaml` Bash deny + runtime-policy whitelist)
에 *type-level read-only* 를 한 겹 더한다 (기존 가드 무변경, 추가만).

impl = ``domains/risk_engine/_boundary.kis_account_adapter()`` (read endpoint 위임).
주입: ``positions_sync.main()`` 이 adapter 구성 → ``sync_account(..., account=...)``.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class KisAccountPort(Protocol):
    """KIS 계좌 조회 6 메서드 — read 전용 (order surface 부재 = G9c)."""

    def issue_access_token(self, env: dict[str, str]) -> str:
        """KIS OAuth 토큰 발급 (토큰 캐시 경로는 adapter 가 내부 주입)."""
        ...

    def fetch_account_balance(self, **kwargs: Any) -> dict[str, Any]:
        """보유 잔고 (positions / summary)."""
        ...

    def fetch_buyable_amount(self, **kwargs: Any) -> dict[str, Any]:
        """매수가능 현금성."""
        ...

    def fetch_account_assets(self, **kwargs: Any) -> dict[str, Any]:
        """계좌 자산 종합 (total_assets fallback)."""
        ...

    def fetch_realized_pnl(self, **kwargs: Any) -> dict[str, Any]:
        """실현손익 (종목별 + 합산)."""
        ...

    def fetch_sellable_qty(self, *, stock_code: str, **kwargs: Any) -> dict[str, Any]:
        """종목별 매도가능수량."""
        ...
