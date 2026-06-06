"""analyze — Trigger + evidence → ResearchOutput (PolicyEngine 위임).

evidence 는 redaction 완료된 fact-only (외부신호 SOP 산출). raw payload 직접
ingest 금지 (G10). 본 모듈은 engine seam 호출만 — LLM 내부는 ports/llm 구현 책임.
"""
from __future__ import annotations

from domains.policy.domain.research_result import ResearchOutput
from domains.policy.domain.trigger import Trigger
from domains.policy.ports.llm import PolicyEngine


def run_analysis(
    trigger: Trigger,
    engine: PolicyEngine,
    *,
    evidence: tuple[str, ...] = (),
) -> ResearchOutput:
    """engine.analyze 위임. 순수 — I/O · commit 없음 (commit 은 별도 단계)."""
    return engine.analyze(trigger, evidence=evidence)
