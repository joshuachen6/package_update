VENV   := .venv
PYTHON := $(VENV)/bin/python3

.PHONY: install gui quick test coverage lint format clean clean-cache clean-build

install: $(PYTHON)

$(PYTHON): pyproject.toml
	python3 -m venv $(VENV)
	$(PYTHON) -m pip install --quiet --upgrade pip
	$(PYTHON) -m pip install --quiet -e ".[dev]"
	@echo "Installed. Run 'source $(VENV)/bin/activate' or use 'make gui' / 'make quick'."

gui: $(PYTHON)
	$(PYTHON) gui.py

quick: $(PYTHON)
	$(PYTHON) quick_update.py

clean: clean-cache clean-build
	rm -rf $(VENV)

clean-cache:
	rm -rf .pytest_cache
	find . \( -path './.venv' -o -path './.*' \) -prune -o -type d -name '__pycache__' -print -exec rm -rf {} +
	rm -f .coverage coverage.xml

clean-build:
	rm -rf build dist *.egg-info


test: $(PYTHON)
	$(PYTHON) -m pytest

coverage: $(PYTHON)
	$(PYTHON) -m pytest --cov=. --cov-report=term-missing --cov-report=xml

lint: $(PYTHON)
	$(PYTHON) -m ruff check .

format: $(PYTHON)
	$(PYTHON) -m ruff format .
