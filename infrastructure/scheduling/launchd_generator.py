"""
infrastructure/scheduling/launchd_generator.py — schedules.yaml → launchd plist.

governance/schedules.yaml (SSoT) 의 각 schedule entry 를 읽어 macOS launchd
plist XML 을 emit 한다. plist 의 첫 줄은 AUTO-GENERATED 마커로 시작하며,
드리프트 탐지를 위한 lock 파일 (schedules.lock.yaml) 을 동시에 갱신한다.

설계 원칙:
  - 본 generator 는 OS 경계의 유일한 derived artifact 작성자다.
  - emit 한 plist 의 손편집은 drift_audit.py 의 SHA256 비교로 다음 SessionStart
    hook 에서 finding 으로 노출된다.
  - .env 등 secret 은 본 module 이 읽지 않는다. 환경변수도 schedule.
    environment 의 non-secret key 만 plist 에 박는다.
  - 산출물 디렉토리 (~/Library/LaunchAgents) 는 alias 부재 — macOS launchd
    convention 으로 하드코딩 (Linux/Windows generator 는 별도 추가 예정).

CLI:
  python3 -m infrastructure.scheduling.launchd_generator [--dry-run]

Hook / install.sh 가 본 module 을 호출한다. 직접 launchctl 등록은 본 module
이 하지 않으며, install.sh 가 후속 launchctl bootstrap 을 담당한다.

isomorphic 참조:
  - governance/schedules.yaml 가 schedule SSoT — 본 module 은 단방향 emit (derived).
  - governance/thresholds.yaml 의 정량 SSoT 와 동형 — 단방향 emit.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import yaml

from infrastructure.scheduling._labels import LABEL_PREFIX

# ============================================================
# Repo root (이 파일은 <repo>/infrastructure/scheduling/launchd_generator.py)
# ============================================================
REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR_PATH = Path(__file__).resolve()

# ============================================================
# 상수 — macOS launchd convention. Linux/Windows generator 는 별도.
# ============================================================
LAUNCHAGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
# LABEL_PREFIX 는 infrastructure.scheduling._labels 에서 import (SSoT).

# AUTO-GENERATED 마커. drift_audit 가 본 문자열 prefix 로 plist 인식.
AUTO_GEN_MARKER_PREFIX = "<!-- AUTO-GENERATED"


# ============================================================
# Utility
# ============================================================
def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_of_file(path: Path) -> str:
    return sha256_of(path.read_text(encoding="utf-8"))


def kst_now_iso() -> str:
    """KST 현재 시각 (ISO 8601, second precision)."""
    kst = timezone(timedelta(hours=9))
    return datetime.now(tz=kst).replace(microsecond=0).isoformat()


def expand_aliases(value: str, env_overrides: dict[str, str] | None = None) -> str:
    """schedules.yaml 의 $ALIAS / ${ALIAS} 표기를 환경변수로 치환.

    env_overrides 가 주어지면 우선, 아니면 os.environ 사용. 미해결 alias 는
    raise (silent pass-through 금지 — generator 가 SSoT 의 정합 강제).
    """
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    # $VAR / ${VAR} 양식 모두 지원
    import re

    pattern = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}|\$([A-Z_][A-Z0-9_]*)")

    def _sub(m: re.Match[str]) -> str:
        key = m.group(1) or m.group(2)
        if key in env:
            return env[key]
        raise KeyError(f"alias 미해결: ${key} — install.sh / generator 의 환경변수 export 확인")

    return pattern.sub(_sub, value)


def cron_to_calendar_interval(cron_expr: str) -> dict[str, int]:
    """5-field cron expression → launchd StartCalendarInterval dict.

    "30 7 * * *" → {Minute: 30, Hour: 7}
    "* * * * *" (모든 와일드카드) → {} (실용성 0, raise)
    """
    fields = cron_expr.split()
    if len(fields) != 5:
        raise ValueError(f"cron expression 필드 5개 아님: {cron_expr!r}")
    minute, hour, day_of_month, month, day_of_week = fields
    result: dict[str, int] = {}
    if minute != "*":
        result["Minute"] = int(minute)
    if hour != "*":
        result["Hour"] = int(hour)
    if day_of_month != "*":
        result["Day"] = int(day_of_month)
    if month != "*":
        result["Month"] = int(month)
    if day_of_week != "*":
        # launchd Weekday: 0=Sun, 1=Mon, ..., 7=Sun (cron 과 동일)
        result["Weekday"] = int(day_of_week)
    if not result:
        raise ValueError(f"cron expression 전체 와일드카드 — schedules.yaml 검토 필요: {cron_expr!r}")
    return result


# ============================================================
# plist emit
# ============================================================
def emit_plist(schedule_key: str, schedule: dict[str, Any], src_sha: str) -> tuple[str, Path]:
    """단일 schedule entry → plist XML 문자열 + 산출 경로.

    plist 첫 줄에 AUTO-GENERATED 마커 + source SHA + generator SHA + emit 시각.
    Label / ProgramArguments / StartCalendarInterval / WakeSystem / EnvironmentVariables
    / Std{Out,Err}Path / ProcessType / LowPriorityIO / RunAtLoad 등 채택.
    """
    label = f"{LABEL_PREFIX}.{schedule_key}"
    out_path = LAUNCHAGENTS_DIR / f"{label}.plist"

    # 필드 추출 + alias 확장
    command = expand_aliases(schedule["command"])
    working_dir = expand_aliases(schedule.get("working_dir", "$REPO_ROOT"))
    stdout_path = expand_aliases(schedule["stdout_path"])
    stderr_path = expand_aliases(schedule["stderr_path"])

    env_block = ""
    env = schedule.get("environment", {}) or {}
    if env:
        env_lines = ["  <key>EnvironmentVariables</key>", "  <dict>"]
        for k, v in env.items():
            env_lines.append(f"    <key>{k}</key>")
            env_lines.append(f"    <string>{expand_aliases(str(v))}</string>")
        env_lines.append("  </dict>")
        env_block = "\n".join(env_lines)

    cal = cron_to_calendar_interval(schedule["cron"])
    cal_lines = ["  <key>StartCalendarInterval</key>", "  <dict>"]
    for k, v in cal.items():
        cal_lines.append(f"    <key>{k}</key>")
        cal_lines.append(f"    <integer>{v}</integer>")
    cal_lines.append("  </dict>")
    cal_block = "\n".join(cal_lines)

    wake_block = ""
    wake_cfg = schedule.get("wake", {}) or {}
    if wake_cfg.get("enabled"):
        # WakeSystem 은 plist 가 powerd 에 wake hint 등록. pmset 의 백업.
        wake_block = "  <key>WakeSystem</key>\n  <true/>"

    process_type = schedule.get("process_type", "Background")
    low_prio_io = "true" if schedule.get("low_priority_io") else "false"

    header = (
        f"{AUTO_GEN_MARKER_PREFIX} from governance/schedules.yaml@{src_sha[:12]} "
        f"by infrastructure/scheduling/launchd_generator.py "
        f"at {kst_now_iso()}. DO NOT EDIT — 손편집 시 drift_audit 가 finding 발행. -->"
    )

    plist_body = f"""{header}
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>{command}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>{working_dir}</string>
{cal_block}
  <key>RunAtLoad</key>
  <false/>
{wake_block}
  <key>ProcessType</key>
  <string>{process_type}</string>
  <key>LowPriorityIO</key>
  <{low_prio_io}/>
{env_block}
  <key>StandardOutPath</key>
  <string>{stdout_path}</string>
  <key>StandardErrorPath</key>
  <string>{stderr_path}</string>
</dict>
</plist>
"""
    # 빈 줄 정리
    cleaned = "\n".join(line for line in plist_body.splitlines() if line.strip() or "\n" in line)
    return cleaned + "\n", out_path


# ============================================================
# lock 파일 갱신
# ============================================================
def write_lock(emitted: dict[str, dict[str, str]], lock_path: Path, src_sha: str) -> None:
    """schedules.lock.yaml 갱신.

    artifacts:
      "<absolute plist path>":
        sha256: "<hex>"
        source_sha: "<schedules.yaml sha>"
        generator: "infrastructure/scheduling/launchd_generator.py"
        emit_time: "<kst iso>"
    """
    lock_data = {
        "version": "1.0",
        "description": "Scheduler artifact lock — generated by infrastructure/scheduling/*_generator.py. Hand-edit 금지.",
        "schema": "investment-schedules-lock-v1",
        "last_updated": kst_now_iso(),
        "source": {
            "schedules_yaml_sha256": src_sha,
        },
        "artifacts": emitted,
    }
    lock_path.write_text(
        "# AUTO-GENERATED by infrastructure/scheduling/launchd_generator.py — DO NOT EDIT\n"
        + yaml.safe_dump(lock_data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


# ============================================================
# main
# ============================================================
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="plist / lock 파일 작성 없이 emit 결과만 stdout 에 출력",
    )
    args = parser.parse_args()

    # 경로 환경변수 미설정 시 generator 자체에서 REPO_ROOT 기준 default 주입 —
    # CLI 단독 실행 가능. install.sh 가 export 한 값이 있으면 그것이 우선.
    os.environ.setdefault("REPO_ROOT", str(REPO_ROOT))
    os.environ.setdefault("LAUNCHD_LOG_DIR", str(REPO_ROOT / "telemetry/logs/launchd"))
    os.environ.setdefault("SCHEDULER_STATE_DIR", str(REPO_ROOT / "telemetry/audit/scheduler-state"))
    os.environ.setdefault("AUDIT_DIR", str(REPO_ROOT / "telemetry/audit"))
    os.environ.setdefault("VENV_PYTHON", str(REPO_ROOT / ".venv/bin/python3"))

    # SSoT 로드
    schedules_path = Path(os.environ.get("SCHEDULES_PATH", REPO_ROOT / "governance" / "schedules.yaml"))
    lock_path = Path(os.environ.get("SCHEDULES_LOCK_PATH", REPO_ROOT / "governance" / "schedules.lock.yaml"))
    if not schedules_path.exists():
        print(f"[launchd_generator] FATAL: {schedules_path} 없음", file=sys.stderr)
        return 2
    src_text = schedules_path.read_text(encoding="utf-8")
    src_sha = sha256_of(src_text)
    schedules = yaml.safe_load(src_text) or {}

    LAUNCHAGENTS_DIR.mkdir(parents=True, exist_ok=True)

    emitted: dict[str, dict[str, str]] = {}
    for key, schedule in (schedules.get("schedules") or {}).items():
        if not schedule.get("enabled", True):
            print(f"[launchd_generator] skip (disabled): {key}", file=sys.stderr)
            continue
        plist_xml, plist_path = emit_plist(key, schedule, src_sha)
        if args.dry_run:
            print(f"--- DRY-RUN: {plist_path} ---")
            print(plist_xml)
            continue
        plist_path.write_text(plist_xml, encoding="utf-8")
        artifact_sha = sha256_of(plist_xml)
        emitted[str(plist_path)] = {
            "sha256": artifact_sha,
            "source_sha": src_sha,
            "generator": "infrastructure/scheduling/launchd_generator.py",
            "emit_time": kst_now_iso(),
            "schedule_key": key,
        }
        print(f"[launchd_generator] emit: {plist_path} (sha256={artifact_sha[:12]}...)")

    if not args.dry_run and emitted:
        write_lock(emitted, lock_path, src_sha)
        print(f"[launchd_generator] lock updated: {lock_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
