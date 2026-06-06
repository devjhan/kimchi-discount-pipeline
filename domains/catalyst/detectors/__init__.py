"""catalyst detectors — CatalystDetector plugin (ABC + registry + factory + 6 plugin).

universe ``sources/`` 패턴 동형. 신규 detector 추가 = 1 plugin 클래스 +
``factory.py`` import 1줄 + ``config/detectors.yaml`` entry.
"""
from __future__ import annotations
