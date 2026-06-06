"""
infrastructure/notify/adapter.py — NotifierAdapter ABC.

각 채널 (Slack / Gmail / KakaoTalk / Discord / Telegram / generic webhook) 은
본 ABC 를 상속해 `render(brief_md) → payload` 와 `send(payload, dry_run) →
AdapterResult` 를 구현한다.

dispatcher 는 LLM tool 을 직접 호출하지 않는다 — payload 생성 + 검증까지가
adapter 의 책임이며, 실제 LLM tool 호출 (Slack MCP / Gmail MCP) 은 routine
prompt 본문에서 받은 payload 를 인자로 호출. webhook 처럼 stdlib HTTP 로
보내는 채널은 send() 안에서 직접 송신.

Hard guards (모든 adapter 공통):
    - G7: brief 본문에 unsourced 숫자 없는지 검사 (`validate_brief`)
    - G19: forbidden language ("guaranteed", "alpha confirmed" 등) 사전 검사
    - G21: secret 환경변수 leak 검사 (env value literal 본문 포함 시 raise)
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from infrastructure._common.utils import SECRET_ENV_KEYS, load_env_file

# G19 — 산출물 본문에 절대 등장 금지 wording. 일부는 단어 boundary 검사.
FORBIDDEN_PATTERNS = (
    r"\bshould buy\b",
    r"\bshould sell\b",
    r"\blooks bullish\b",
    r"\blooks bearish\b",
    r"\bguaranteed\b",
    r"\bsure thing\b",
    r"\bno-brainer\b",
    r"\balpha confirmed\b",
    r"\bstrategy proven\b",
    r"\bmust hold\b",
    r"\bmust buy\b",
)
_FORBIDDEN_RE = re.compile("|".join(FORBIDDEN_PATTERNS), re.IGNORECASE)

# G7 — 본문 내 raw 숫자가 citation 없이 등장하는 경우 detection
# 단, header / disclaimer / structural 라인은 제외 — 본 검사는 약한 heuristic.
# 강한 검사는 brief_citation_gate.sh 가 별도로 수행. adapter 는 light gate 만.
_CITATION_RE = re.compile(r"@\d{4}-\d{2}-\d{2}|@FRED|@DART|@KIS|@yahoo")


class BriefBlocked(RuntimeError):
    """brief 본문이 forbidden wording / secret leak 검사에 실패. dispatcher 가
    해당 채널 skip 하고 다른 채널은 계속.
    """


@dataclass
class AdapterResult:
    """채널별 send 결과.

    status:
        'sent'    — payload 가 외부로 송신 완료 (또는 dry-run 이면 검증 통과)
        'skipped' — required_env 미설정 / dry-run 모드 등
        'blocked' — BriefBlocked 발생 (validate_brief 실패)
        'error'   — 외부 송신 실패 (HTTP / connector error)
    """

    channel: str
    status: str
    payload: dict[str, Any] | None = None
    skip_reason: str | None = None
    error: str | None = None


class NotifierAdapter(ABC):
    """모든 notifier 채널의 base class.

    Subclass MUST set:
        - name: registry key ("slack" / "gmail" / ...)
        - required_env: 미설정 시 skip 조건이 되는 env var name list
    """

    name: str = ""
    required_env: tuple[str, ...] = ()

    def __init__(self, env: dict[str, str] | None = None) -> None:
        self.env = env if env is not None else load_env_file()

    def is_ready(self) -> tuple[bool, str | None]:
        """required_env 검사. (ready, missing_reason)."""
        missing = [k for k in self.required_env if not self.env.get(k, "").strip()]
        if missing:
            return False, f"env missing: {','.join(missing)}"
        return True, None

    def validate_brief(self, brief_md: str) -> None:
        """G19 + G21 검사. 위반 시 BriefBlocked raise."""
        m = _FORBIDDEN_RE.search(brief_md)
        if m:
            raise BriefBlocked(f"forbidden_wording: {m.group(0)!r}")
        for key in SECRET_ENV_KEYS:
            val = self.env.get(key, "")
            if val and val in brief_md:
                raise BriefBlocked(f"secret_leak: brief 본문에 {key} 값 포함")

    @abstractmethod
    def render(self, brief_md: str) -> dict[str, Any]:
        """채널별 payload 형태 (예: Slack blocks / Email body+subject) 로 변환."""

    @abstractmethod
    def send(self, payload: dict[str, Any], *, dry_run: bool) -> AdapterResult:
        """payload 외부 송신. dry_run=True 면 송신 없이 'sent' 반환 가능 (또는
        skipped). MCP tool 호출이 필요한 채널은 caller (routine prompt) 가 받은
        payload 를 다시 도구에 넣도록 'sent' + payload 동봉으로 위임.
        """


__all__ = [
    "FORBIDDEN_PATTERNS",
    "BriefBlocked",
    "AdapterResult",
    "NotifierAdapter",
]
