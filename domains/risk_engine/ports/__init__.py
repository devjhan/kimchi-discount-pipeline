"""domains/risk_engine/ports — risk_engine BC-local **Port (Protocol)** 정의 (순수 typing).

risk_engine 1개 BC 만 쓰는 외부 의존 계약 (KIS 계좌 read 등). cross-cutting (≥2 BC) 은
``domains/_shared/ports`` 에 둔다. impl(adapter) 은 ``_boundary.py`` 잔류 — D-CORE-4
(domain ← infra 단방향) 안전: Protocol 은 typing 만 import.
"""
