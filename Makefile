.PHONY: test test-unit test-integration test-arch test-cov lint check install-dev clean telemetry-gc telemetry-gc-apply

PYTHON ?= python3

# ADR-0014: ruff lint enforcement scope (점진 확대). 정책 계약 핵심 모듈 + 신규 생성기/arch test.
RUFF_PATHS ?= domains/policy domains/_shared/policy_profile domains/_shared/profile_registry \
	domains/_shared/segment_registry applications/gen_methods_manifest.py tests/architecture

install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

test-unit:
	$(PYTHON) -m pytest -m unit

test-integration:
	$(PYTHON) -m pytest -m integration

# 아키텍처 fitness functions (D-ARCH 불변식). `make test` 에도 자동 포함 (testpaths=tests/).
test-arch:
	$(PYTHON) -m pytest tests/architecture -ra

# ADR-0014: 결정론적 Python lint (ruff). scope 는 RUFF_PATHS (점진 확대).
lint:
	$(PYTHON) -m ruff check $(RUFF_PATHS)

# 결정론적 게이트 집합 — lint + 전체 테스트(arch 포함). CI / pre-merge 단일 진입점.
check: lint test

test-cov:
	$(PYTHON) -m pytest --cov=domains --cov=infrastructure/_common --cov-report=term-missing

clean:
	rm -rf .pytest_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

# telemetry retention GC — registry(SSoT) 기반 stale/legacy/충돌본 정리.
# telemetry-gc       : dry-run (변경 없음, 계획만 출력).
# telemetry-gc-apply : 실제 삭제/정규화 수행 (PERMANENT/STATE/BINARY 증거 불변).
telemetry-gc:
	$(PYTHON) -m applications.telemetry_gc

telemetry-gc-apply:
	$(PYTHON) -m applications.telemetry_gc --apply
