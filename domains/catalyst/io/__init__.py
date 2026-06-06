"""catalyst io — 외부 adapter (trail 로더 / DART·KIS·Yahoo fetch).

모든 외부 의존은 ``domains.catalyst._boundary`` 경유 (infrastructure 직접 import 금지).
NAV 시계열 store 는 cross-BC 공유라 ``domains/_shared/nav_history`` 로 이전 (B-2).
"""
from __future__ import annotations
