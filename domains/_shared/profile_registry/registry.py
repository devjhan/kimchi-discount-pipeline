"""ProfileRegistry — 종목별 프로파일의 버전 관리 어댑터 (load read + injected-writer commit).

설계 원칙 (DDD shared kernel):
- ``_shared`` 는 ``infrastructure`` 를 import 하지 않는다 → utils path helper /
  ``write_output_safely`` 직접 호출 금지. ``root: Path`` 는 caller(consumer 의
  ``_boundary.profiles_root()``)가 주입. ``commit`` 의 writer 도 주입.
- YAML 읽기는 stdlib ``yaml.safe_load`` 직접 사용. (``infrastructure`` 의
  ``load_yaml_config`` 는 파일 부재 시 ``SystemExit`` 라 라이브러리 코드에 부적합.)

저장 레이아웃: ``<root>/<ticker_dir>/v<N>.yaml`` (``KR:005930`` → ``KR_005930/v3.yaml``).
신규 버전은 항상 새 파일 — 덮어쓰기 없이 이력 보존 (G20).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

from domains._shared.profile_registry import serde
from domains._shared.profile_registry.errors import ProfileNotFoundError
from domains._shared.profile_registry.schema import EnrichCutoffProfile


@dataclass(frozen=True)
class ProfileRegistry:
    """프로파일 read + versioned commit. root 는 caller 가 주입 (_boundary.profiles_root())."""

    root: Path

    def load_latest(self, ticker: str) -> EnrichCutoffProfile | None:
        """ticker 의 최신 버전 프로파일. 미등록 ticker → None (Default No-Action).

        손상 YAML → serde 가 ProfileSchemaError 전파 (silent pass 금지).
        """
        d = self.root / _ticker_dir(ticker)
        if not d.exists():
            return None
        versions = _sorted_versions(d)
        if not versions:
            return None
        return self.load_version(ticker, versions[-1])

    def load_version(self, ticker: str, version: int) -> EnrichCutoffProfile:
        """특정 버전 명시 조회. 부재 → ProfileNotFoundError."""
        path = self.root / _ticker_dir(ticker) / f"v{version}.yaml"
        if not path.exists():
            raise ProfileNotFoundError(f"{ticker} v{version} 부재: {path}")
        with path.open("r", encoding="utf-8") as f:
            return serde.from_dict(yaml.safe_load(f) or {})

    def list_versions(self, ticker: str) -> tuple[int, ...]:
        """등록된 버전 번호 오름차순 tuple. 미등록 ticker → 빈 tuple."""
        d = self.root / _ticker_dir(ticker)
        if not d.exists():
            return ()
        return tuple(_sorted_versions(d))

    def commit(
        self,
        profile: EnrichCutoffProfile,
        *,
        writer: Callable[[Path, Any], Path],
    ) -> Path:
        """versioned 파일 write. writer(consumer 의 write_output_safely) 주입.

        version 은 caller 가 이미 설정 — registry 는 경로 계산 + 직렬화만.
        """
        path = self.root / _ticker_dir(profile.ticker) / f"v{profile.profile_version}.yaml"
        return writer(path, serde.to_dict(profile))


def _ticker_dir(ticker: str) -> str:
    """"KR:005930" → "KR_005930" (콜론은 디렉토리명에 부적합)."""
    return ticker.replace(":", "_")


def _sorted_versions(d: Path) -> list[int]:
    """``v<N>.yaml`` 파일들의 N 을 오름차순으로. 비-정수 stem 은 무시."""
    out: list[int] = []
    for p in d.glob("v*.yaml"):
        stem = p.stem[1:]  # "v3" -> "3"
        if stem.isdigit():
            out.append(int(stem))
    return sorted(out)
