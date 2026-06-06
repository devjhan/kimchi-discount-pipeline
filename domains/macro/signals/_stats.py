"""macro signal 공유 통계 helper."""
from __future__ import annotations


def percentile(samples: list[float], target: float) -> float | None:
    """target value 가 samples 안에서 차지하는 percentile (0.0~1.0)."""
    if not samples:
        return None
    less = sum(1 for s in samples if s <= target)
    return less / len(samples)
