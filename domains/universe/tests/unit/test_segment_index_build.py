"""segment_index_main (Task 9) — build 오케스트레이션 composition root 검증.

순수 build 로직은 test_segment_build 가 보증. 본 파일은 universe trail → row 수집 +
boundary 주입 + dry-run/live 경로를 검증 (네트워크/벡터DB 불요 — stub 주입).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from domains._shared.adapters.embedding_remote import RemoteEmbeddingAdapter
from domains._shared.adapters.vector_index_memory import InMemoryVectorIndex
from domains.universe import _boundary
from domains.universe import segment_index_main as segidx

pytestmark = pytest.mark.unit


def test_collect_universe_rows_extracts_whitelisted_scalars(tmp_path: Path) -> None:
    trail = tmp_path / "01-universe.json"
    trail.write_text(
        json.dumps(
            {
                "entries": [
                    {
                        "ticker": "KR:003550",
                        "source_category": "holding_company",
                        "metadata": {"market_cap_krw": 5e11, "ignored": "x"},
                        "enrichments": {"nav_discount": {"discount_pct": 0.42}},
                    },
                    {"ticker": "KR:000660", "source_category": "manual_addition", "metadata": {}},
                    {"name": "no-ticker-skipped"},
                ]
            }
        ),
        encoding="utf-8",
    )
    tickers, scalars, warnings = segidx.collect_universe_rows(trail)
    assert tickers == ["KR:003550", "KR:000660"]
    assert scalars["KR:003550"]["source_category"] == "holding_company"
    assert scalars["KR:003550"]["market_cap_krw"] == 5e11
    assert scalars["KR:003550"]["nav_discount_pct"] == 0.42
    assert "ignored" not in scalars["KR:003550"]  # 화이트리스트 밖 제외
    assert warnings == []


def test_collect_universe_rows_missing_trail_graceful(tmp_path: Path) -> None:
    tickers, scalars, warnings = segidx.collect_universe_rows(tmp_path / "absent.json")
    assert tickers == [] and scalars == {}
    assert len(warnings) == 1


def _write_trail(trail_dir: Path, entries: list[dict]) -> None:
    trail_dir.mkdir(parents=True, exist_ok=True)
    (trail_dir / "01-universe.json").write_text(
        json.dumps({"entries": entries}), encoding="utf-8"
    )


def test_main_dry_run_writes_scalars_only(tmp_path: Path, monkeypatch) -> None:
    trail_dir = tmp_path / "ops"
    _write_trail(
        trail_dir,
        [{"ticker": "KR:003550", "source_category": "holding_company",
          "metadata": {"market_cap_krw": 5e11}}],
    )
    idx = InMemoryVectorIndex()
    monkeypatch.setattr(_boundary, "resolve_trail_dir", lambda date=None: trail_dir)
    monkeypatch.setattr(_boundary, "vector_index", lambda db_path=None: idx)
    monkeypatch.setattr(_boundary, "vector_store_path", lambda: tmp_path / "v.sqlite")
    monkeypatch.setattr(_boundary, "load_env", lambda *a, **k: {})

    rc = segidx.main(["--dry-run", "--date", "2026-05-17"])
    assert rc == 0
    # dry-run → 임베딩 skip, scalar 는 적재됨 (rule-based 선택 계속 가능).
    attrs = idx.attributes_for("KR:003550")
    assert attrs["source_category"] == "holding_company"
    assert attrs["market_cap_krw"] == 5e11
    # 임베딩 안 함 → cosine None.
    assert idx.cosine("KR:003550", "holdco_value_trap") is None


def test_main_live_embeds_concept_and_ticker(tmp_path: Path, monkeypatch) -> None:
    trail_dir = tmp_path / "ops"
    _write_trail(trail_dir, [{"ticker": "KR:003550", "source_category": "holding_company"}])
    texts = tmp_path / "texts.json"
    texts.write_text(json.dumps({"KR:003550": "지주회사 NAV 할인 가치주"}), encoding="utf-8")

    idx = InMemoryVectorIndex()

    def _fake_transport(texts_list):
        return [[1.0, 0.0] for _ in texts_list], "fake-model", 2

    fake = RemoteEmbeddingAdapter(transport=_fake_transport, model_id="fake-model", available=True)
    monkeypatch.setattr(_boundary, "resolve_trail_dir", lambda date=None: trail_dir)
    monkeypatch.setattr(_boundary, "vector_index", lambda db_path=None: idx)
    monkeypatch.setattr(_boundary, "vector_store_path", lambda: tmp_path / "v.sqlite")
    monkeypatch.setattr(_boundary, "load_env", lambda *a, **k: {})
    monkeypatch.setattr(_boundary, "embedding_port", lambda env, dry_run=False: fake)

    rc = segidx.main(["--date", "2026-05-17", "--texts-file", str(texts)])
    assert rc == 0
    # 예시 concept(holdco_value_trap) anchor + ticker 둘 다 임베딩 → cosine 계산 가능.
    assert idx.cosine("KR:003550", "holdco_value_trap") == pytest.approx(1.0)
