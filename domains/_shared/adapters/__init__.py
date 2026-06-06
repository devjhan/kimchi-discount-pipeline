"""domains/_shared/adapters — cross-cutting **shared 알고리즘** (infra import 0).

여러 BC 가 복제하던 외부 의존 처리 스켈레톤을, 외부 자원을 ``_shared/ports`` Protocol
로 주입받아 수행하는 순수 공유 코드. 일반 hexagonal "adapter" (infra 접촉) 와 달리 본
패키지는 infra 를 직접 import 하지 않고 *주입된 port* 로만 외부와 닿는다 — 따라서 D-CORE-4
(domain ← infra 단방향) 안전하며 ``domains/_shared`` 에 거주 가능. 실제 infra 어댑터는
각 BC ``_boundary.py`` 잔류.
"""
