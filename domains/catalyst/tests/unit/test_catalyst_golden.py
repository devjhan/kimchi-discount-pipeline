"""Golden snapshot — 신 ``catalyst.main`` 1-step 출력 회귀 가드.

snapshot ``fixtures/golden_03_catalyst_events.json`` 은 구 ``alpha_factory`` 3-step
pipeline 과 *증명된 byte-동일* 출력에서 캡처됐다 (old==new equivalence 는 catalyst BC
마이그레이션 커밋에서 검증; alpha_factory 삭제 후엔 본 snapshot 이 회귀 가드 역할).
비교 대상은 substantive 필드 (schema/date/stats/catalysts/d_type_orphans/warnings);
envelope metadata (generated_at/config_path/config_version) 는 의도적 차이라 제외.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_SNAPSHOT = Path(__file__).parent / "fixtures" / "golden_03_catalyst_events.json"

FIXED_TS = "2026-05-15T15:30:00+09:00"
DATE = "2026-05-15"
# 멀티문자 secret 값 — secret_safe_log 가 warning 본문의 우연한 단일문자 (s/k 등)
# 를 redact 하지 않도록 (single-char secret 은 pathological test 입력).
TEST_ENV = {"DART_API_KEY": "DARTKEY123", "KIS_APP_KEY": "KISKEY123", "KIS_APP_SECRET": "KISSECRET123"}

# ----------------------------------------------------------------------
# Mocked DART disclosures (keyed by pblntf_ty)
# ----------------------------------------------------------------------
_DART_B = [  # 자사주 소각 + 분할
    {"report_nm": "자기주식소각 결정", "stock_code": "000001", "rcept_no": "R001", "rcept_dt": "20260510"},
    {"report_nm": "이익소각 결정", "stock_code": "000006", "rcept_no": "R006", "rcept_dt": "20260510"},
    {"report_nm": "회사분할 결정", "stock_code": "000002", "rcept_no": "R002", "rcept_dt": "20260511"},
]
_DART_D = [  # 5% 대량보유 (d_type)
    {"report_nm": "주식등의대량보유상황보고서", "stock_code": "000005", "flr_nm": "행동주의펀드", "rcept_no": "R005", "rcept_dt": "20260512"},
    {"report_nm": "주식등의대량보유상황보고서", "stock_code": "000006", "flr_nm": "어떤펀드", "rcept_no": "R066", "rcept_dt": "20260512"},
]
_DART_I = [  # 지수 편출 + 실적 발표 (둘 다 pblntf_ty=I)
    {"report_nm": "KOSPI200 정기변경 편입제외 안내", "stock_code": "000003", "corp_name": "인덱스종목", "rcept_no": "R003", "rcept_dt": "20260513"},
    {"report_nm": "영업(잠정)실적 (공정공시)", "stock_code": "000004", "corp_name": "실적종목", "rcept_no": "R004", "rcept_dt": "20260514"},
]
_KIS_ROWS = [  # KR:000004 어닝 발표 (20260514) 전후 — drop -15%
    {"stck_bsop_date": "20260513", "stck_clpr": "10000"},
    {"stck_bsop_date": "20260514", "stck_clpr": "9000"},
    {"stck_bsop_date": "20260515", "stck_clpr": "8500"},
]


def _fake_iter_disclosures(api_key, *, bgn_de, end_de, pblntf_ty=None, corp_code=None):
    if pblntf_ty == "B":
        return list(_DART_B)
    if pblntf_ty == "D":
        return list(_DART_D)
    if pblntf_ty == "I":
        return list(_DART_I)
    return []


def _fake_fetch_daily_ohlcv(**kwargs):
    return list(_KIS_ROWS)


def _write_fixtures(trail: Path) -> None:
    trail.mkdir(parents=True, exist_ok=True)
    universe = {
        "schema": "investment-stage1-universe-v1",
        "entries": [
            {"ticker": "KR:000001", "name": "소각주", "source_category": "manual_addition", "metadata": {"market": "KOSPI"}},
            {"ticker": "KR:000002", "name": "분할주", "source_category": "manual_addition", "metadata": {"market": "KOSPI"}},
            {"ticker": "KR:000003", "name": "인덱스종목", "source_category": "manual_addition", "metadata": {"market": "KOSPI"}},
            {"ticker": "KR:000004", "name": "실적종목", "source_category": "manual_addition", "metadata": {"market": "KOSPI"}},
            {"ticker": "KR:000005", "name": "행동주의표적", "source_category": "manual_addition", "metadata": {"market": "KOSPI"}},
            {"ticker": "KR:000006", "name": "소각플러스행동", "source_category": "manual_addition", "metadata": {"market": "KOSPI"}},
        ],
    }
    quality = {
        "schema": "investment-stage2-quality-filter-v1",
        "verdicts": [
            {"ticker": "KR:000001", "verdict": "pass"},
            {"ticker": "KR:000002", "verdict": "pass"},
            {"ticker": "KR:000003", "verdict": "fail"},
            {"ticker": "KR:000004", "verdict": "pass"},
            {"ticker": "KR:000006", "verdict": "pass"},
        ],
    }
    (trail / "01-universe.json").write_text(json.dumps(universe), encoding="utf-8")
    (trail / "02-quality-filter.json").write_text(json.dumps(quality), encoding="utf-8")


_SUBSTANTIVE = ("schema", "date", "stats", "catalysts", "d_type_orphans", "warnings")


def _substantive(payload: dict) -> dict:
    return {k: payload.get(k) for k in _SUBSTANTIVE}


def _run_new(monkeypatch, trail: Path) -> dict:
    monkeypatch.setenv("TRAIL_TODAY", str(trail))
    # nav-history store 격리 (empty) — list_parents()=[] 이라 nav detector 가
    # 결정론적으로 skip (golden parity: "manual map 비어있음" warning 보존).
    monkeypatch.setenv("NAV_HISTORY_DIR", str(trail / "_navhist"))
    from domains.catalyst import _boundary
    import domains.catalyst.main as new_main

    monkeypatch.setattr(_boundary, "load_env", lambda *a, **k: dict(TEST_ENV))
    monkeypatch.setattr(_boundary, "now_iso_kst", lambda: FIXED_TS)
    monkeypatch.setattr(_boundary, "resolve_allow_yahoo_fallback", lambda v: False)
    monkeypatch.setattr("infrastructure.dart.client.iter_disclosures", _fake_iter_disclosures)
    monkeypatch.setattr("infrastructure.dart.client.has_dart_key", lambda env: bool(env.get("DART_API_KEY")))
    monkeypatch.setattr("infrastructure.kis.client.has_kis_keys", lambda env: True)
    monkeypatch.setattr("infrastructure.kis.client.issue_access_token", lambda env, cache_path=None: "tok")
    monkeypatch.setattr("infrastructure.kis.client.fetch_daily_ohlcv", _fake_fetch_daily_ohlcv)

    assert new_main.main(["--date", DATE]) == 0
    return json.loads((trail / "03-catalyst-events.json").read_text(encoding="utf-8"))


@pytest.mark.unit
def test_catalyst_output_matches_golden_snapshot(monkeypatch, tmp_path) -> None:
    """신 파이프라인 substantive 출력이 frozen golden snapshot 과 byte 동일 (회귀 가드)."""
    trail = Path(tmp_path) / "g"
    _write_fixtures(trail)
    with monkeypatch.context() as m:
        new = _run_new(m, trail)
    expected = json.loads(_SNAPSHOT.read_text(encoding="utf-8"))
    assert _substantive(new) == expected


@pytest.mark.unit
def test_catalyst_new_detects_expected(monkeypatch, tmp_path) -> None:
    """신 파이프라인 산출 내용 first-principles 확인 (augment / orphan / quality marker)."""
    trail = Path(tmp_path) / "n"
    _write_fixtures(trail)
    with monkeypatch.context() as m:
        new = _run_new(m, trail)

    by_ticker = {c["ticker"]: c for c in new["catalysts"]}
    # primary catalysts: 000001(treasury) 000002(spin) 000003(index) 000004(earnings) 000006(treasury)
    assert set(by_ticker) == {"KR:000001", "KR:000002", "KR:000003", "KR:000004", "KR:000006"}
    # 000006 = treasury(primary) + activist(d_type) → augment 부착
    assert "d_type_augments" in by_ticker["KR:000006"]["metadata"]
    # 000005 = activist 단독 → d_type orphan (candidates 제외)
    orphans = {c["ticker"] for c in new["d_type_orphans"]}
    assert orphans == {"KR:000005"}
    # earnings triggered (drop -15% ≤ -10%)
    assert by_ticker["KR:000004"]["catalyst_type"] == "earnings_panic"
    assert by_ticker["KR:000004"]["metadata"]["one_day_drop_pct"] == -0.15
    # quality marker: 000003 fail → False, 000001 pass → True
    assert by_ticker["KR:000003"]["metadata"]["quality_pass_at_stage2"] is False
    assert by_ticker["KR:000001"]["metadata"]["quality_pass_at_stage2"] is True
    # nav warning 보존 (holding_companies 비어있음)
    assert any("holding_companies_subsidiaries manual map 비어있음" in w for w in new["warnings"])
