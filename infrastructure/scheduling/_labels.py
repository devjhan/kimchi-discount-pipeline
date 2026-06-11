"""launchd label prefix SSoT — scheduling 패키지 공유 상수.

``launchd_generator`` (emit) 와 ``drift_audit`` (대조) 가 본 단일 정의를 import 한다.
이전에는 두 모듈이 각자 ``LABEL_PREFIX`` 를 중복 정의해 v2↔v3 드리프트의 원천이었다
(arch-review/stale-audit X-1). shell (``install.sh`` / ``uninstall.sh``) 의 glob 은
Python import 가 불가하므로 본 값과 **수동 동기** 의무 — 변경 시:
  1. 본 파일 LABEL_PREFIX
  2. install.sh / uninstall.sh 의 ``com.investment_v*.`` glob + 하드코딩 label
  3. governance/schedules.yaml §Schedules 의 derive 주석
을 함께 갱신한다.
"""

from __future__ import annotations

LABEL_PREFIX = "com.kimchidiscountpipeline"
"""macOS launchd plist Label prefix. 최종 label = f"{LABEL_PREFIX}.{schedule_key}" """
