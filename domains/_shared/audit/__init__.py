"""domains/_shared/audit — BC 공통 audit plumbing (공유 커널).

screener / universe / policy / macro 4개 bounded context 가 복붙해 온
``audit/{citation,violation,log}.py`` 의 *plumbing* (G7 citation 정규식 ·
``GuardViolation`` 값 객체 · JSONL append-only ``ViolationLog``) 단일화.
``_shared/__init__.py`` 의 rule-of-three (3번째 consumer → 추출) 를 이미 초과
(4 consumer) 했으므로 ``profile_registry`` / ``positions_store`` 와 동형으로 추출.

추출 대상 / 비대상:
- 대상 (본 패키지): ``citation`` (G7 ``CITATION_RE`` SSoT) · ``violation``
  (``GuardViolation`` frozen dataclass) · ``log`` (``ViolationLog``, ``bc_name``
  파라미터화).
- 비대상 (각 BC 보존): ``audit/invariants.py`` — BC 고유 도메인 룰 (universe 의
  G7+enricher 검사 81 LOC vs screener 의 RuleFactory assert re-export 13 LOC).

레이어 정책 (``domains/_shared/__init__.py`` 계승):
- ``infrastructure._common`` (platform utility — ``audit_dir`` 등) 만 import 가능
  (``log.ViolationLog`` 의 default audit_dir 해석용, lazy import).
- ``infrastructure/{dart,kis,yahoo,fred}`` (vendor adapter) import 금지.
- 다른 도메인 (``domains.screener`` 등) import 금지 — 본 패키지가 그들의 의존.

각 BC 의 ``audit/{citation,violation,log}.py`` 는 본 패키지 재export / thin
subclass shim 으로 남아 기존 import 경로 (``from domains.screener.audit.log
import ViolationLog``) 와 positional 시그니처 (``ViolationLog(clock)``) 를 보존한다.
"""
from __future__ import annotations
