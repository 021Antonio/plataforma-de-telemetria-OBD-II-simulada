PYTHON ?= python

.PHONY: test cov lint run

test:
	$(PYTHON) -m pytest -q --tb=short

cov:
	$(PYTHON) -m pytest -q --tb=short --cov=obd --cov-report=term-missing

lint:
	$(PYTHON) -m ruff check src tests
	$(PYTHON) -m ruff format --check src tests
	$(PYTHON) -m mypy

run:
	$(PYTHON) -m obd run
