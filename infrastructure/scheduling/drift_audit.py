"""
infrastructure/scheduling/drift_audit.py — 일별 scheduler-state snapshot.

run_daily_local.sh 의 시작 / 종료 시점에 호출되어 다음을 기록한다:
  1. ~/Library/LaunchAgents/com.kimchidiscountpipeline.*.plist 의 SHA256
  2. governance/schedules.lock.yaml 의 잠금 hash 와의 비교 결과
  3. `launchctl print gui/$UID/<label>` 출력 (state / runs / last_exit_code)
  4. `pmset -g sched` 출력 (wake/repeat 등록 여부)

산출: $SCHEDULER_STATE_DIR/scheduler-state-{YYYY-MM-DD}.json

다음 SessionStart hook (또는 audit-process skill) 이 본 파일을 읽고 다음
finding 발행:
  - hash mismatch → "scheduler_plist_drift" (손편집 의심)
  - launchctl state != "waiting" → "scheduler_agent_not_loaded"
  - pmset wake 누락 → "scheduler_wake_unregistered"
  - lock 에 없는 plist 발견 → "scheduler_unknown_artifact" (governance 우회)

본 module 은 변경을 가하지 않는다 — read-only audit. governance 위반은 보고만 한다.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from infrastructure.scheduling._labels import LABEL_PREFIX

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHAGENTS_DIR = Path.home() / "Library" / "LaunchAgents"


def sha256_of_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def kst_now() -> datetime:
    return datetime.now(tz=timezone(timedelta(hours=9)))


def run_cmd(cmd: list[str], timeout: float = 10.0) -> tuple[int, str, str]:
    """subprocess wrapper — stdout/stderr 캡처. 실패 시 raise 안 함."""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
        return r.returncode, r.stdout, r.stderr
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return 127, "", str(exc)


def collect_plist_state(lock_data: dict[str, Any]) -> list[dict[str, Any]]:
    """LaunchAgents 디렉토리의 com.kimchidiscountpipeline.*.plist 와 lock 대조."""
    results: list[dict[str, Any]] = []
    locked_artifacts: dict[str, dict[str, Any]] = lock_data.get("artifacts", {}) or {}
    seen_paths: set[str] = set()

    for plist_path in sorted(LAUNCHAGENTS_DIR.glob(f"{LABEL_PREFIX}.*.plist")):
        seen_paths.add(str(plist_path))
        entry: dict[str, Any] = {
            "path": str(plist_path),
            "exists": True,
            "sha256_actual": sha256_of_file(plist_path),
        }
        locked = locked_artifacts.get(str(plist_path))
        if locked is None:
            entry["finding"] = "scheduler_unknown_artifact"
            entry["detail"] = (
                "lock 에 없는 plist — 사용자가 직접 작성했거나 다른 generator 가 emit"
            )
        else:
            entry["sha256_locked"] = locked.get("sha256")
            entry["source_sha"] = locked.get("source_sha")
            entry["emit_time"] = locked.get("emit_time")
            if entry["sha256_actual"] != entry["sha256_locked"]:
                entry["finding"] = "scheduler_plist_drift"
                entry["detail"] = (
                    "SHA256 불일치 — plist 손편집 의심. install.sh 재실행 필요."
                )
        results.append(entry)

    # lock 에는 있는데 실제 파일 부재 (사용자가 plist 삭제)
    for locked_path, locked_meta in locked_artifacts.items():
        if locked_path not in seen_paths:
            results.append(
                {
                    "path": locked_path,
                    "exists": False,
                    "sha256_locked": locked_meta.get("sha256"),
                    "finding": "scheduler_artifact_missing",
                    "detail": "lock 에 기록됐으나 파일 부재 — uninstall 또는 손삭제. install.sh 재실행 필요.",
                }
            )

    return results


def collect_launchctl_state() -> dict[str, Any]:
    """launchctl print gui/$UID/<label> 출력 캡처."""
    uid = os.getuid()
    out: dict[str, Any] = {"uid": uid, "agents": {}}
    for plist_path in sorted(LAUNCHAGENTS_DIR.glob(f"{LABEL_PREFIX}.*.plist")):
        label = plist_path.stem
        target = f"gui/{uid}/{label}"
        rc, stdout, stderr = run_cmd(["launchctl", "print", target])
        agent_info: dict[str, Any] = {
            "label": label,
            "loaded": rc == 0,
            "raw_output": stdout if rc == 0 else stderr,
        }
        if rc == 0:
            # state = waiting / running / not yet seen — 단순 정규식 추출
            for line in stdout.splitlines():
                line = line.strip()
                if line.startswith("state ="):
                    agent_info["state"] = line.split("=", 1)[1].strip()
                elif line.startswith("runs ="):
                    agent_info["runs"] = line.split("=", 1)[1].strip()
                elif line.startswith("last exit code ="):
                    agent_info["last_exit_code"] = line.split("=", 1)[1].strip()
            if agent_info.get("state") not in ("waiting", "running"):
                agent_info["finding"] = "scheduler_agent_not_loaded"
                agent_info["detail"] = (
                    f"state={agent_info.get('state')!r} — bootstrap 필요"
                )
        else:
            agent_info["finding"] = "scheduler_agent_not_loaded"
            agent_info["detail"] = "launchctl print 실패 — bootstrap 안 됨"
        out["agents"][label] = agent_info
    return out


def collect_pmset_state() -> dict[str, Any]:
    """pmset -g sched 출력 캡처 + wake 등록 여부."""
    rc, stdout, stderr = run_cmd(["pmset", "-g", "sched"])
    result: dict[str, Any] = {
        "raw_output": stdout if rc == 0 else stderr,
        "wake_registered": False,
    }
    if rc != 0:
        result["finding"] = "scheduler_wake_unregistered"
        result["detail"] = "pmset -g sched 실패"
        return result
    # "wakeorpoweron at 7:25AM" 등 라인 탐지
    for line in stdout.splitlines():
        low = line.lower()
        if "wake" in low or "poweron" in low:
            result["wake_registered"] = True
            break
    if not result["wake_registered"]:
        result["finding"] = "scheduler_wake_unregistered"
        result["detail"] = "pmset 에 wake schedule 미등록 — install.sh 재실행 필요"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase",
        choices=("start", "end"),
        default="end",
        help="run_daily_local.sh 의 시작/종료 phase 표기 (output filename suffix)",
    )
    args = parser.parse_args()

    audit_dir = Path(
        os.environ.get(
            "SCHEDULER_STATE_DIR", REPO_ROOT / "telemetry/audit/scheduler-state"
        )
    )
    audit_dir.mkdir(parents=True, exist_ok=True)

    lock_path = Path(
        os.environ.get(
            "SCHEDULES_LOCK_PATH", REPO_ROOT / "governance/schedules.lock.yaml"
        )
    )
    lock_data: dict[str, Any] = {}
    if lock_path.exists():
        lock_data = yaml.safe_load(lock_path.read_text(encoding="utf-8")) or {}
    else:
        lock_data = {
            "finding_global": "scheduler_lock_missing",
            "detail": f"{lock_path} 없음 — generator 가 한 번도 실행되지 않음",
        }

    snapshot: dict[str, Any] = {
        "schema": "investment-scheduler-state-v1",
        "phase": args.phase,
        "captured_at": kst_now().isoformat(),
        "uid": os.getuid(),
        "lock_path": str(lock_path),
        "lock_loaded": lock_path.exists(),
        "artifacts": collect_plist_state(lock_data) if lock_path.exists() else [],
        "launchctl": collect_launchctl_state(),
        "pmset": collect_pmset_state(),
    }

    # finding 집계 — top-level findings 배열
    findings: list[str] = []
    for art in snapshot["artifacts"]:
        if "finding" in art:
            findings.append(f"{art['finding']}:{art['path']}")
    for label, ag in snapshot["launchctl"]["agents"].items():
        if "finding" in ag:
            findings.append(f"{ag['finding']}:{label}")
    if "finding" in snapshot["pmset"]:
        findings.append(snapshot["pmset"]["finding"])
    snapshot["findings"] = findings
    snapshot["finding_count"] = len(findings)

    date = kst_now().strftime("%Y-%m-%d")
    out_path = audit_dir / f"scheduler-state-{date}.{args.phase}.json"
    out_path.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[drift_audit] {out_path} (findings={len(findings)})")
    if findings:
        for f in findings:
            print(f"[drift_audit] FINDING: {f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
