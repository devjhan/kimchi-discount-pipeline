"""policy bounded context 의 외부 의존 단일 게이트 (anti-corruption layer).

macro / universe / screener 의 ``_boundary.py`` 와 isomorphic. 다른 policy 모듈은
``infrastructure.*`` / ``os.environ`` / utils path helper 직접 호출 금지 — 본 모듈 통과.

export:
- Path / time / citation / env / output
- ``profiles_root`` (registry root) / ``drafts_dir`` (ephemeral draft 디렉토리)
- ``write_output_safely`` (JSON — draft 용) / ``write_profile_safely`` (YAML — commit 용)
- DART: ``dart_has_key`` / ``dart_iter_disclosures`` (intake용), ``DartUnavailable``
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from infrastructure._common import utils as _utils
from infrastructure.dart import client as _dart

KST = _utils.KST

DartUnavailable = _dart.DartUnavailable


# ----------------------------------------------------------------------
# Path / time / citation
# ----------------------------------------------------------------------


def resolve_path(alias: str, *, date: str | None = None) -> Path:
    """경로 alias → Path. policy 의 경로 해석 단일 지점 (REPO_ROOT 직접)."""
    if alias == "operations_audit":
        return _utils.audit_dir()
    if alias == "trail_today":
        return _utils.trail_dir(date)
    raise KeyError(f"policy._boundary.resolve_path: unknown alias {alias!r}")


def profiles_root() -> Path:
    """``governance/policy/profiles`` 절대경로 — ProfileRegistry(root=...) 주입용."""
    return _utils.profiles_dir()


def drafts_dir() -> Path:
    """``telemetry/policy_drafts`` — commit 전 후보 draft (gitignored, ephemeral)."""
    return _utils.policy_drafts_dir()


def now_kst() -> datetime:
    return datetime.now(KST)


def now_iso_kst() -> str:
    return _utils.now_iso_kst()


def format_citation(source: str, ts: str, value: Any) -> str:
    return _utils.format_citation(source, ts, value)


# ----------------------------------------------------------------------
# Env / secret
# ----------------------------------------------------------------------


def load_env(path: Path | str | None = None) -> dict[str, str]:
    return _utils.load_env_file(path)


def secret_safe_log(msg: str, env: dict[str, str]) -> str:
    return _utils.secret_safe_log(msg, env)


# ----------------------------------------------------------------------
# Output — draft(JSON) vs commit(YAML)
# ----------------------------------------------------------------------


def write_output_safely(out_path: Path, payload: Any) -> Path:
    """G20 collision-safe JSON write — ephemeral draft 용."""
    return _utils.write_output_safely(out_path, payload)


def write_profile_safely(out_path: Path, payload: Any) -> Path:
    """G20 collision-safe YAML write — governance/policy/profiles 의 사람-리뷰 SSoT commit 용."""
    return _utils.write_yaml_safely(out_path, payload)


# ----------------------------------------------------------------------
# DART API — single gate (intake 용)
# ----------------------------------------------------------------------


def dart_has_key(env: dict[str, str]) -> bool:
    return _dart.has_dart_key(env)


def dart_iter_disclosures(api_key: str, *, bgn_de: str, end_de: str, **kw: Any) -> Any:
    """DART /api/list.json 페이지 iter 위임 (intake 용). 실패 시 DartUnavailable."""
    return _dart.iter_disclosures(api_key, bgn_de=bgn_de, end_de=end_de, **kw)
