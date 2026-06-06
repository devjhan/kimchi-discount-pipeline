# ============================================================
# infrastructure/_common/python_env.sh — Python 인터프리터 해석 utility
# ============================================================
#
# 모든 bash entry point (hook / orchestrator / wrapper) 가 source 한다.
# resolve_python() 함수가 .venv/bin/python3 우선, 없으면 system python3 로
# fallback. 이 한 곳에서만 인터프리터 경로를 결정해 drift 를 방지한다.
#
# 사용:
#   source "$REPO_ROOT/infrastructure/_common/python_env.sh"
#   PY="$(resolve_python)"
#   "$PY" -m some.module
#
# 또는 bootstrap 자동 시도까지 포함:
#   source "$REPO_ROOT/infrastructure/_common/python_env.sh"
#   PY="$(resolve_python_or_bootstrap)"
#
# 본 파일은 source 만 의도 — 직접 실행하지 않는다.
# ============================================================

# .venv/bin/python3 우선, 없으면 system python3.
# stdout 으로 절대경로 반환. stderr 에 어떤 인터프리터를 선택했는지 한 줄 기록.
resolve_python() {
  local repo_root="${REPO_ROOT:-}"
  if [ -z "$repo_root" ]; then
    repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  fi
  if [ -n "$repo_root" ] && [ -x "$repo_root/.venv/bin/python3" ]; then
    echo "$repo_root/.venv/bin/python3"
    return 0
  fi
  command -v python3 || {
    echo "[python_env] FATAL: python3 not found in PATH" >&2
    return 1
  }
}

# resolve_python 과 동일하나, .venv 부재 시 bootstrap.sh 를 자동 호출한 뒤
# 재시도. hook 등에서 첫 1회 자동 복구를 원할 때 사용.
resolve_python_or_bootstrap() {
  local repo_root="${REPO_ROOT:-}"
  if [ -z "$repo_root" ]; then
    repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  fi
  if [ -n "$repo_root" ] && [ -x "$repo_root/.venv/bin/python3" ]; then
    echo "$repo_root/.venv/bin/python3"
    return 0
  fi
  if [ -n "$repo_root" ] && [ -x "$repo_root/applications/bootstrap.sh" ]; then
    echo "[python_env] .venv 부재 — bootstrap.sh 자동 호출" >&2
    bash "$repo_root/applications/bootstrap.sh" >&2 || {
      echo "[python_env] bootstrap 실패 — system python3 fallback" >&2
      command -v python3 || return 1
      return 0
    }
    if [ -x "$repo_root/.venv/bin/python3" ]; then
      echo "$repo_root/.venv/bin/python3"
      return 0
    fi
  fi
  command -v python3 || return 1
}
