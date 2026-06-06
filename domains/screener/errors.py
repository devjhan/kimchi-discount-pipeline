"""screener 도메인 예외 클래스.

bounded context 내부에서만 raise. 다른 도메인 / infrastructure 는 import 금지.
"""
from __future__ import annotations


class ScreenerError(Exception):
    """screener bounded context 의 모든 예외의 base."""


class InsufficientHistoryError(ScreenerError):
    """재무 시계열 / capital signals 가 요구 N년치를 충족 못 함.

    예: ROIC 3년 평균이 요구되는데 annual 시계열이 2개뿐인 경우.
    """


class MetricResolutionError(ScreenerError):
    """resolver 화이트리스트에 없는 metric_path 요청 또는 데이터 None.

    YAML 이 표현식 DSL 로 미끄러지지 않게 dynamic eval 금지 — 등록되지 않은
    metric 은 즉시 raise.
    """


class HardGuardViolationError(ScreenerError):
    """strategy YAML 이 hard_guards.yaml 의 locked_paths 영역을 override 시도.

    factory invariant 검사 단계에서 발생. RuleFactory.build_strategy 가
    catch 하지 않고 caller 까지 전파.
    """


class BoundaryViolationError(ScreenerError):
    """screener 내부 모듈이 _boundary.py 를 우회해 외부 자원 직접 접근.

    실행 중 raise 보다는 lint / 정적 분석으로 잡힐 가능성이 큼.
    이 예외는 _boundary 의 sanity check 에서 사용.
    """
