"""domains/policy/domain — policy 의 도메인 룰 + frozen value objects.

- ``trigger`` / ``research_result`` — producer DTO (Trigger / ResearchOutput).
- ``drift`` — 두 프로파일 비교 (drift detection).
- ``commit_gate`` — 버전 발급 / drift 차단판정 / provenance 조립 (F-4: 진짜 도메인 룰).
"""
from __future__ import annotations
