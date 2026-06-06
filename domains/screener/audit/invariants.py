"""Invariant 검사 — RuleFactory 가 build 시점에 적용하는 검증의 re-export.

본 모듈은 thin re-export — 실제 구현은 rules/factory.py 에. 본 모듈을 통한
import 만 허용해 audit 도메인의 계약 (어떤 invariant 가 강제되는가) 을
한 곳에 보여주는 역할.
"""
from __future__ import annotations

from domains.screener.rules.factory import RuleFactory

# Re-export — 외부 caller 는 본 모듈을 통해 invariant 검사 함수에 접근.
assert_no_hard_guard_override = RuleFactory._assert_no_hard_guard_override
assert_registered_method_only = RuleFactory._assert_registered_method_only
