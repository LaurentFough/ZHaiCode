#= All writable runtime/cache/build paths are project-local; there is no destructive clean target.
PYTHON ?= python3
VENV ?= .venv
export PIP_CACHE_DIR := $(CURDIR)/.runtime/pip-cache
export UV_CACHE_DIR := $(CURDIR)/.runtime/uv-cache
export TMPDIR := $(CURDIR)/.runtime/tmp

.PHONY: venv install check test integration build release schemas
.PHONY: checkpoint-check checkpoint-help
venv:
	mkdir -p .runtime/tmp
	$(PYTHON) -m venv $(VENV)
install: venv
	$(VENV)/bin/python -m pip install -e '.[dev]'
schemas:
	$(VENV)/bin/python scripts/generate_protocols.py
check:
	$(VENV)/bin/ruff check src tests scripts
	$(VENV)/bin/pytest -m 'not postgres'
test: check
integration:
	@test -n "$$ZHAICODE_TEST_DSN" || (echo 'Set ZHAICODE_TEST_DSN to a dedicated test database'; exit 1)
	$(VENV)/bin/pytest -m postgres
build:
	$(VENV)/bin/python -m build --no-isolation
release: check integration build
	@echo 'Artifacts are in dist/. Review and tag explicitly; no push or merge performed.'
checkpoint-check:
	$(VENV)/bin/pytest tests/test_git_checkpoints.py -m 'not postgres'
checkpoint-help:
	$(VENV)/bin/agentctl checkpoint --help
