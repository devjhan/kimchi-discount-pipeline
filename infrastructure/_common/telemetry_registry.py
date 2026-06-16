"""Telemetry Artifact Registry — telemetry/ 산출물 종류의 선언적 SSoT.

본 레지스트리는 telemetry/ 하위에 *체계적으로* 저장되는 모든 산출물 종류(kind)를
선언한다. retention GC(``applications.telemetry_gc``) / context-telemetry 스킬 문서 /
architecture 테스트가 모두 본 레지스트리를 단일 진실원천으로 소비한다.

엔트리 1건 = ``ArtifactKind``:
    - ``kind``            : 고유 식별자.
    - ``glob``           : telemetry/ 루트 기준 상대 glob (해당 kind 의 파일 매칭).
    - ``retention_class``: 보존 정책 (아래 ``RetentionClass``).
    - ``producer_module``: 산출 모듈의 dotted path (None = skill/shell/manual 외부 생산자).
    - ``producer``       : 사람용 생산자 설명.
    - ``scope_segment``  : scope 식별자가 위치한 *상대경로 세그먼트 index* (None = 단일 scope).
    - ``scope_on_stem``  : True 면 scope = 파일명에서 suffix 제거한 stem (nav-history 등).
    - ``id_validator``   : scope 식별자 정규식 (None = 검증 안 함). 실패 → ORPHAN.
    - ``dated``          : 파일명에 ``-{YYYY-MM-DD}`` 가 박혀 일별 이력을 이루는지.

설계 결론(ADR-0008 retention class 정합):
    - 레지스트리는 **현재 살아있는 생산자(ACTIVE kind)** 만 선언한다.
    - 디스크 파일이 어떤 kind glob 에도 매칭되지 않으면 ORPHAN — 생산자 소멸 산출물
      (예: ADR-0010 으로 파기된 hook 의 ``logs/_hook_audit.log``)과 미등록 신규 산출물을
      한 축으로 포착한다.
    - ``id_validator`` 실패(예: ticker dir ``088350`` ∉ ``^KR_\\d+$``)도 ORPHAN.
    - ``producer_module`` 이 지정됐는데 repo 에서 파일이 사라지면 LEGACY(미래 drift 가드).

레이어: 본 모듈은 ``infrastructure._common.utils`` 의 path helper 만 사용하고 domain 모듈을
*import 하지 않는다* — 생산자 존재성은 dotted path → 파일경로 변환 후 ``exists()`` 로만
확인(레이어 회피 + import side-effect 회피).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from infrastructure._common import utils as _utils


class RetentionClass(str, Enum):
    """telemetry 산출물 보존 정책 (ADR-0008 세분)."""

    PERMANENT = "permanent"        # append-only 증거 — distinct date 전부 보존
    STATE = "state"                # living 단일 파일 — GC 미prune (충돌본 정규화만)
    SNAPSHOT = "snapshot"          # point-in-time mirror/파생 — scope별 최신 1건
    BINARY_EVIDENCE = "binary"     # 재생성-불가 바이너리 — 보존
    EPHEMERAL = "ephemeral"        # gitignore — age-prune 대상


@dataclass(frozen=True)
class ArtifactKind:
    kind: str
    glob: str
    retention_class: RetentionClass
    producer_module: str | None
    producer: str
    scope_segment: int | None = None
    scope_on_stem: bool = False
    id_validator: str | None = None
    dated: bool = False


# ticker 식별자 규약: KIS 콜론 sanitize ``KR:003550`` → ``KR_003550`` (positions/README §2).
# bare 6-digit(예: 레거시 ``088350``)은 위반 → ORPHAN.
TICKER_ID_RE = r"^KR_\d+$"


REGISTRY: tuple[ArtifactKind, ...] = (
    # ---- positions/_account (account-level, summary→derived 계보) ----
    ArtifactKind(
        kind="positions_account_summary",
        glob="positions/_account/summary-*.json",
        retention_class=RetentionClass.SNAPSHOT,
        producer_module="domains.risk_engine.positions_sync",
        producer="risk_engine positions_sync (KIS 계좌 read-only sync)",
        dated=True,
    ),
    ArtifactKind(
        kind="positions_account_derived",
        glob="positions/_account/derived-*.json",
        retention_class=RetentionClass.SNAPSHOT,
        producer_module="domains.risk_engine.portfolio_state_derive",
        producer="risk_engine portfolio_state_derive (summary scan 파생)",
        dated=True,
    ),
    # ---- positions/{ticker} (per-ticker) ----
    ArtifactKind(
        kind="positions_ticker_balance",
        glob="positions/*/balance-*.json",
        retention_class=RetentionClass.SNAPSHOT,
        producer_module="domains.risk_engine.positions_sync",
        producer="risk_engine positions_sync (종목별 잔고 스냅샷)",
        scope_segment=1,
        id_validator=TICKER_ID_RE,
        dated=True,
    ),
    ArtifactKind(
        kind="positions_ticker_thesis_json",
        glob="positions/*/thesis.json",
        retention_class=RetentionClass.STATE,
        producer_module="domains.risk_engine.thesis_sync",
        producer="risk_engine thesis_sync (falsifier spec machine state)",
        scope_segment=1,
        id_validator=TICKER_ID_RE,
    ),
    ArtifactKind(
        kind="positions_ticker_thesis_md",
        glob="positions/*/thesis.md",
        retention_class=RetentionClass.STATE,
        producer_module=None,
        producer="stage4-thesis-auditor skill / 사용자 (narrative)",
        scope_segment=1,
        id_validator=TICKER_ID_RE,
    ),
    ArtifactKind(
        kind="positions_ticker_drift",
        glob="positions/*/drift-*.md",
        retention_class=RetentionClass.SNAPSHOT,
        producer_module="domains.risk_engine.falsifier_proximity",
        producer="risk_engine falsifier_proximity (반증 근접도 리포트)",
        scope_segment=1,
        id_validator=TICKER_ID_RE,
        dated=True,
    ),
    ArtifactKind(
        kind="positions_ticker_expiry",
        glob="positions/*/expiry-*.md",
        retention_class=RetentionClass.SNAPSHOT,
        producer_module="domains.risk_engine.thesis_expiry_monitor",
        producer="risk_engine thesis_expiry_monitor (time-horizon 만료 모니터)",
        scope_segment=1,
        id_validator=TICKER_ID_RE,
        dated=True,
    ),
    # ---- nav-history (append-only NAV 시계열 증거, F-14) ----
    ArtifactKind(
        kind="nav_history",
        glob="nav-history/*.jsonl",
        retention_class=RetentionClass.PERMANENT,
        producer_module="domains._shared.nav_history",
        producer="_shared nav_history (지주사 NAV 시계열 append)",
        scope_segment=1,
        scope_on_stem=True,
        id_validator=TICKER_ID_RE,
    ),
    # ---- external_signals (ingest 증거, append-only, redacted) ----
    ArtifactKind(
        kind="external_signal_intake",
        glob="external_signals/*/*.md",
        retention_class=RetentionClass.PERMANENT,
        producer_module=None,
        producer="ingest-external-signal skill (per-ticker fact-only paraphrase)",
        scope_segment=1,
        id_validator=TICKER_ID_RE,
    ),
    # ---- segments (벡터 인덱스, 모델버전 의존 증거 — ADR-0008) ----
    ArtifactKind(
        kind="segments_vector_store",
        glob="segments/vectors.sqlite",
        retention_class=RetentionClass.BINARY_EVIDENCE,
        producer_module="domains.universe.segment_index_main",
        producer="universe segment_index_main (sqlite-vec 임베딩 저장소)",
    ),
    # ---- audit/violations/{bc} (per-BC 위반 audit trail) ----
    ArtifactKind(
        kind="audit_violations",
        glob="audit/violations/*/*.jsonl",
        retention_class=RetentionClass.PERMANENT,
        producer_module="domains._shared.audit.log",
        producer="_shared audit.log ViolationLog (BC별 위반 append)",
        scope_segment=2,
    ),
    # ---- audit/breadth (Stage 0a SPX breadth 스냅샷) ----
    ArtifactKind(
        kind="audit_breadth",
        glob="audit/breadth/macro-breadth-*.json",
        retention_class=RetentionClass.PERMANENT,
        producer_module="domains.macro.breadth_fetch",
        producer="macro breadth_fetch (Stage 0a SPX 200d breadth)",
        dated=True,
    ),
    # ---- audit/subsidiaries (지주사 자회사 audit) ----
    ArtifactKind(
        kind="audit_subsidiaries",
        glob="audit/subsidiaries/subsidiaries-audit-*.json",
        retention_class=RetentionClass.PERMANENT,
        producer_module="domains.universe.sources.holding_company",
        producer="universe HoldingCompanySource (DART 자회사 audit)",
        dated=True,
    ),
    # ---- audit/shadow-portfolio (4-tier paper trade) ----
    ArtifactKind(
        kind="audit_shadow_state",
        glob="audit/shadow-portfolio/state.json",
        retention_class=RetentionClass.STATE,
        producer_module="domains.audit_integrity.main",
        producer="audit_integrity main (4-tier shadow portfolio state)",
    ),
    ArtifactKind(
        kind="audit_shadow_trade_log",
        glob="audit/shadow-portfolio/trade-log-*.csv",
        retention_class=RetentionClass.PERMANENT,
        producer_module="domains.audit_integrity.io.trade_log",
        producer="audit_integrity trade_log (tier별 closed trade append)",
    ),
    # ---- audit/scheduler-state (일별 scheduler drift 스냅샷) ----
    ArtifactKind(
        kind="audit_scheduler_state",
        glob="audit/scheduler-state/scheduler-state-*.json",
        retention_class=RetentionClass.SNAPSHOT,
        producer_module="infrastructure.scheduling.drift_audit",
        producer="scheduling drift_audit (launchd/cron drift 스냅샷)",
        dated=True,
    ),
    # ---- policy_drafts (commit 전 ephemeral, gitignore) ----
    ArtifactKind(
        kind="policy_draft_intake",
        glob="policy_drafts/*/_intake-*.json",
        retention_class=RetentionClass.EPHEMERAL,
        producer_module="domains.policy.main",
        producer="policy main (trigger intake)",
        scope_segment=1,
        id_validator=TICKER_ID_RE,
        dated=True,
    ),
    ArtifactKind(
        kind="policy_draft_profile",
        glob="policy_drafts/*/_profile-draft-*.json",
        retention_class=RetentionClass.EPHEMERAL,
        producer_module=None,
        producer="policy-profiler skill draft + policy main --commit-draft",
        scope_segment=1,
        id_validator=TICKER_ID_RE,
        dated=True,
    ),
    # ---- logs (gitignore, EPHEMERAL — age prune) ----
    ArtifactKind(
        kind="logs_cron",
        glob="logs/cron/run-*.log",
        retention_class=RetentionClass.EPHEMERAL,
        producer_module=None,
        producer="run_daily_local.sh / daily_pipeline.sh (cron stdout/stderr)",
        dated=True,
    ),
)


def telemetry_root() -> Path:
    """GC / 스캐너의 스캔 루트 ($TELEMETRY_DIR override)."""
    return _utils.telemetry_dir()


def _module_to_path(dotted: str) -> Path:
    """dotted module path → repo 내 파일 경로 후보 (``a.b.c`` → a/b/c.py).

    ``a/b/c.py`` 또는 패키지 ``a/b/c/__init__.py`` 둘 중 하나라도 존재하면 그 경로 반환,
    아니면 ``.py`` 후보 경로(미존재)를 반환한다 (caller 가 exists() 로 판정).
    """
    rel = Path(*dotted.split("."))
    module_file = _utils.REPO_ROOT / rel.with_suffix(".py")
    package_init = _utils.REPO_ROOT / rel / "__init__.py"
    if module_file.exists():
        return module_file
    if package_init.exists():
        return package_init
    return module_file


def producer_exists(kind: ArtifactKind) -> bool:
    """kind 의 생산자 모듈이 repo 에 존재하는지. ``producer_module=None`` → True(외부 생산자)."""
    if kind.producer_module is None:
        return True
    return _module_to_path(kind.producer_module).exists()


def kinds_by_name() -> dict[str, ArtifactKind]:
    return {k.kind: k for k in REGISTRY}
