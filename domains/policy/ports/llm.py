"""PolicyEngine — LLM research seam (인터페이스만; 내부 설계는 본 PR 범위 밖).

구현(Claude skill / API)은 ``_boundary`` 뒤에 둔다. application 은 본 Protocol 에만
의존 — LLM 교체 / mock 주입이 자유롭다 (테스트는 stub engine 주입).
"""
from __future__ import annotations

from typing import Protocol

from domains.policy.domain.research_result import ResearchOutput
from domains.policy.domain.trigger import Trigger


class PolicyEngine(Protocol):
    """trigger + evidence → 제안 프로파일 (required_enrichments + cutoff_rules + citations)."""

    def analyze(
        self, trigger: Trigger, *, evidence: tuple[str, ...]
    ) -> ResearchOutput:
        """순수 변환: I/O · commit 금지. ``cutoff_rules`` 는 RuleFactory 소비 가능 문법.

        evidence 는 redaction 완료된 fact-only (외부신호 SOP 산출). raw payload
        직접 ingest 금지 (G10).
        """
        ...
