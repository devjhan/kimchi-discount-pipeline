"""segment_registry.concepts — ConceptDeclaration schema + ConceptRegistry 단위 테스트 (Task 1)."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from domains._shared.segment_registry import concepts as C
from domains._shared.segment_registry.concepts import (
    CONCEPT_SCHEMA_VERSION,
    ConceptDeclaration,
    ConceptRegistry,
)
from domains._shared.segment_registry.errors import (
    ConceptNotFoundError,
    ConceptSchemaError,
)


def _decl(version: int = 1, **overrides) -> ConceptDeclaration:
    kwargs = dict(
        concept_id="holdco_value_trap",
        schema_version=CONCEPT_SCHEMA_VERSION,
        concept_version=version,
        anchor_text="지주회사 구조로 시장가가 순자산가치 대비 큰 폭으로 할인된 종목",
        seed_tickers=("KR:003550",),
        default_op="ge",
        default_threshold=0.78,
        description="지주사 NAV 할인",
    )
    kwargs.update(overrides)
    return ConceptDeclaration(**kwargs)


@pytest.mark.unit
def test_valid_concept_constructs() -> None:
    c = _decl()
    assert c.concept_id == "holdco_value_trap"
    assert c.default_threshold == 0.78


@pytest.mark.unit
def test_empty_anchor_and_no_seed_raises() -> None:
    with pytest.raises(ConceptSchemaError):
        _decl(anchor_text="", seed_tickers=())


@pytest.mark.unit
def test_anchor_text_only_allowed() -> None:
    c = _decl(seed_tickers=())
    assert c.seed_tickers == ()


@pytest.mark.unit
def test_seed_only_allowed() -> None:
    c = _decl(anchor_text="   ", seed_tickers=("KR:003550",))
    assert c.seed_tickers == ("KR:003550",)


@pytest.mark.unit
def test_bad_schema_version_raises() -> None:
    with pytest.raises(ConceptSchemaError):
        _decl(schema_version="segment-concept-v999")


@pytest.mark.unit
def test_version_zero_raises() -> None:
    with pytest.raises(ConceptSchemaError):
        _decl(version=0)


@pytest.mark.unit
def test_round_trip() -> None:
    c = _decl(2)
    assert C.from_dict(C.to_dict(c)) == c


@pytest.mark.unit
def test_from_dict_schema_gate() -> None:
    with pytest.raises(ConceptSchemaError):
        C.from_dict({"schema": "wrong", "version": 1, "concept_id": "x"})


@pytest.mark.unit
def test_registry_load_latest_and_versions(tmp_path: Path) -> None:
    reg = ConceptRegistry(root=tmp_path)
    assert reg.load_latest("holdco_value_trap") is None  # 미등록 → None
    d = tmp_path / "holdco_value_trap"
    d.mkdir()
    for v in (1, 2, 3):
        (d / f"v{v}.yaml").write_text(
            yaml.safe_dump(C.to_dict(_decl(v)), allow_unicode=True), encoding="utf-8"
        )
    latest = reg.load_latest("holdco_value_trap")
    assert latest is not None and latest.concept_version == 3
    assert reg.list_versions("holdco_value_trap") == (1, 2, 3)
    assert reg.list_concepts() == ("holdco_value_trap",)


@pytest.mark.unit
def test_registry_load_version_missing_raises(tmp_path: Path) -> None:
    reg = ConceptRegistry(root=tmp_path)
    with pytest.raises(ConceptNotFoundError):
        reg.load_version("nope", 1)


@pytest.mark.unit
def test_registry_corrupt_yaml_raises(tmp_path: Path) -> None:
    d = tmp_path / "broken"
    d.mkdir()
    (d / "v1.yaml").write_text("schema: segment-concept-v1\nversion: 1\n", encoding="utf-8")
    reg = ConceptRegistry(root=tmp_path)
    with pytest.raises(ConceptSchemaError):  # concept_id 누락
        reg.load_latest("broken")
