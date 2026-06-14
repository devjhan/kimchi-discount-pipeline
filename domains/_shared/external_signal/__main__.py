"""CLI 엔트리포인트 — external signal 파일 검증 게이트.

    python -m domains._shared.external_signal --validate <file>
    python -m domains._shared.external_signal --validate-all

error 가 1건이라도 있으면 exit 1 (daily_pipeline 게이트 호환). warning 은 통과(exit 0).
디렉토리 해석(``--validate-all``)만 ``infrastructure._common.utils`` 를 import 한다 —
entrypoint 관례(domains/*/main.py 와 동형); 코어 ``validate.py`` 는 순수 유지.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from domains._shared.external_signal.validate import (
    ValidationResult,
    validate_signal_file,
)


def _print_result(res: ValidationResult) -> None:
    status = "OK" if res.ok else "FAIL"
    print(f"[{status}] {res.path}")
    for e in res.errors:
        print(f"    error: {e}")
    for w in res.warnings:
        print(f"    warn:  {w}")


def _collect_targets(args: argparse.Namespace) -> list[Path]:
    if args.validate:
        return [Path(args.validate)]
    # --validate-all: intake 디렉토리 스캔 (dir 해석만 infra import)
    from infrastructure._common.utils import external_signal_intake_dir

    root = external_signal_intake_dir()
    if not root.exists():
        return []
    return sorted(root.rglob("*.md"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m domains._shared.external_signal",
        description="external signal ingest 산출물 schema validator (G7/G20).",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--validate", metavar="FILE", help="단일 signal 파일 검증")
    group.add_argument(
        "--validate-all",
        action="store_true",
        help="intake 디렉토리(telemetry/external_signals) 전체 검증",
    )
    args = parser.parse_args(argv)

    targets = _collect_targets(args)
    if not targets:
        print("검증 대상 signal 파일 없음 (intake 디렉토리 비어있음).")
        return 0

    failed = 0
    for path in targets:
        res = validate_signal_file(path)
        _print_result(res)
        if not res.ok:
            failed += 1

    print(f"\n검증 완료: {len(targets)}개 중 {failed}개 FAIL.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
