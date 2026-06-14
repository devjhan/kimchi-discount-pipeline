"""screener bounded context 의 외부 의존 단일 게이트 (anti-corruption layer).

다른 screener 모듈은 외부 시스템 (infrastructure._common, infrastructure.dart,
os.environ, file system 경로) 에 직접 접근하지 않고 본 모듈을 통과한다.
새 외부 의존 추가 시 AGENTS.md + .guidelines/05-boundaries.md 동시 갱신 의무.
"""
from __future__ import annotations

from datetime import date as _date
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from infrastructure._common import utils as _utils
from infrastructure.dart import client as _dart
from infrastructure.vectorstore.store import SqliteVectorStore as _SqliteVectorStore

from domains._shared.policy_profile import serde as _policy_serde
from domains._shared.ports.citation import CitationPort
from domains._shared.segment_registry import _versioning

KST = _utils.KST

# DART module-level constants re-export (raw infrastructure import 우회용).
DART_REPRT_CODE_ANNUAL = _dart.REPRT_CODE_ANNUAL
DART_REPRT_CODE_HALF = _dart.REPRT_CODE_HALF
DART_REPRT_CODE_Q1 = _dart.REPRT_CODE_Q1
DART_REPRT_CODE_Q3 = _dart.REPRT_CODE_Q3
DART_FS_DIV_CONSOLIDATED = _dart.FS_DIV_CONSOLIDATED
DART_FS_DIV_SEPARATE = _dart.FS_DIV_SEPARATE

# DART exception re-export — caller 의 except 절에서 사용.
DartUnavailable = _dart.DartUnavailable


# ----------------------------------------------------------------------
# Path / time / citation
# ----------------------------------------------------------------------


def resolve_path(alias: str, *, date: str | None = None) -> Path:
    """경로 alias → Path. 본 함수가 screener 의 경로 해석 단일 지점 (REPO_ROOT 직접)."""
    if alias == "trail_today":
        return _utils.trail_dir(date)
    if alias == "operations_audit":
        return _utils.audit_dir()
    if alias == "financials_cache":
        return _utils.repo_path(".cache", "financials")
    if alias == "dart_cache":
        return _utils.repo_path(".cache", "dart")
    raise KeyError(f"screener._boundary.resolve_path: unknown alias {alias!r}")


def profiles_root() -> Path:
    """``governance/policy/profiles/ticker`` 절대경로 — ProfileRegistry(root=...) 주입용 (ADR-0014)."""
    return _utils.ticker_profiles_dir()


# ----------------------------------------------------------------------
# Segment 계층 (부분집합 profile) — read-only 소비 (Task 10).
# screener 는 segment 인덱스를 *읽기* 만 한다 (cosine/top_k/scalar 조회). 임베딩
# 생성(EmbeddingPort)은 build 단계(universe boundary)의 책임이라 여기엔 없다.
# kernel(SegmentResolver)은 VectorIndexPort Protocol 만 받고, 본 _boundary 가
# sqlite-vec 백엔드를 주입한다 (불변식 C — infra import 는 boundary 한정).
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
    """``telemetry/segments/vectors.sqlite`` — 벡터 인덱스 경로 (모델 버전 증거)."""
    return _utils.segment_vector_store_path()


def vector_index(db_path: Path | None = None) -> Any:
    """VectorIndexPort 구현(sqlite-vec 가속) 반환. 경로 미지정 → 기본 telemetry 경로.

    인덱스 파일이 없으면 빈 store 가 생성되고 cosine/top_k 는 None/[] 을 돌려
    semantic leaf 가 UNKNOWN 으로 격하된다 (G8/G11 — build 미실행 시 정상 degrade).
    """
    return _SqliteVectorStore(db_path or _utils.segment_vector_store_path())


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


class _CitationAdapter:
    """CitationPort impl — ``_utils.format_citation`` 에 위임 (infra 게이트)."""

    def format(self, source: str, ts: str, value: Any) -> str:
        """G7 citation 문자열 — free fn ``format_citation`` 과 byte-identical."""
        return _utils.format_citation(source, ts, value)


def citation_adapter() -> CitationPort:
    """CitationPort 어댑터 factory — composition root(main) 주입용.

    application/io 는 본 factory 가 반환한 port 에만 의존한다 — ``format_citation``
    free fn 직접 호출 대신 주입된 port 사용 (feature-first hexagonal seam, Phase 0).
    """
    return _CitationAdapter()


# ----------------------------------------------------------------------
# Output emit
# ----------------------------------------------------------------------


def emit_summary(stage: str, summary: dict[str, Any], out_path: Path) -> None:
    """D-Q-6 표준 stage handoff 1줄을 stdout 으로 emit."""
    _utils.emit_summary_line(stage_name=stage, summary=summary, out_path=out_path)


def write_envelope(
    out_path: Path,
    payload: dict[str, Any],
    *,
    schema: str,
    date: str,
    config_path: Path | None = None,
    config_version: str | int | None = None,
    warnings: list[str] | None = None,
) -> Path:
    """D-Q-2 envelope (schema/generated_at/date/config_version/warnings/items)
    감싸기 + ``.{N}.json`` suffix 보존을 _common.utils 에 위임.

    ``warnings`` 는 envelope 의 top-level 키로 들어가도록 extra 에 packing.
    """
    envelope = _utils.base_report_envelope(
        schema=schema,
        date=date,
        config_path=str(config_path) if config_path is not None else "",
        config_version=config_version if config_version is not None else "",
        extra={"warnings": warnings or []},
    )
    envelope.update(payload)
    return _utils.write_output_safely(out_path, envelope)


# ----------------------------------------------------------------------
# Config loaders — screener 내부 config/ 디렉토리 한정
# ----------------------------------------------------------------------


def _latest_version_path(root: Path, name: str) -> Path:
    """``<root>/<name>/v<N>.yaml`` 최신 버전 경로 (ADR-0014 versioned global/strategy).

    버전 디렉토리가 없거나 비면 ``v1.yaml`` 경로를 돌려준다(load_yaml_config 가 부재 시
    SystemExit — fail-loud). _versioning 은 segment/concept registry 와 동일 규약.
    """
    versions = _versioning.sorted_versions(root / _versioning.id_dir(name))
    version = versions[-1] if versions else 1
    return _versioning.version_path(root, name, version)


def load_profile(name: str) -> dict[str, Any]:
    """``governance/policy/profiles/global/{name}/v{N}.yaml`` 최신 버전 → RuleFactory 소비 shape.

    ADR-0014: global 정책도 versioned-dir(``profiles/global/<name>/v<N>.yaml``) 로 통일.
    on-disk 는 통합 ``policy-profile-v1`` (scope=global, ``cutoff_rules:``). RuleFactory 는
    profile 의 rule 트리를 ``["rule"]`` 키에서 읽으므로(decision 3 — cutoff *평가* 는
    RuleFactory 소유), 본 어댑터가 통합 스키마를 RuleFactory 가 기대하는 ``{"name", "rule",
    "qualitative_lenses", "description"}`` dict 로 투영한다. 구 ``screener-profile-v1``
    (``rule:`` 키)도 ``policy_profile.serde`` legacy 게이트로 수용.
    """
    raw = _utils.load_yaml_config(_latest_version_path(_utils.global_profiles_dir(), name))
    pp = _policy_serde.from_dict(raw)
    return {
        "name": pp.key,
        "rule": dict(pp.cutoff_rules),
        "qualitative_lenses": list(pp.qualitative_lenses),
        "description": pp.description,
    }


def load_strategy(name: str) -> dict[str, Any]:
    """``governance/policy/strategies/{name}/v{N}.yaml`` 최신 버전. profile 조합 + constants (ADR-0014)."""
    return _utils.load_yaml_config(_latest_version_path(_utils.strategies_dir(), name))


def load_hard_guards() -> dict[str, Any]:
    """``governance/policy/hard_guards.yaml`` 로드. strategy-agnostic 잠금 영역 (ADR-0014 singleton)."""
    return _utils.load_yaml_config(_utils.hard_guards_path())


def profile_path(name: str) -> Path:
    """global profile YAML 최신 버전 실제 경로 — write_envelope 의 ``config_path`` 인자용."""
    return _latest_version_path(_utils.global_profiles_dir(), name)


def strategy_path(name: str) -> Path:
    """strategy YAML 최신 버전 실제 경로 — write_envelope 의 ``config_path`` 인자용."""
    return _latest_version_path(_utils.strategies_dir(), name)


# ----------------------------------------------------------------------
# DART API — single gate (자체 HTTP 호출 금지)
# ----------------------------------------------------------------------


def load_env(path: Path | str | None = None) -> dict[str, str]:
    """``.env`` 로드. infrastructure 위임. secret 키도 dict 에 포함되지만
    본문 / 산출물 / stdout 노출은 secret_safe_log 가 자동 redact.
    """
    return _utils.load_env_file(path)


def secret_safe_log(msg: str, env: dict[str, str]) -> str:
    """env 의 secret 값을 ``***REDACTED***`` 로 치환한 메시지 반환."""
    return _utils.secret_safe_log(msg, env)


def dart_load_corp_index(api_key: str, cache_path: Path | None = None) -> dict[str, str]:
    """6자리 stock_code → 8자리 corp_code 매핑. infrastructure 위임."""
    return _dart.load_or_fetch_corp_code_index(api_key, cache_path)


def dart_has_key(env: dict[str, str]) -> bool:
    """``.env`` 의 DART_API_KEY 존재 검사 (값 자체는 노출 금지)."""
    return _dart.has_dart_key(env)


def dart_fetch_financial_statements(
    api_key: str,
    *,
    corp_code: str,
    bsns_year: str,
    reprt_code: str = DART_REPRT_CODE_ANNUAL,
    fs_div: str = DART_FS_DIV_CONSOLIDATED,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    """DART /api/fnlttSinglAcntAll.json 위임. 실패 시 DartUnavailable raise."""
    return _dart.fetch_financial_statements(
        api_key,
        corp_code=corp_code,
        bsns_year=bsns_year,
        reprt_code=reprt_code,
        fs_div=fs_div,
        timeout=timeout,
    )


def dart_iter_disclosures(
    api_key: str,
    *,
    bgn_de: str,
    end_de: str,
    pblntf_ty: str,
    corp_code: str | None = None,
) -> Iterable[dict[str, Any]]:
    """DART /api/list.json 페이지 iter 위임. 실패 시 DartUnavailable raise."""
    return _dart.iter_disclosures(
        api_key,
        bgn_de=bgn_de,
        end_de=end_de,
        pblntf_ty=pblntf_ty,
        corp_code=corp_code,
    )
