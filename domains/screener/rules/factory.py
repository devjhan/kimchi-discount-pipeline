"""RuleFactory — strategy / profile YAML 을 Rule 트리로 변환.

3 핵심 anchor 중 1: 모든 Rule 트리 생성은 본 클래스를 통과. 직접 ``AndRule(...)``
생성 시 HardGuardWrapper 자동 삽입이 누락되어 G13 우회 통로가 열림.

invariant 검사:
- assert_no_hard_guard_override: strategy 가 hard_guards.yaml 의 locked_paths 영역을 override 시도 차단
- assert_registered_method_only: 사용된 scoring method 가 registry 에 등록되어 있는지 확인
"""
from __future__ import annotations

from typing import Any

from domains.screener.errors import HardGuardViolationError
from domains.screener.rules.base import Rule
from domains.screener.rules.composite import AndRule, NotRule, OrRule, WeightedSumRule
from domains.screener.rules.guards import HardGuardWrapper
from domains.screener.rules.leaf import ScoringRule, SignalPresenceRule, ThresholdRule
from domains.screener.rules.methods import SCORING_METHODS


class RuleFactory:
    """strategy YAML 전체를 받아 Rule 트리 + HardGuardWrapper 로 감싸 반환."""

    @staticmethod
    def build_strategy(
        strategy_yaml: dict[str, Any],
        profiles: dict[str, dict[str, Any]],
        hard_guards: dict[str, Any],
        *,
        tax_rate: float | None = None,
    ) -> Rule:
        """Strategy 의 inner rule 트리 + outer HardGuardWrapper 자동 wrap.

        steps:
        1. invariant: hard_guards 의 locked_paths 영역 override 시도 차단
        2. invariant: 사용된 method 가 SCORING_METHODS 에 등록되어 있는지
        3. inner rule 트리 빌드
        4. hard guards 를 outer wrapper 로 자동 삽입 (우회 불가)
        """
        RuleFactory._assert_no_hard_guard_override(strategy_yaml, hard_guards)
        RuleFactory._assert_registered_method_only(strategy_yaml, profiles)

        inner = RuleFactory._from_dict(
            strategy_yaml["rule"], profiles, tax_rate=tax_rate
        )
        guards = tuple(
            RuleFactory._from_dict(g, profiles, tax_rate=tax_rate)
            for g in hard_guards.get("guards", [])
        )
        return HardGuardWrapper(
            _name=f"strategy[{strategy_yaml['name']}]",
            inner=inner,
            guards=guards,
        )

    # ------------------------------------------------------------------
    # Invariant 검사
    # ------------------------------------------------------------------

    @staticmethod
    def _assert_no_hard_guard_override(
        strategy_yaml: dict[str, Any], hard_guards: dict[str, Any]
    ) -> None:
        """strategy 가 hard_guards 의 locked_paths 영역을 override 했는지 검사."""
        locked = set(hard_guards.get("locked_paths") or [])
        if not locked:
            return
        names_in_strategy = _collect_rule_names(strategy_yaml.get("rule", {}))
        guard_names = {g.get("name") for g in hard_guards.get("guards", [])}
        conflict = names_in_strategy & guard_names
        if conflict:
            raise HardGuardViolationError(
                f"strategy 가 hard guard 이름을 override 시도: {sorted(conflict)}"
            )

    @staticmethod
    def _assert_registered_method_only(
        strategy_yaml: dict[str, Any], profiles: dict[str, dict[str, Any]]
    ) -> None:
        """YAML 에 등장하는 모든 scoring method 가 registry 에 있는지 확인."""
        methods_used = _collect_methods(strategy_yaml.get("rule", {}), profiles)
        unknown = methods_used - set(SCORING_METHODS.keys())
        if unknown:
            raise ValueError(f"unknown scoring methods: {sorted(unknown)}")

    # ------------------------------------------------------------------
    # 재귀 dispatch — 새 rule 타입은 본 메서드에 한 분기 추가로 확장
    # ------------------------------------------------------------------

    @staticmethod
    def _from_dict(
        spec: dict[str, Any],
        profiles: dict[str, dict[str, Any]],
        *,
        tax_rate: float | None,
    ) -> Rule:
        rtype = spec["type"]

        if rtype == "and":
            return AndRule(
                _name=spec.get("name", "and"),
                children=tuple(
                    RuleFactory._from_dict(c, profiles, tax_rate=tax_rate)
                    for c in spec["children"]
                ),
            )

        if rtype == "or":
            return OrRule(
                _name=spec.get("name", "or"),
                children=tuple(
                    RuleFactory._from_dict(c, profiles, tax_rate=tax_rate)
                    for c in spec["children"]
                ),
            )

        if rtype == "not":
            return NotRule(
                _name=spec.get("name", "not"),
                inner=RuleFactory._from_dict(spec["inner"], profiles, tax_rate=tax_rate),
            )

        if rtype == "weighted_sum":
            children = tuple(
                (
                    RuleFactory._from_dict(c["rule"], profiles, tax_rate=tax_rate),
                    float(c["weight"]),
                )
                for c in spec["children"]
            )
            return WeightedSumRule(
                _name=spec.get("name", "weighted_sum"),
                children=children,
                pass_score=float(spec["pass_score"]),
            )

        if rtype == "profile_ref":
            profile_name = spec["profile"]
            if profile_name not in profiles:
                raise ValueError(f"unknown profile: {profile_name}")
            return RuleFactory._from_dict(
                profiles[profile_name]["rule"], profiles, tax_rate=tax_rate
            )

        if rtype == "threshold":
            return ThresholdRule(
                _name=spec["name"],
                metric_path=spec["metric_path"],
                op=spec["op"],
                threshold=float(spec["threshold"]),
                period_years=spec.get("period_years"),
                tax_rate=tax_rate,
            )

        if rtype == "scoring":
            return ScoringRule(
                _name=spec["name"],
                metric_path=spec["metric_path"],
                method=spec["method"],
                params=dict(spec.get("params") or {}),
                pass_score=float(spec.get("pass_score", 0.5)),
                period_years=spec.get("period_years"),
                tax_rate=tax_rate,
            )

        if rtype == "signal_presence":
            return SignalPresenceRule(
                _name=spec["name"],
                required_any_of=tuple(spec["required_any_of"]),
            )

        raise ValueError(f"unknown rule type: {rtype}")


def _collect_rule_names(spec: dict[str, Any]) -> set[str]:
    """rule 트리 YAML 에서 모든 name 필드 수집 (override 검사용)."""
    names: set[str] = set()
    if not isinstance(spec, dict):
        return names
    n = spec.get("name")
    if isinstance(n, str):
        names.add(n)
    for key in ("children", "inner"):
        v = spec.get(key)
        if isinstance(v, list):
            for c in v:
                if isinstance(c, dict):
                    inner_spec = c.get("rule", c)
                    names |= _collect_rule_names(inner_spec)
        elif isinstance(v, dict):
            names |= _collect_rule_names(v)
    return names


def _collect_methods(
    spec: dict[str, Any], profiles: dict[str, dict[str, Any]]
) -> set[str]:
    """rule 트리 + 참조된 profile 에서 사용된 method 이름 수집."""
    methods: set[str] = set()
    if not isinstance(spec, dict):
        return methods
    if spec.get("type") == "scoring":
        m = spec.get("method")
        if isinstance(m, str):
            methods.add(m)
    if spec.get("type") == "profile_ref":
        pname = spec.get("profile")
        if pname in profiles:
            methods |= _collect_methods(profiles[pname].get("rule", {}), profiles)
    for key in ("children", "inner"):
        v = spec.get(key)
        if isinstance(v, list):
            for c in v:
                if isinstance(c, dict):
                    methods |= _collect_methods(c.get("rule", c), profiles)
        elif isinstance(v, dict):
            methods |= _collect_methods(v, profiles)
    return methods
