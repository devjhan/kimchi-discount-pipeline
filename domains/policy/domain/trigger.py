"""Trigger — 정책 저작을 촉발한 사건 (공시 / 외부신호 / 수동)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Trigger:
    """단일 정책 검토 촉발 사건. raw payload 가 아니라 *참조* 만 보관 (G10)."""

    kind: str  # "filing" | "news" | "manual"
    ticker: str  # "KR:005930"
    payload_ref: str  # 공시 rcept_no / 외부신호 파일 경로 (raw payload 아님)
    detected_at: str  # iso kst

    def describe(self) -> str:
        return f"{self.kind}:{self.payload_ref}"
