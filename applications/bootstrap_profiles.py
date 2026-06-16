"""applications/bootstrap_profiles.py — cold-start 프로파일 부트스트랩 러너 (Phase 6 cold-start).

종목 리스트를 받아 종목마다 ``[phase1 intake → (사람: /policy-profiler 스킬 → draft)
→ phase3 commit]`` 를 순차 구동하는 얇은 오케스트레이터. commit / drift / version /
provenance 산술은 **절대 재구현하지 않고** ``domains.policy.main`` 의 결정론 진입점
(intake / ``--commit-draft``)을 그대로 재사용한다 (F-10 — LLM·스킬은 commit 안 하고,
본 러너도 commit 산술을 보유하지 않는다). cold-start 의 변화는 "사람의 세션 왕복 N회"
가 "1 러너 호출 + 종목별 스킬 invoke" 로 바뀌는 것뿐 — 거버넌스(F-10/G20/G7/drift)는 무손상.

usage:
    # phase 1 — 종목별 intake 산출 (스킬 input). 이후 사람이 /policy-profiler 로 draft 작성.
    python -m applications.bootstrap_profiles --tickers KR:003550 KR:005930 --phase intake
    python -m applications.bootstrap_profiles --tickers-file watchlist.txt  --phase intake

    # phase 3 — draft 존재 종목 일괄 commit (draft 없는 종목은 "대기" 리포트 — 비-에러)
    python -m applications.bootstrap_profiles --tickers-file watchlist.txt  --phase commit

    # all — intake 후 commit 시도 (대개 draft 미작성 → 대기; 스킬 작성 후 재실행으로 resume)
    python -m applications.bootstrap_profiles --tickers KR:003550 --phase all

산출/소비:
- intake → ``telemetry/policy_drafts/{ticker}/_intake-{date}.json`` (policy.main phase1)
- commit → ``governance/policy/profiles/ticker/{ticker}/vN.yaml`` (policy.main --commit-draft)
- commit 성공 시 active draft 를 ``_profile-draft-{date}.committed.json`` 로 archive →
  재실행 멱등(active draft 부재 + committed marker 존재 → "done", 재-commit 안 함;
  G20 append-only 보존). 사람이 새 draft 를 다시 두면 amendment 로 commit(v+1).

자동 매매 / 사이즈 / Kelly / LLM 호출 일체 없음 (G6/G9). 네트워크 없음 (manual trigger).
exit 0 = 모든 종목 committed/done/waiting. exit 2 = malformed/blocked draft 또는 형식위반 ticker.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date as _date
from datetime import datetime
from pathlib import Path

from domains._shared.time.clock import AsOfClock, now_kst
from domains.policy import _boundary as policy_boundary
from domains.policy import main as policy_main

STAGE_NAME = "bootstrap-profiles"
_TICKER_RE = re.compile(r"^KR:\d{6}$")
_DEFAULT_DRIFT_THRESHOLD = 0.5


def _parse_date(s: str | None) -> _date:
    if s:
        return datetime.strptime(s, "%Y-%m-%d").date()
    return now_kst().date()


def _date_iso(s: str | None) -> str:
    """policy.main 과 동일 규칙으로 거래일 ISO 산출 (intake/draft 파일명 정합)."""
    return AsOfClock.at_market_close(_parse_date(s)).trading_date.isoformat()


def _ticker_dir(ticker: str) -> str:
    return ticker.replace(":", "_")


def load_tickers(
    cli_tickers: list[str] | None, tickers_file: str | None
) -> tuple[list[str], list[str]]:
    """(valid, invalid) — CLI + 파일 병합, 순서 보존 dedup, ``KR:NNNNNN`` 형식 검증."""
    raw: list[str] = list(cli_tickers or [])
    if tickers_file:
        p = Path(tickers_file)
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s and not s.startswith("#"):
                    raw.append(s)
    valid: list[str] = []
    invalid: list[str] = []
    seen: set[str] = set()
    for t in raw:
        if t in seen:
            continue
        seen.add(t)
        (valid if _TICKER_RE.match(t) else invalid).append(t)
    return valid, invalid


def _intake_one(ticker: str, trigger: str, date_iso: str) -> int:
    """phase1 위임 — ``policy.main --dry-run`` (engine 미주입 = intake-only)."""
    return policy_main.main(
        ["--ticker", ticker, "--trigger", trigger, "--dry-run", "--date", date_iso]
    )


def _find_active_draft(tdir: Path, date_iso: str) -> Path | None:
    """active(미-commit) draft 탐색 — exact date 우선, 없으면 최신 ``_profile-draft-*.json``."""
    if not tdir.exists():
        return None
    exact = tdir / f"_profile-draft-{date_iso}.json"
    if exact.exists():
        return exact
    cands = sorted(
        p
        for p in tdir.glob("_profile-draft-*.json")
        if not p.name.endswith(".committed.json")
    )
    return cands[-1] if cands else None


def _has_committed_marker(tdir: Path) -> bool:
    return tdir.exists() and any(tdir.glob("_profile-draft-*.committed.json"))


def _precheck_draft(path: Path) -> tuple[bool, str]:
    """commit 전 경량 구조 검증 (malformed↔blocked 구분 보고용; 권위 검증은 commit_profile)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"JSON 파싱 실패: {exc}"
    payload = raw.get("payload", raw) if isinstance(raw, dict) else {}
    if not isinstance(payload, dict) or not payload.get("ticker"):
        return False, "ticker 필드 누락"
    cutoff = payload.get("cutoff_rules")
    if not isinstance(cutoff, dict) or "type" not in cutoff:
        return False, "cutoff_rules(type) 누락"
    return True, ""


def _commit_one(ticker: str, date_iso: str, *, drift_threshold: float) -> str:
    """phase3 위임 + 멱등 archive. status ∈ {committed, done, waiting, malformed, blocked}."""
    tdir = policy_boundary.drafts_dir() / _ticker_dir(ticker)
    draft = _find_active_draft(tdir, date_iso)
    if draft is None:
        return "done" if _has_committed_marker(tdir) else "waiting"
    ok, reason = _precheck_draft(draft)
    if not ok:
        print(f"[{STAGE_NAME}] {ticker}: malformed draft — {reason}", file=sys.stderr)
        return "malformed"
    rc = policy_main.main(
        [
            "--commit-draft",
            str(draft),
            "--date",
            date_iso,
            "--drift-threshold",
            str(drift_threshold),
        ]
    )
    if rc == 0:
        archived = draft.with_name(draft.stem + ".committed.json")
        try:
            draft.rename(archived)
        except OSError:
            # archive 실패해도 commit 자체는 성공 — 다음 실행서 재-commit 위험만 (보고됨).
            print(
                f"[{STAGE_NAME}] WARN: {ticker} draft archive 실패 — 수기 정리 필요: {draft}",
                file=sys.stderr,
            )
        return "committed"
    return "blocked"


@dataclass
class _Row:
    ticker: str
    intake: str = "-"
    commit: str = "-"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="applications.bootstrap_profiles",
        description="cold-start 프로파일 부트스트랩 — 종목 리스트 순차 intake/commit (F-10 위임).",
    )
    parser.add_argument("--tickers", nargs="+", help="KR:NNNNNN 공백 구분 리스트.")
    parser.add_argument("--tickers-file", help="종목 리스트 파일 (1줄 1티커, # 주석).")
    parser.add_argument(
        "--phase",
        choices=["intake", "commit", "all"],
        default="all",
        help="intake=phase1만 / commit=phase3만 / all=intake후 commit 시도 (기본 all).",
    )
    parser.add_argument("--trigger", default="manual", help='trigger 라벨 (기본 "manual").')
    parser.add_argument("--date", help="YYYY-MM-DD (KST). 기본 오늘 거래일.")
    parser.add_argument(
        "--drift-threshold",
        type=float,
        default=_DEFAULT_DRIFT_THRESHOLD,
        help=f"commit 위임 drift 한계 (기본 {_DEFAULT_DRIFT_THRESHOLD}).",
    )
    args = parser.parse_args(argv)

    date_iso = _date_iso(args.date)
    valid, invalid = load_tickers(args.tickers, args.tickers_file)
    for t in invalid:
        print(
            f"[{STAGE_NAME}] WARN: 형식 위반 ticker skip (KR:NNNNNN 기대): {t!r}",
            file=sys.stderr,
        )
    if not valid and not invalid:
        print(f"[{STAGE_NAME}] 대상 ticker 없음 — Default No-Action")
        return 0

    rows: list[_Row] = []
    errors: list[str] = list(invalid)
    for t in valid:
        row = _Row(ticker=t)
        if args.phase in ("intake", "all"):
            rc = _intake_one(t, args.trigger, date_iso)
            row.intake = "ok" if rc == 0 else f"rc{rc}"
            if rc != 0:
                errors.append(t)
        if args.phase in ("commit", "all"):
            status = _commit_one(t, date_iso, drift_threshold=args.drift_threshold)
            row.commit = status
            if status in ("malformed", "blocked"):
                errors.append(t)
        rows.append(row)

    # ----- report -----
    print(
        f"\n[{STAGE_NAME}] date={date_iso} phase={args.phase} "
        f"tickers={len(valid)} (invalid={len(invalid)})"
    )
    for r in rows:
        print(f"  {r.ticker:12s} intake={r.intake:6s} commit={r.commit}")
    committed = [r.ticker for r in rows if r.commit == "committed"]
    waiting = [r.ticker for r in rows if r.commit == "waiting"]
    if committed:
        print(f"  → committed: {', '.join(committed)}")
    if waiting:
        print(
            f"  → 대기(스킬 draft 미작성): {', '.join(waiting)} "
            f"— /policy-profiler 로 draft 작성 후 재실행"
        )
    print(f"[{STAGE_NAME}] {'OK' if not errors else f'errors: {len(errors)}'}")
    return 2 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
