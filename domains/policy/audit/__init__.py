"""domains/policy/audit — minimal violation logging (macro/universe/screener 동형).

citation regex + JSONL append-only log + GuardViolation frozen dataclass. policy 는
commit 시점의 drift / citation 위반을 기록 (silent overwrite 금지).
"""
from __future__ import annotations
