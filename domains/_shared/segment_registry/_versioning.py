"""versioned-file 레이아웃 공통 helper — concept / segment registry 공유.

``profile_registry/registry.py`` 의 ``_ticker_dir`` / ``_sorted_versions`` 와 동일
규약: ``<root>/<id_dir>/v<N>.yaml``, 신규 버전은 항상 새 파일 (덮어쓰기 없이 이력
보존 — G20). id 의 ``:`` 는 디렉토리명에 부적합하므로 ``_`` 로 치환.
"""
from __future__ import annotations

from pathlib import Path


def id_dir(identifier: str) -> str:
    """``KR:005930`` → ``KR_005930`` (콜론은 디렉토리명에 부적합)."""
    return identifier.replace(":", "_")


def sorted_versions(d: Path) -> list[int]:
    """``v<N>.yaml`` 파일들의 N 을 오름차순으로. 비-정수 stem 은 무시."""
    out: list[int] = []
    if not d.exists():
        return out
    for p in d.glob("v*.yaml"):
        stem = p.stem[1:]  # "v3" -> "3"
        if stem.isdigit():
            out.append(int(stem))
    return sorted(out)


def version_path(root: Path, identifier: str, version: int) -> Path:
    """``<root>/<id_dir>/v<version>.yaml`` 절대경로."""
    return root / id_dir(identifier) / f"v{version}.yaml"
