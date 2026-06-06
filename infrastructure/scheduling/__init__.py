"""infrastructure.scheduling — OS-scheduler 경계 layer.

governance/schedules.yaml (SSoT) 를 입력으로 OS 별 derived artifact
(macOS launchd plist / Linux systemd timer / ...) 를 emit 하고, lock 파일과
drift snapshot 으로 일관성을 enforce 한다. 본 패키지가 OS 경계의 유일한
통로 — 다른 어떤 layer 도 launchctl / systemctl / schtasks 를 직접 호출하지
않는다.
"""

from __future__ import annotations
