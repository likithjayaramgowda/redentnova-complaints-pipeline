SHELL := /bin/sh

VENV := .venv
RUN_ARGS ?= backup --sp-upload --sp-upload-log

ifeq ($(OS),Windows_NT)
	VENV_BIN := $(VENV)/Scripts
	PY := $(VENV_BIN)/python.exe
	PIP := $(VENV_BIN)/pip.exe
else
	VENV_BIN := $(VENV)/bin
	PY := $(VENV_BIN)/python
	PIP := $(VENV_BIN)/pip
endif

.PHONY: help venv install test run lint format clean run-dispatch

help:
	@echo "Targets:"
	@echo "  make install                      - create venv, install deps, install package (editable)"
	@echo "  make test                         - run pytest"
	@echo "  make lint                         - ruff check"
	@echo "  make format                       - ruff format"
	@echo "  make run                          - run default (backup -> SharePoint)"
	@echo "  make run RUN_ARGS='...'           - run with custom args"
	@echo "  make run-dispatch                 - run dispatch processing using sample_event.json"
	@echo "  make clean                        - remove venv and caches"

venv:
	python -m venv $(VENV)

install: venv
	$(PIP) install -U pip
	$(PIP) install -r requirements.txt -r requirements-dev.txt
	$(PIP) install -e .

test:
	$(PY) -m pytest -q

run:
	$(PY) -m complaints_pipeline $(RUN_ARGS)

run-dispatch:
	$(PY) -m complaints_pipeline dispatch --event-path sample_event.json --sp-upload --email

lint:
	$(PY) -m ruff check .

format:
	$(PY) -m ruff format .

clean:
	$(PY) - <<'PY'
import shutil, pathlib
for p in [".venv", ".pytest_cache", ".ruff_cache"]:
    shutil.rmtree(p, ignore_errors=True)
for d in pathlib.Path(".").rglob("__pycache__"):
    shutil.rmtree(d, ignore_errors=True)
PY
