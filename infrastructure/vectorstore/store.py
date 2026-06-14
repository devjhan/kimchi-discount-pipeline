"""infrastructure/vectorstore — 임베디드 벡터 + scalar 선택 속성 저장소 (11-b/13-a).

단일 ``sqlite`` 파일에 (1) 벡터(kind='ticker'|'concept') + 임베딩 메타, (2) scalar
선택 속성을 함께 보관한다. 벡터는 모델 버전 의존 *재생성 불가 증거* → telemetry 거주
(ADR-0008, 경로는 caller 주입).

sqlite-vec 사용 (명세: https://alexgarcia.xyz/sqlite-vec/api-reference.html):
- 벡터는 ``vec_f32`` 호환 **little-endian float32 BLOB** 로 *일반 테이블*(``vectors``)에
  보관한다. 일반 테이블이라 ``sqlite-vec`` 확장이 로드되지 않은 환경에서도 *항상 판독
  가능* — 감사 증거(audit evidence)의 내구성을 보장한다. (벡터를 ``vec0`` 가상테이블에만
  저장하면 확장 미로드 시 ``no such module: vec0`` 로 **판독 불가** → 비재생성 증거의
  내구성 원칙 위배라 의도적으로 회피. 13-a 결정의 정신은 'sqlite-vec 를 실제로 사용'이며,
  명세가 1급으로 문서화한 "Manually with SQL scalar functions" KNN 방식으로 충족한다.)
- 유사도/KNN 은 ``sqlite-vec`` 의 ``vec_distance_cosine(a, b)`` SQL 함수로 계산한다. 이
  함수는 코사인 *거리* 를 돌려주므로 ``cosine_similarity = 1 - vec_distance_cosine`` 이다
  (명세 검증: 정렬 벡터→거리 0→유사도 1, 직교→거리 1→유사도 0, 반대→거리 2→유사도 -1).
  확장이 로드되지 않았거나 함수 호출이 실패하면 **동일 결과의 순수 Python cosine** 으로
  graceful fallback 한다 (G8/G11 — 견고성).

불변식: ``domains`` import 0 (불변식 A). ``VectorIndexPort`` 를 *구조적* 으로 충족
(Protocol import 안 함). 모든 메서드는 primitive in/out.
"""
from __future__ import annotations

import json
import math
import sqlite3
import struct
from pathlib import Path
from typing import Any, Mapping, Sequence


def _pack(vector: Sequence[float]) -> bytes:
    """float 시퀀스 → little-endian float32 BLOB (sqlite-vec ``vec_f32`` 호환)."""
    return struct.pack(f"<{len(vector)}f", *(float(x) for x in vector))


def _unpack(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))


def _cosine(a: Sequence[float], b: Sequence[float]) -> float | None:
    """순수 Python 코사인 유사도. 빈/차원불일치/영벡터 → None (확장 fallback 과 동일 시맨틱)."""
    if not a or not b or len(a) != len(b):
        return None
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return None
    return dot / (na * nb)


class SqliteVectorStore:
    """sqlite 단일 파일 벡터/scalar 저장소. ``VectorIndexPort`` 를 구조적으로 충족.

    ``db_path`` 부모 디렉토리는 생성된다. ``sqlite-vec`` 확장은 있으면 로드해 질의를
    ``vec_distance_cosine`` 으로 가속하고, 없으면 순수 Python cosine 으로 동작한다.
    저장 포맷(일반 테이블 + float32 BLOB)은 두 경우 모두 동일하므로 확장 유무와
    무관하게 파일은 항상 판독 가능하다.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._sqlite_vec_loaded = self._try_load_sqlite_vec(self._conn)
        self._init_schema()

    @staticmethod
    def _try_load_sqlite_vec(conn: sqlite3.Connection) -> bool:
        """``sqlite-vec`` 확장 best-effort 로드 + ``vec_distance_cosine`` 가용성 검증.

        설치/로드/함수호출 중 어느 단계든 실패하면 ``False`` (정확 Python 경로 사용).
        """
        try:
            import sqlite_vec  # type: ignore

            conn.enable_load_extension(True)
            sqlite_vec.load(conn)
            conn.enable_load_extension(False)
            # 함수가 실제로 등록·동작하는지 smoke-test (로드만 되고 함수 부재인 빌드 방어).
            conn.execute("SELECT vec_distance_cosine(vec_f32(?), vec_f32(?))", (_pack([1.0]), _pack([1.0])))
            return True
        except Exception:  # noqa: BLE001 — 미설치/미지원/빌드결함 → 가속 없이 진행
            try:
                conn.enable_load_extension(False)
            except Exception:  # noqa: BLE001
                pass
            return False

    @property
    def sqlite_vec_loaded(self) -> bool:
        return self._sqlite_vec_loaded

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vectors (
                kind TEXT NOT NULL,
                key TEXT NOT NULL,
                dim INTEGER NOT NULL,
                model_id TEXT NOT NULL,
                text_hash TEXT NOT NULL,
                embedded_at TEXT NOT NULL,
                vec BLOB NOT NULL,
                PRIMARY KEY (kind, key)
            )
            """
        )
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS scalars (
                ticker TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    # ----- VectorIndexPort surface -----
    def upsert_vector(
        self,
        *,
        kind: str,
        key: str,
        vector: Sequence[float],
        model_id: str,
        text_hash: str,
        embedded_at: str,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO vectors (kind, key, dim, model_id, text_hash, embedded_at, vec)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(kind, key) DO UPDATE SET
                dim=excluded.dim, model_id=excluded.model_id,
                text_hash=excluded.text_hash, embedded_at=excluded.embedded_at,
                vec=excluded.vec
            """,
            (kind, key, len(vector), model_id, text_hash, embedded_at, _pack(vector)),
        )
        self._conn.commit()

    def has_fresh_vector(
        self, *, kind: str, key: str, model_id: str, text_hash: str
    ) -> bool:
        cur = self._conn.execute(
            "SELECT 1 FROM vectors WHERE kind=? AND key=? AND model_id=? AND text_hash=?",
            (kind, key, model_id, text_hash),
        )
        return cur.fetchone() is not None

    def upsert_scalars(self, ticker: str, scalars: Mapping[str, Any]) -> None:
        merged = dict(self.attributes_for(ticker))
        merged.update(scalars)
        self._conn.execute(
            "INSERT INTO scalars (ticker, data) VALUES (?, ?) "
            "ON CONFLICT(ticker) DO UPDATE SET data=excluded.data",
            (ticker, json.dumps(merged, ensure_ascii=False)),
        )
        self._conn.commit()

    def _vector_row(self, kind: str, key: str) -> tuple[bytes, int] | None:
        cur = self._conn.execute(
            "SELECT vec, dim FROM vectors WHERE kind=? AND key=?", (kind, key)
        )
        row = cur.fetchone()
        return (row[0], row[1]) if row else None

    def cosine(self, ticker: str, concept: str) -> float | None:
        """ticker 벡터 vs concept anchor 벡터 코사인 유사도. 둘 중 하나라도 부재/차원불일치 → None."""
        tv = self._vector_row("ticker", ticker)
        cv = self._vector_row("concept", concept)
        if tv is None or cv is None or tv[1] != cv[1]:
            return None
        if self._sqlite_vec_loaded:
            sim = self._cosine_sql(tv[0], cv[0])
            if sim is not None:
                return sim
        return _cosine(_unpack(tv[0]), _unpack(cv[0]))

    def _cosine_sql(self, a_blob: bytes, b_blob: bytes) -> float | None:
        """``vec_distance_cosine`` 으로 유사도(=1-거리) 계산. 실패 → None (Python fallback 유도)."""
        try:
            cur = self._conn.execute(
                "SELECT vec_distance_cosine(vec_f32(?), vec_f32(?))", (a_blob, b_blob)
            )
            row = cur.fetchone()
        except sqlite3.Error:
            return None
        if row is None or row[0] is None:
            return None
        dist = float(row[0])
        if math.isnan(dist):  # 영벡터 등 → 정의 불가
            return None
        return 1.0 - dist

    def top_k(self, concept: str, k: int) -> list[tuple[str, float]]:
        """concept anchor 에 가장 가까운 ticker top-k [(ticker, cosine), ...] 내림차순(유사도)."""
        if k < 1:
            return []
        cv = self._vector_row("concept", concept)
        if cv is None:
            return []
        concept_blob, dim = cv
        if self._sqlite_vec_loaded:
            ranked = self._top_k_sql(concept_blob, dim, k)
            if ranked is not None:
                return ranked
        return self._top_k_py(concept_blob, dim, k)

    def _top_k_sql(
        self, concept_blob: bytes, dim: int, k: int
    ) -> list[tuple[str, float]] | None:
        """sqlite-vec 의 ``vec_distance_cosine`` + ORDER BY 로 brute-force KNN (명세 권장 방식).

        같은 차원의 ticker 벡터만 대상 (vec_distance_cosine 은 차원불일치 시 raise).
        실패 시 None → Python fallback.
        """
        try:
            cur = self._conn.execute(
                """
                SELECT key, vec_distance_cosine(vec_f32(vec), vec_f32(?)) AS dist
                FROM vectors
                WHERE kind='ticker' AND dim=?
                ORDER BY dist ASC
                LIMIT ?
                """,
                (concept_blob, dim, k),
            )
            rows = cur.fetchall()
        except sqlite3.Error:
            return None
        out: list[tuple[str, float]] = []
        for key, dist in rows:
            if dist is None or math.isnan(float(dist)):
                continue
            out.append((key, 1.0 - float(dist)))
        return out

    def _top_k_py(
        self, concept_blob: bytes, dim: int, k: int
    ) -> list[tuple[str, float]]:
        """순수 Python brute-force KNN (확장 미가용 fallback)."""
        cv = _unpack(concept_blob)
        scored: list[tuple[str, float]] = []
        for key, blob, vdim in self._conn.execute(
            "SELECT key, vec, dim FROM vectors WHERE kind='ticker'"
        ):
            if vdim != dim:
                continue
            sim = _cosine(_unpack(blob), cv)
            if sim is not None:
                scored.append((key, sim))
        scored.sort(key=lambda kv: kv[1], reverse=True)
        return scored[:k]

    def attributes_for(self, ticker: str) -> Mapping[str, Any]:
        cur = self._conn.execute(
            "SELECT data FROM scalars WHERE ticker=?", (ticker,)
        )
        row = cur.fetchone()
        return json.loads(row[0]) if row else {}

    def close(self) -> None:
        self._conn.close()
