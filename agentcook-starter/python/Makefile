PYTHON ?= python3
VENV   := .venv
BIN    := $(VENV)/bin
PORT   ?= 8000

.PHONY: help setup dev test lint format seed docker clean

help:  ## Show the available commands
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-8s %s\n", $$1, $$2}'

setup:  ## Create .venv, install dependencies, create .env
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -q --upgrade pip
	$(BIN)/pip install -q -r requirements-dev.txt
	@test -f .env || (cp .env.example .env && echo "created .env (mock mode on)")

dev:  ## Run the server with auto-reload on http://localhost:$(PORT)
	$(BIN)/uvicorn app.main:app --reload --host 127.0.0.1 --port $(PORT)

test:  ## Run the tests
	$(BIN)/python -m pytest

lint:  ## Check style and common bugs
	$(BIN)/ruff check .
	$(BIN)/ruff format --check .

format:  ## Auto-format the code
	$(BIN)/ruff check --fix .
	$(BIN)/ruff format .

seed:  ## Create data/sales.db for the chapter 24 sales_query solution
	$(BIN)/python -m solutions.ch24.seed_sales_db

docker:  ## Build the production image
	docker build -t agentcook-starter .

clean:  ## Remove caches and the virtualenv
	rm -rf $(VENV) .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
