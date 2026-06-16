"""universe bounded context 의 외부 의존 단일 게이트 (anti-corruption layer).

``domains/screener/_boundary.py`` 와 isomorphic 패턴. 다른 universe 모듈은
외부 시스템 (infrastructure._common, infrastructure.dart, infrastructure.kis,
infrastructure.yahoo, os.environ, file system path alias) 에 직접 접근하지
않고 본 모듈을 통과한다.

Run 5 시점 export:
- Path / time / citation / env 기본 helper
- ``load_sources_config`` / ``load_enrichers_config`` / ``load_sub_config`` /
  ``config_path`` (config/ 로더)
- ``base_report_envelope`` (D-Q-2 envelope wrapper) + ``resolve_trail_dir`` (trail path) +
  ``emit_summary`` (stage handoff stdout line) + ``resolve_allow_yahoo_fallback``
- ``write_output_safely`` (G20 — 같은 경로 collision 시 .{N}.json 보존)
- DART API: ``dart_has_key``, ``dart_load_corp_index``, ``dart_load_corp_full_index``,
  ``dart_parse_subsidiary_table``, ``dart_merge_with_manual_ssot``,
  ``dart_iter_disclosures``, ``dart_discover_preferred_pairs``,
  ``dart_merge_preferred_pairs``, ``DartUnavailable``
- KIS API: ``kis_has_keys``, ``kis_issue_access_token``, ``kis_fetch_current_price``,
  ``kis_fetch_daily_ohlcv``, ``KisUnavailable``
- Yahoo API: ``yahoo_fetch_daily_ohlcv``, ``yahoo_krx_to_yahoo``, ``YahooUnavailable``

후속 Run 확장:
- Run 6: audit invariants 완성 (citation 검증 등)

새 외부 의존 추가 시 AGENTS.md + .guidelines/03-boundaries.md 동시 갱신 의무.
"""
from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from datetime import timedelta
from pathlib import Path
from typing import Any

from infrastructure._common import utils as _utils
from infrastructure.dart import client as _dart
from infrastructure.dart import holding_subsidiaries_parser as _dart_subs
from infrastructure.dart import preferred_pairs_parser as _dart_pref
from infrastructure.embedding import client as _embedding
from infrastructure.kis import client as _kis
from infrastructure.vectorstore.store import SqliteVectorStore as _SqliteVectorStore
from infrastructure.yahoo import client as _yahoo

KST = _utils.KST

# DART / KIS / Yahoo exception re-export — caller 의 except 절에서 사용.
DartUnavailable = _dart.DartUnavailable
KisUnavailable = _kis.KisUnavailable
YahooUnavailable = _yahoo.YahooUnavailable


# ----------------------------------------------------------------------
# Path / time / citation
# ----------------------------------------------------------------------


def resolve_path(alias: str, *, date: str | None = None) -> Path:
    """경로 alias → Path. 본 함수가 universe 의 경로 해석 단일 지점 (REPO_ROOT 직접)."""
    if alias == "operations_audit":
        return _utils.audit_dir()
    if alias == "trail_today":
        return _utils.trail_dir(date)
    if alias == "dart_cache":
        return _utils.repo_path(".cache", "dart")
    if alias == "kis_token":
        return _utils.repo_path("secrets", ".kis_token.json")
    raise KeyError(f"universe._boundary.resolve_path: unknown alias {alias!r}")


def profiles_root() -> Path:
    """``governance/policy/profiles/ticker`` 절대경로 — ProfileRegistry(root=...) 주입용 (ADR-0014)."""
    return _utils.ticker_profiles_dir()


# ----------------------------------------------------------------------
# Segment 계층 (부분집합 profile) — root 주입 + 임베딩/벡터 adapter factory.
# 임베딩/벡터 I/O 는 본 _boundary 만 infra 를 import (불변식 C). kernel(SegmentResolver
# / build)은 EmbeddingPort / VectorIndexPort / TickerTextSource Protocol 만 받는다.
# ----------------------------------------------------------------------
def segments_root() -> Path:
    """``governance/policy/segments`` — SegmentRegistry(root=...) 주입용."""
    return _utils.segments_dir()


def concepts_root() -> Path:
    """``governance/policy/concepts`` — ConceptRegistry(root=...) 주입용."""
    return _utils.concepts_dir()


def segment_profiles_root() -> Path:
    """``governance/policy/profiles/segment`` — SegmentProfileRegistry(root=...) 주입용 (ADR-0014)."""
    return _utils.segment_profiles_dir()


def vector_store_path() -> Path:
    """``telemetry/segments/vectors.sqlite`` — 벡터 저장소 경로 (모델 버전 증거)."""
    return _utils.segment_vector_store_path()


def vector_index(db_path: Path | None = None) -> Any:
    """VectorIndexPort 구현(sqlite-vec 가속) 반환. 경로 미지정 → 기본 telemetry 경로."""
    return _SqliteVectorStore(db_path or _utils.segment_vector_store_path())


def embedding_port(env: dict[str, str], *, dry_run: bool = False) -> Any:
    """EmbeddingPort 구현 반환. 키 부재 → available=False (semantic graceful skip).

    transport 는 ``infrastructure.embedding.client.embed_texts`` 에 키/모델 바인딩.
    """
    from domains._shared.adapters.embedding_remote import RemoteEmbeddingAdapter

    api_key = env.get("EMBEDDING_API_KEY", "")
    model = _embedding.resolve_model(env)
    base_url = _embedding.resolve_base_url(env)

    def _transport(texts: list[str]) -> tuple[list[list[float]], str, int]:
        return _embedding.embed_texts(
            texts, api_key=api_key, base_url=base_url, model=model
        )

    return RemoteEmbeddingAdapter(
        transport=_transport,
        model_id=model,
        available=bool(api_key),
        dry_run=dry_run,
    )


def embedding_has_key(env: dict[str, str]) -> bool:
    """``.env`` 의 EMBEDDING_API_KEY 존재 검사 (값 자체는 노출 금지, G21)."""
    return _embedding.has_embedding_key(env)


# 임베딩 입력 cap (chars) — text-embedding-3-* per-input 8191 토큰 한계 회피 (G8 graceful 보강).
_EMBED_TEXT_MAX_CHARS = 2000


def ticker_text_source(env: dict[str, str], *, lookback_days: int = 460) -> Any | None:
    """DART 사업보고서 MD&A(이사의 경영진단) 기반 TickerTextSource (Task 6 production source).

    벡터 인덱스 build 의 per-ticker 임베딩 텍스트 출처. corp_index(stock_code→corp_code) 와
    최신 사업보고서 검색 날짜창(기본 ~15개월)을 바인딩한 fetch 를 ``DartTickerTextSource`` 에
    주입한다. DART 키 부재 / corp_index 로드 실패 → ``None`` (build 는 수기 source 만 사용 —
    graceful). 본 source 는 종목별 fetch 실패 시 '' 반환.

    텍스트 우선순위 (핸드오프 §4 2-a / §11): **MD&A(이사의 경영진단 및 분석의견)** 1차 —
    경영진의 추세·전망 서술이라 지주/운영 코호트 분리 신호가 강하다. MD&A 부재/추출 실패
    (보고서 미제출/비정형) → **'사업의 내용'** fallback (운영 사실이라도 빈 텍스트보다 낫다).

    NOTE: DART document.xml 본문 추출은 best-effort (인코딩·포맷 비정형) — 운영 투입 전 실제
    보고서로 검증 필요(라이브 하네스 applications.verify_dart_business_content --section mda).
    """
    if not _dart.has_dart_key(env):
        return None
    api_key = env.get("DART_API_KEY", "")
    try:
        corp_index = _dart.load_or_fetch_corp_code_index(
            api_key, resolve_path("dart_cache") / "corp_index.json"
        )
    except _dart.DartUnavailable:
        return None

    end = datetime.now(KST).date()
    bgn = end - timedelta(days=lookback_days)
    bgn_de, end_de = bgn.isoformat(), end.isoformat()

    def _fetch(corp_code: str) -> str:
        # MD&A 1차 — 코호트 분리 신호 강함 (Task 6 §4 2-a). 부재/추출 실패 시 사업의 내용
        # fallback (§11 기본 정책). 둘 다 실패하면 DartTickerTextSource 가 '' 로 degrade.
        try:
            return _dart.fetch_mda(
                api_key, corp_code=corp_code, bgn_de=bgn_de, end_de=end_de
            )
        except _dart.DartUnavailable:
            return _dart.fetch_business_content(
                api_key, corp_code=corp_code, bgn_de=bgn_de, end_de=end_de
            )

    from domains._shared.adapters.ticker_text import DartTickerTextSource

    # 임베딩 입력 길이 cap — text-embedding-3-* 의 per-input 한계는 8191 토큰.
    # 한국어 MD&A 본문(~20000자)은 이를 크게 초과해 OpenAI 가 400 을 반환하므로, 의미 신호가
    # 가장 강한 머리말만 임베딩한다. 2000자는 최악 토큰밀도에서도 한계 이내(여유 마진) +
    # 코호트 분류에 충분한 경영진단 개요 신호.
    return DartTickerTextSource(
        fetch=_fetch, corp_index=corp_index, max_chars=_EMBED_TEXT_MAX_CHARS
    )


def now_kst() -> datetime:
    """현재 KST datetime (tz-aware)."""
    return datetime.now(KST)


def now_iso_kst() -> str:
    """현재 KST 시각의 ISO8601 표현 (citation timestamp 용)."""
    return _utils.now_iso_kst()


def is_trading_day(target: _date) -> bool:
    """KRX 거래일 여부 (utils.is_trading_day 의 date wrapper)."""
    return _utils.is_trading_day(target.isoformat())


def format_citation(source: str, ts: str, value: Any) -> str:
    """G7 형식 citation 문자열: ``{SOURCE}@{ISO_KST}={VALUE}``."""
    return _utils.format_citation(source, ts, value)


# ----------------------------------------------------------------------
# Env / secret
# ----------------------------------------------------------------------


def load_env(path: Path | str | None = None) -> dict[str, str]:
    """``.env`` 로드. infrastructure 위임. secret 키도 dict 에 포함되지만
    본문 / 산출물 / stdout 노출은 secret_safe_log 가 자동 redact.
    """
    return _utils.load_env_file(path)


def secret_safe_log(msg: str, env: dict[str, str]) -> str:
    """env 의 secret 값을 ``***REDACTED***`` 로 치환한 메시지 반환."""
    return _utils.secret_safe_log(msg, env)


# ----------------------------------------------------------------------
# Output emit
# ----------------------------------------------------------------------


def write_output_safely(out_path: Path, payload: Any) -> Path:
    """G20 — 같은 경로 collision 시 ``.{N}.json`` suffix 자동 부여 후 write."""
    return _utils.write_output_safely(out_path, payload)


def resolve_trail_dir(date: str | None = None) -> Path:
    """오늘 (또는 지정 일자) 의 trail 디렉토리 절대경로 반환 (= $TRAIL_TODAY).

    mkdir 은 caller 책임. 본 함수는 ``_utils.trail_dir(date)`` 의 wrapper.
    """
    return _utils.trail_dir(date)


def base_report_envelope(
    *,
    schema: str,
    date: str,
    config_path: Path | str,
    config_version: int | str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """D-Q-2 stage envelope (schema / generated_at / date / config_path / config_version).

    각 stage 가 ``entries`` / ``stats`` / ``warnings`` 등을 자체 schema 로 추가.
    """
    return _utils.base_report_envelope(
        schema=schema,
        date=date,
        config_path=config_path,
        config_version=config_version,
        extra=extra,
    )


def emit_summary(stage: str, summary: dict[str, Any], out_path: Path) -> None:
    """D-Q-6 표준 stage handoff 1줄 stdout emit."""
    _utils.emit_summary_line(stage_name=stage, summary=summary, out_path=out_path)


def resolve_allow_yahoo_fallback(cli_value: bool | None) -> bool:
    """KIS 미가용 시 Yahoo public endpoint 사용 여부.

    ``cli_value`` 가 True/False 면 그대로, None 이면 ``config/user/behavior.yaml``
    의 ``allow_yahoo_fallback`` 키 사용 (기본 False — 정확한 출처 우선).
    """
    return _utils.resolve_allow_yahoo_fallback(cli_value)


# ----------------------------------------------------------------------
# Config loaders — universe 내부 config/ 디렉토리 한정
# ----------------------------------------------------------------------


def _config_root() -> Path:
    return Path(__file__).resolve().parent / "config"


def load_sources_config() -> dict[str, Any]:
    """``config/sources.yaml`` 로드 — 활성화된 source 목록 + 각각의 spec."""
    return _utils.load_yaml_config(_config_root() / "sources.yaml")


def load_enrichers_config() -> dict[str, Any]:
    """``config/enrichers.yaml`` 로드 — 활성화된 enricher 목록 + 각각의 spec."""
    return _utils.load_yaml_config(_config_root() / "enrichers.yaml")


def load_sub_config(filename: str) -> dict[str, Any]:
    """``config/{filename}`` 로드 — items_ref / subsidiaries_map_ref 외부화 용.

    ``filename`` 은 단순 basename (예: ``"subsidiaries.yaml"``). path 분리자
    포함 시 ValueError (config root 탈출 방지). BC-local *reference data* 전용
    (subsidiaries / preferred_pairs). 사용자 결정(manual_additions/exclusions)은
    ``load_user_config`` (config/user/) — ADR-0015.
    """
    if "/" in filename or ".." in filename:
        raise ValueError(f"load_sub_config: 단순 basename 만 허용 (got: {filename!r})")
    return _utils.load_yaml_config(_config_root() / filename)


def load_user_config(filename: str) -> dict[str, Any]:
    """``config/user/{filename}`` graceful load (미존재 → {}) — 사용자 universe 결정 (ADR-0015).

    manual_additions / exclusions 는 developer doctrine(governance) 도 mechanical
    wiring(BC config) 도 아닌 *사용자 override* 라 config/user/ 거주 (ADR-0002 ownership
    axis). gitignored worktree 부재 시 graceful {} (G8). basename only.
    """
    return _utils.load_user_config_optional(filename)


def config_path(filename: str) -> Path:
    """config 파일의 절대 경로. envelope ``config_path`` 인자 / 디버깅 용."""
    if "/" in filename or ".." in filename:
        raise ValueError(f"config_path: 단순 basename 만 허용 (got: {filename!r})")
    return _config_root() / filename


# ----------------------------------------------------------------------
# DART API — single gate (자체 HTTP 호출 금지)
# ----------------------------------------------------------------------


def dart_has_key(env: dict[str, str]) -> bool:
    """``.env`` 의 DART_API_KEY 존재 검사 (값 자체는 노출 금지)."""
    return _dart.has_dart_key(env)


def dart_load_corp_index(api_key: str, cache_path: Path | None = None) -> dict[str, str]:
    """6자리 stock_code → 8자리 corp_code 매핑. infrastructure 위임."""
    return _dart.load_or_fetch_corp_code_index(api_key, cache_path)


def dart_load_corp_full_index(api_key: str, cache_path: Path | None = None) -> dict[str, Any]:
    """corp_code → 회사 metadata 전체 매핑 (사업보고서 fetch 용 보조 인덱스)."""
    return _dart.load_or_fetch_corp_full_index(api_key, cache_path)


def dart_parse_subsidiary_table(
    parent_corp_code: str,
    *,
    bsns_year: str,
    env: dict[str, str],
    corp_full_index: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """지주사 출자현황 표 파싱 → (auto_entries, warnings).

    parser 결과는 *비결정적* — 사용자가 manual SSoT 와 merge 후 검토 권장.
    """
    return _dart_subs.parse_subsidiary_table(
        parent_corp_code,
        bsns_year=bsns_year,
        env=env,
        corp_full_index=corp_full_index,
    )


def dart_merge_with_manual_ssot(
    auto_entries: list[dict[str, Any]],
    manual_entries: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """auto-parsed entries + manual SSoT merge. manual 우선."""
    return _dart_subs.merge_with_manual_ssot(auto_entries, manual_entries)


def dart_iter_disclosures(
    api_key: str,
    *,
    bgn_de: str,
    end_de: str,
    pblntf_ty: str | None = None,
    corp_code: str | None = None,
) -> Any:
    """DART /api/list.json 페이지 iter 위임. 실패 시 ``DartUnavailable`` raise.

    DartDisclosureFilter (Run 3) 의 단일 DART 진입점.
    """
    return _dart.iter_disclosures(
        api_key,
        bgn_de=bgn_de,
        end_de=end_de,
        pblntf_ty=pblntf_ty,
        corp_code=corp_code,
    )


def dart_discover_preferred_pairs(
    env: dict[str, str],
) -> tuple[list[dict[str, Any]], list[str]]:
    """KRX 상장정보 기반 우선주/보통주 페어 자동 발견 (best-effort)."""
    return _dart_pref.discover_pairs_from_listing(env)


def dart_merge_preferred_pairs(
    auto_pairs: list[dict[str, Any]],
    manual_pairs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """auto + manual 페어 merge. manual 우선."""
    return _dart_pref.merge_with_manual_pairs(auto_pairs, manual_pairs)


# ----------------------------------------------------------------------
# KIS API — single gate
# ----------------------------------------------------------------------


def kis_has_keys(env: dict[str, str]) -> bool:
    """``.env`` 의 KIS_APP_KEY / KIS_APP_SECRET 존재 검사."""
    return _kis.has_kis_keys(env)


def kis_issue_access_token(env: dict[str, str], cache_path: Path | None = None) -> str:
    """KIS access token 발급 (cache 파일이 valid 하면 재사용)."""
    return _kis.issue_access_token(env, cache_path=cache_path)


def kis_fetch_current_price(
    *,
    token: str,
    app_key: str,
    app_secret: str,
    stock_code: str,
) -> dict[str, Any]:
    """KIS 현재가 조회 (시총 / 상장주식수 / 종가 포함)."""
    return _kis.fetch_current_price(
        token=token, app_key=app_key, app_secret=app_secret, stock_code=stock_code
    )


def kis_fetch_daily_ohlcv(
    *,
    token: str,
    app_key: str,
    app_secret: str,
    stock_code: str,
    period_days: int = 100,
    end_date: str | None = None,
    adjusted: bool = True,
) -> list[dict[str, Any]]:
    """KIS 일봉 시세 (최대 100일 / 호출). 더 긴 lookback 은 caller 가 분할 호출."""
    return _kis.fetch_daily_ohlcv(
        token=token,
        app_key=app_key,
        app_secret=app_secret,
        stock_code=stock_code,
        period_days=period_days,
        end_date=end_date,
        adjusted=adjusted,
    )


# ----------------------------------------------------------------------
# Yahoo Finance — single gate (KIS fallback)
# ----------------------------------------------------------------------


def yahoo_krx_to_yahoo(stock_code: str, market: str = "KOSPI") -> str:
    """KRX 6자리 stock_code → Yahoo ticker 문자열 (예: ``005930.KS``)."""
    return _yahoo.krx_to_yahoo(stock_code, market)


def yahoo_fetch_daily_ohlcv(
    ticker: str, period_days: int = 750
) -> list[dict[str, Any]]:
    """Yahoo public chart endpoint — 일봉 fetch. 무인증."""
    return _yahoo.fetch_daily_ohlcv(ticker, period_days=period_days)
