"""
불변식 — ADR-0014: governance/policy/methods_manifest.yaml 은 code SSoT 와 동기 상태다.

manifest 는 screener rules(resolver/factory/leaf) + segment_registry.attributes 의
어휘를 투영한 *생성 산출물* 이다. 코드가 metric_path/rule_type/op/selection_attribute 를
추가·변경했는데 manifest 를 재생성하지 않으면 본 fitness function 이 빌드를 red 로 만든다
(환각 차단의 1차 방어가 실재하는 파일 + 동기 보장에 의존).

재생성: ``python -m applications.gen_methods_manifest``.
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import pytest  # noqa: E402
import yaml  # noqa: E402

import _helpers as h  # noqa: E402

from applications.gen_methods_manifest import build_manifest  # noqa: E402

_MANIFEST_PATH = h.REPO_ROOT / "governance" / "policy" / "methods_manifest.yaml"


@pytest.mark.arch
def test_methods_manifest_exists() -> None:
    """SoT #5 가 가리키는 manifest 가 실재한다 (finding 1 — dangling reference 해소)."""
    assert _MANIFEST_PATH.is_file(), (
        f"{h.rel(_MANIFEST_PATH)} 부재 — "
        "'python -m applications.gen_methods_manifest' 로 생성 (ADR-0014)"
    )


@pytest.mark.arch
def test_methods_manifest_in_sync_with_code() -> None:
    """on-disk manifest == 코드에서 재생성한 manifest (drift = build fail)."""
    on_disk = yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))
    rebuilt = build_manifest()
    assert on_disk == rebuilt, (
        "methods_manifest.yaml 이 code SSoT 와 불일치 — "
        "'python -m applications.gen_methods_manifest' 로 재생성 후 commit (ADR-0014)"
    )
