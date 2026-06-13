"""infrastructure/vectorstore — SqliteVectorStore 영속 roundtrip 단위 테스트 (Task 4)."""
from __future__ import annotations

import sqlite3
import struct
from pathlib import Path

import pytest

from infrastructure.vectorstore.store import SqliteVectorStore


def _seed(path: Path) -> SqliteVectorStore:
    s = SqliteVectorStore(path)
    meta = dict(model_id="m", embedded_at="2026-06-12T00:00:00+09:00")
    s.upsert_vector(kind="concept", key="holdco", vector=[1.0, 0.0], text_hash="c", **meta)
    s.upsert_vector(kind="ticker", key="KR:A", vector=[1.0, 0.0], text_hash="a", **meta)
    s.upsert_vector(kind="ticker", key="KR:B", vector=[0.0, 1.0], text_hash="b", **meta)
    return s


@pytest.mark.integration
def test_cosine_and_topk(tmp_path: Path) -> None:
    s = _seed(tmp_path / "vectors.sqlite")
    assert s.cosine("KR:A", "holdco") == pytest.approx(1.0)
    assert s.cosine("KR:B", "holdco") == pytest.approx(0.0)
    assert [k for k, _ in s.top_k("holdco", 1)] == ["KR:A"]
    s.close()


@pytest.mark.integration
def test_persistence_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "vectors.sqlite"
    s = _seed(db)
    s.upsert_scalars("KR:A", {"market_cap_krw": 5e11})
    s.close()
    s2 = SqliteVectorStore(db)
    assert s2.cosine("KR:A", "holdco") == pytest.approx(1.0)
    assert s2.attributes_for("KR:A")["market_cap_krw"] == 5e11
    s2.close()


@pytest.mark.integration
def test_idempotent_upsert(tmp_path: Path) -> None:
    db = tmp_path / "v.sqlite"
    s = _seed(db)
    # re-upsert same key with new vector → overwrite, not duplicate
    s.upsert_vector(
        kind="ticker", key="KR:A", vector=[0.0, 1.0],
        model_id="m", text_hash="a2", embedded_at="t",
    )
    assert s.cosine("KR:A", "holdco") == pytest.approx(0.0)
    s.close()


@pytest.mark.integration
def test_staleness(tmp_path: Path) -> None:
    s = _seed(tmp_path / "v.sqlite")
    assert s.has_fresh_vector(kind="ticker", key="KR:A", model_id="m", text_hash="a")
    assert not s.has_fresh_vector(kind="ticker", key="KR:A", model_id="m", text_hash="zzz")
    s.close()


@pytest.mark.integration
def test_sqlite_vec_loaded_is_bool(tmp_path: Path) -> None:
    # 확장 설치 여부와 무관하게 store 는 동작하고 플래그는 bool.
    s = SqliteVectorStore(tmp_path / "v.sqlite")
    assert isinstance(s.sqlite_vec_loaded, bool)
    s.close()


@pytest.mark.integration
def test_cosine_known_values_including_negative(tmp_path: Path) -> None:
    """vec_distance_cosine 시맨틱 검증: 정렬→1, 직교→0, 반대→-1, 45°→~0.707."""
    s = SqliteVectorStore(tmp_path / "v.sqlite")
    meta = dict(model_id="m", embedded_at="t")
    s.upsert_vector(kind="concept", key="c", vector=[1.0, 0.0], text_hash="c", **meta)
    s.upsert_vector(kind="ticker", key="ALIGN", vector=[1.0, 0.0], text_hash="1", **meta)
    s.upsert_vector(kind="ticker", key="ORTHO", vector=[0.0, 1.0], text_hash="2", **meta)
    s.upsert_vector(kind="ticker", key="OPP", vector=[-1.0, 0.0], text_hash="3", **meta)
    s.upsert_vector(kind="ticker", key="DIAG", vector=[1.0, 1.0], text_hash="4", **meta)
    assert s.cosine("ALIGN", "c") == pytest.approx(1.0, abs=1e-6)
    assert s.cosine("ORTHO", "c") == pytest.approx(0.0, abs=1e-6)
    assert s.cosine("OPP", "c") == pytest.approx(-1.0, abs=1e-6)
    assert s.cosine("DIAG", "c") == pytest.approx(0.70710678, abs=1e-6)
    s.close()


@pytest.mark.integration
def test_sql_and_python_paths_agree(tmp_path: Path) -> None:
    """확장(vec_distance_cosine) 경로와 순수 Python fallback 경로가 동일 결과를 내야 한다."""
    s = SqliteVectorStore(tmp_path / "v.sqlite")
    if not s.sqlite_vec_loaded:
        s.close()
        pytest.skip("sqlite-vec 확장 미설치 — parity 검증 불가")
    meta = dict(model_id="m", embedded_at="t")
    vectors = {
        "c": [0.2, 0.9, -0.1, 0.4],
        "A": [0.1, 0.8, 0.0, 0.5],
        "B": [-0.3, 0.2, 0.9, 0.1],
        "C": [0.25, 0.85, -0.05, 0.45],
    }
    s.upsert_vector(kind="concept", key="c", vector=vectors["c"], text_hash="c", **meta)
    for key in ("A", "B", "C"):
        s.upsert_vector(kind="ticker", key=key, vector=vectors[key], text_hash=key, **meta)

    # SQL 경로 (확장 로드 상태) 결과
    sql_cos = {k: s.cosine(k, "c") for k in ("A", "B", "C")}
    sql_topk = s.top_k("c", 3)

    # 동일 store 에서 강제로 Python fallback 경로 실행
    object.__setattr__(s, "_sqlite_vec_loaded", False)
    py_cos = {k: s.cosine(k, "c") for k in ("A", "B", "C")}
    py_topk = s.top_k("c", 3)

    for k in ("A", "B", "C"):
        assert sql_cos[k] == pytest.approx(py_cos[k], abs=1e-6)
    assert [k for k, _ in sql_topk] == [k for k, _ in py_topk]
    for (k1, v1), (k2, v2) in zip(sql_topk, py_topk):
        assert k1 == k2
        assert v1 == pytest.approx(v2, abs=1e-6)
    s.close()


@pytest.mark.integration
def test_durable_table_readable_without_extension(tmp_path: Path) -> None:
    """감사 증거 내구성: 확장 없이 raw sqlite3 로 열어도 벡터/메타가 판독 가능해야 한다."""
    db = tmp_path / "v.sqlite"
    s = SqliteVectorStore(db)
    s.upsert_vector(
        kind="ticker", key="KR:A", vector=[1.0, 0.0, 0.5],
        model_id="model-x", text_hash="h1", embedded_at="2026-06-12T00:00:00+09:00",
    )
    s.close()

    raw = sqlite3.connect(str(db))  # 확장 로드 일절 없음
    try:
        row = raw.execute(
            "SELECT kind, key, dim, model_id, text_hash, vec FROM vectors WHERE key=?",
            ("KR:A",),
        ).fetchone()
    finally:
        raw.close()
    assert row is not None
    kind, key, dim, model_id, text_hash, vec = row
    assert (kind, key, dim, model_id, text_hash) == ("ticker", "KR:A", 3, "model-x", "h1")
    # float32 little-endian BLOB 복원 가능 (vec_f32 호환 포맷).
    assert list(struct.unpack(f"<{dim}f", vec)) == pytest.approx([1.0, 0.0, 0.5])


@pytest.mark.integration
def test_topk_ignores_dimension_mismatch(tmp_path: Path) -> None:
    """차원 다른 ticker 벡터는 KNN 대상에서 제외 (vec_distance_cosine raise 방어)."""
    s = SqliteVectorStore(tmp_path / "v.sqlite")
    meta = dict(model_id="m", embedded_at="t")
    s.upsert_vector(kind="concept", key="c", vector=[1.0, 0.0], text_hash="c", **meta)
    s.upsert_vector(kind="ticker", key="OK", vector=[1.0, 0.0], text_hash="1", **meta)
    s.upsert_vector(kind="ticker", key="BADDIM", vector=[1.0, 0.0, 0.0], text_hash="2", **meta)
    top = s.top_k("c", 5)
    assert [k for k, _ in top] == ["OK"]
    assert s.cosine("BADDIM", "c") is None  # 차원불일치 → None
    s.close()
