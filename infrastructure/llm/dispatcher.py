#!/usr/bin/env python3
"""
infrastructure/llm/dispatcher.py — LLM 런타임 호출 dispatcher.

"LLM_VENDOR" env (기본 "deepseek") 로 REGISTRY adapter 선택 후 prompt 실행.
``run_daily_local.sh`` 가 stage4 / stage6 / MCP-notify 호출을 본 dispatcher 경유로
실행 — vendor swap 이 bash 수정 없이 adapter 교체로 끝나게 (F-13 T1).

CLI:
    python -m infrastructure.llm.dispatcher \\
        --prompt "/investment-stage4-thesis-auditor 2026-06-05" \\
        --allowed-tools "Bash,Read,Write,Edit,Glob,Grep" [--vendor claude-cli] [--dry-run]

exit code:
    completed → claude 런타임의 returncode (caller 의 `|| WARN` 가 실패 감지)
    skipped / dry_run → 0 (graceful — 런타임 부재 시 stage skip)
    error / unknown vendor → 1
"""

from __future__ import annotations

import argparse
import os
import sys

from infrastructure.llm import REGISTRY
from infrastructure.llm.adapter import LlmAdapter, LlmResult


def invoke(
    prompt: str,
    *,
    allowed_tools: str = "",
    vendor: str | None = None,
    dry_run: bool = False,
) -> LlmResult:
    """선택된 vendor adapter 로 prompt 실행. unknown vendor → status='error'."""
    vendor = vendor or os.environ.get("LLM_VENDOR") or "deepseek"
    adapter_cls = REGISTRY.get(vendor)
    if adapter_cls is None:
        return LlmResult(
            vendor=vendor,
            status="error",
            error=f"unknown LLM vendor '{vendor}' (registry: {sorted(REGISTRY)})",
        )
    adapter: LlmAdapter = adapter_cls()
    return adapter.invoke(prompt, allowed_tools=allowed_tools, dry_run=dry_run)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="LLM runtime dispatcher (F-13 single port)"
    )
    parser.add_argument(
        "--prompt", required=True, help="skill slash-command 또는 ad-hoc 지시"
    )
    parser.add_argument(
        "--allowed-tools",
        default="",
        help="런타임 tool whitelist CSV (MCP tool UUID 포함 가능)",
    )
    parser.add_argument(
        "--vendor", default=None, help="LLM vendor (기본: $LLM_VENDOR, 없으면 deepseek)"
    )
    parser.add_argument("--dry-run", action="store_true", help="실행 없이 cmd 만 산출")
    args = parser.parse_args(argv)

    result = invoke(
        args.prompt,
        allowed_tools=args.allowed_tools,
        vendor=args.vendor,
        dry_run=args.dry_run,
    )

    # 상태 1줄 stderr (prompt 본문은 미출력 — 길이/노이즈 방지).
    print(
        f"[llm] vendor={result.vendor} status={result.status}"
        + (f" rc={result.returncode}" if result.returncode is not None else "")
        + (f" skip={result.skip_reason}" if result.skip_reason else "")
        + (f" error={result.error}" if result.error else ""),
        file=sys.stderr,
    )

    if result.status == "completed":
        return result.returncode or 0
    if result.status in ("skipped", "dry_run"):
        return 0
    return 1  # error / unknown vendor


if __name__ == "__main__":
    sys.exit(main())
