"""domains/_shared/ports — cross-cutting **Port (Protocol)** 정의 (순수 typing).

≥2 BC 가 공유하는 외부 의존 계약을 ``typing.Protocol`` 로 선언한다 (infra import 0).
구현(adapter)은 각 BC ``_boundary.py`` 가 ``infrastructure._common.utils`` 등에 위임해
구성하고, composition root(``<bc>/main.py``)가 순수 use-case 에 주입한다.

선례: ``domains/policy/ports/llm.py`` (PolicyEngine) — port=Protocol / adapter=_boundary
/ main()=주입. 본 패키지는 그 BC-local 패턴을 cross-cutting 축(citation/clock/...)으로
일반화한 것이다. D-CORE-4 (domain ← infra 단방향) 안전 — Protocol 은 typing 만 import.
"""
