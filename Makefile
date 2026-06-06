.PHONY: test test-unit test-integration test-arch test-cov install-dev clean

PYTHON ?= python3

install-dev:
	$(PYTHON) -m pip install -r infrastructure/requirements.txt

test:
	$(PYTHON) -m pytest

test-unit:
	$(PYTHON) -m pytest -m unit

test-integration:
	$(PYTHON) -m pytest -m integration

# 아키텍처 fitness functions (D-ARCH 불변식). `make test` 에도 자동 포함 (testpaths=tests/).
test-arch:
	$(PYTHON) -m pytest tests/architecture -ra

test-cov:
	$(PYTHON) -m pytest --cov=domains --cov=infrastructure/_common --cov-report=term-missing

clean:
	rm -rf .pytest_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
