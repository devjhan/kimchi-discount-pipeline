"""domains/macro/audit — minimal violation logging.

universe 의 audit pattern 직역 — citation regex + JSONL append-only log +
GuardViolation frozen dataclass. 차이: macro 는 N entries 가 아니라 1 RegimeResult
+ 4 indicators 만 산출하므로 runtime invariant 검증 범위 작음.
"""
from __future__ import annotations
