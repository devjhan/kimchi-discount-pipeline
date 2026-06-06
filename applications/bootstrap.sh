#!/usr/bin/env bash
# ============================================================
# applications/bootstrap.sh — repo-local Python venv 초기화 (멱등)
# ============================================================
#
# 목적: PyYAML 등 third-party 의존성을 시스템 python 에 흘리지 않고
# .venv/ 에 격리해 재현성을 확보한다. domains / infrastructure 코드 및
# scheduling generator 가 PyYAML 에 의존한다.
#
# 호출:
#   bash applications/bootstrap.sh                  # 기본 python3 사용
#   PYTHON_BOOTSTRAP=python3.13 bash applications/bootstrap.sh
#
# 멱등성: .venv/ 가 이미 존재하면 venv 재생성 없이 pip install 만 수행.
# requirements.txt 가 갱신된 경우에도 같은 호출로 동기화 가능.
#
# 제약:
#   - 본 script 는 .env 를 읽지 않는다. secret 노출 가능성 0.
#   - sudo 요구 없음. user 권한으로만 동작.
#   - .venv/ 는 .gitignore 에 이미 등록되어 있음.
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

PYTHON_BOOTSTRAP="${PYTHON_BOOTSTRAP:-python3}"
VENV_DIR="$REPO_ROOT/.venv"
REQ_FILE="$REPO_ROOT/requirements.txt"

if [ ! -f "$REQ_FILE" ]; then
  echo "[bootstrap] FATAL: $REQ_FILE 없음" >&2
  exit 2
fi

# venv 생성 (멱등)
if [ ! -x "$VENV_DIR/bin/python3" ]; then
  echo "[bootstrap] creating .venv with $PYTHON_BOOTSTRAP ($("$PYTHON_BOOTSTRAP" --version 2>&1))"
  "$PYTHON_BOOTSTRAP" -m venv "$VENV_DIR"
else
  echo "[bootstrap] .venv 이미 존재 — pip install 만 수행"
fi

# Python 버전 검증 — 3.11 이상 권장 (domains/* 의 신문법 사용)
PY_VER="$("$VENV_DIR/bin/python3" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_MAJOR="${PY_VER%%.*}"
PY_MINOR="${PY_VER##*.}"
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
  echo "[bootstrap] WARN: Python $PY_VER detected — 3.11+ 권장 (일부 코드 호환성 영향 가능)" >&2
fi

# pip 업그레이드 + requirements 설치
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$REQ_FILE"

# 검증: import yaml 가능 여부
if "$VENV_DIR/bin/python3" -c 'import yaml' 2>/dev/null; then
  YAML_VER="$("$VENV_DIR/bin/python3" -c 'import yaml; print(yaml.__version__)')"
  echo "[bootstrap] done. python=$PY_VER pyyaml=$YAML_VER venv=$VENV_DIR"
else
  echo "[bootstrap] FATAL: pyyaml import 실패 — requirements.txt 확인" >&2
  exit 3
fi
