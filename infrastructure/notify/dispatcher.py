#!/usr/bin/env python3
"""
infrastructure/notify/dispatcher.py — daily brief notification dispatcher.

NOTIFY_CHANNELS env (`slack,gmail` 식 CSV) 또는 명시 인자로 활성 채널 list 결정,
각 채널 adapter 의 render → validate → send 를 순차 호출 후 결과 dict 반환.

CLI:
    python -m infrastructure.notify.dispatcher --brief operations/2026-05-09/daily-brief.md \
        [--channels slack,gmail] [--dry-run] [--out-json -]

산출:
    JSON dict — { channel: {status, skip_reason, error, payload} }
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from infrastructure._common.utils import load_env_file, secret_safe_log
from infrastructure.notify import REGISTRY, AdapterResult, BriefBlocked, NotifierAdapter


def _merged_env(base: dict[str, str] | None) -> dict[str, str]:
    """`.env` (local dev) + `os.environ`. os.environ
    가 우선 — runtime env 가 local override 를 정상 표현하기 위함.
    """
    out: dict[str, str] = {}
    if base:
        out.update(base)
    for k, v in os.environ.items():
        if v:
            out[k] = v
    return out


def _resolve_channels(channels: list[str] | None, env: dict[str, str]) -> list[str]:
    if channels:
        return channels
    raw = (env.get("NOTIFY_CHANNELS") or "email,telegram").strip()
    return [c.strip() for c in raw.split(",") if c.strip()]


def dispatch_brief(
    brief_md: str,
    *,
    channels: list[str] | None = None,
    dry_run: bool = False,
    env: dict[str, str] | None = None,
) -> dict[str, AdapterResult]:
    """채널별 adapter 실행. 한 채널 실패해도 나머지 진행 (graceful degrade).

    Args:
        brief_md: daily brief markdown 본문 (skill 산출).
        channels: 활성 채널 list. None 이면 NOTIFY_CHANNELS env.
        dry_run: True 면 외부 송신 없이 payload 검증만.
        env: load_env_file() 결과. None 이면 자동 load.

    Returns:
        dict mapping channel name → AdapterResult.
    """
    env = _merged_env(env if env is not None else load_env_file())
    active = _resolve_channels(channels, env)
    results: dict[str, AdapterResult] = {}

    for ch in active:
        adapter_cls = REGISTRY.get(ch)
        if adapter_cls is None:
            results[ch] = AdapterResult(
                channel=ch,
                status="skipped",
                skip_reason=f"unknown channel '{ch}' (registry: {sorted(REGISTRY)})",
            )
            continue
        adapter: NotifierAdapter = adapter_cls(env=env)
        ready, missing = adapter.is_ready()
        if not ready:
            results[ch] = AdapterResult(
                channel=ch, status="skipped", skip_reason=missing
            )
            continue
        try:
            adapter.validate_brief(brief_md)
        except BriefBlocked as exc:
            results[ch] = AdapterResult(channel=ch, status="blocked", error=str(exc))
            continue
        try:
            payload = adapter.render(brief_md)
        except NotImplementedError as exc:
            results[ch] = AdapterResult(
                channel=ch, status="skipped", skip_reason=f"adapter_deferred: {exc}"
            )
            continue
        try:
            result = adapter.send(payload, dry_run=dry_run)
        except Exception as exc:  # noqa: BLE001
            result = AdapterResult(
                channel=ch,
                status="error",
                payload=payload,
                error=secret_safe_log(str(exc), env),
            )
        results[ch] = result

    return results


def register_adapter(name: str, adapter_cls: type[NotifierAdapter]) -> None:
    """외부 plugin 추가용 hook. 본 함수 호출 후 dispatcher 가 같은 process 내
    이후 dispatch 부터 사용 가능.
    """
    REGISTRY[name] = adapter_cls


def _serialize(results: dict[str, AdapterResult]) -> dict[str, dict[str, Any]]:
    return {ch: asdict(r) for ch, r in results.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily brief notification dispatcher")
    parser.add_argument(
        "--brief",
        required=True,
        help="brief markdown 파일 경로 (보통 $TRAIL_TODAY/daily-brief.md)",
    )
    parser.add_argument(
        "--channels",
        default=None,
        help="활성 채널 CSV (예: slack,gmail). 미지정 시 NOTIFY_CHANNELS env",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="외부 송신 없이 검증 + payload 출력만",
    )
    parser.add_argument(
        "--out-json",
        default="-",
        help="결과 JSON 출력 경로. '-' = stdout (default)",
    )
    args = parser.parse_args()

    brief_path = Path(args.brief)
    if not brief_path.exists():
        print(f"[ERROR] brief 파일 없음: {brief_path}", file=sys.stderr)
        return 2

    channels = (
        [c.strip() for c in args.channels.split(",") if c.strip()]
        if args.channels
        else None
    )
    brief_md = brief_path.read_text(encoding="utf-8")
    results = dispatch_brief(brief_md, channels=channels, dry_run=args.dry_run)
    payload_out = _serialize(results)

    rendered = json.dumps(payload_out, ensure_ascii=False, indent=2)
    if args.out_json == "-":
        sys.stdout.write(rendered + "\n")
    else:
        Path(args.out_json).write_text(rendered + "\n", encoding="utf-8")
        print(f"[notify] results written -> {args.out_json}", file=sys.stderr)

    # exit 0 even on partial fail — caller (routine prompt) 가 본문 status 로 판정
    return 0


if __name__ == "__main__":
    sys.exit(main())
