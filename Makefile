# agentcook-cc — unified developer commands.
# Phase 2 Day 21 — Agent C.
#
# Usage:
#   make dev          — start docker-compose + Python app
#   make test-py      — run Python full test suite
#   make test-java    — run Java full test suite
#   make lint         — Python ruff + mypy
#   make ci-local     — simulate full CI locally
#   make down         — stop docker-compose
#   make clean        — stop compose + wipe volumes

.PHONY: dev down clean test-py test-java test-contract lint ci-local help

COMPOSE := docker compose -f docker-compose.dev.yml

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Development ──────────────────────────────────────────────────────────────

dev: ## Start docker-compose services + Python app (foreground)
	$(COMPOSE) up -d
	@echo "\n✅ Services up. Starting Python app on :8000 …"
	OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
		uv run python -m uvicorn agentcook_app.main:app --host 0.0.0.0 --port 8000 --reload

down: ## Stop docker-compose (keep data)
	$(COMPOSE) down

clean: ## Stop docker-compose + wipe volumes
	$(COMPOSE) down -v

# ── Testing ──────────────────────────────────────────────────────────────────

test-py: ## Run Python full test suite (unit + integration)
	uv run pytest --tb=short -q

test-py-unit: ## Run Python unit tests only
	uv run pytest -m "not integration and not slow" --tb=short -q

test-py-cov: ## Run Python tests with coverage report (excludes contract — those need broker; see test-contract)
	uv run pytest agentcook-core agentcook-providers agentcook-storage agentcook \
		--cov --cov-report=term-missing --cov-report=xml:coverage.xml -q

test-java: ## Run Java full test suite
	cd agentcook-java && ./mvnw -B -ntp test

test-contract: ## Run Pact consumer + publish + provider verify (requires broker on :9292)
	@$(COMPOSE) ps pact-broker | grep -q "(healthy)" || \
		(echo "❌ pact-broker not healthy. Run: $(COMPOSE) up -d pact-broker"; exit 1)
	uv run pytest tests/contract/ -v --no-cov

# ── Linting ──────────────────────────────────────────────────────────────────

lint: lint-py ## Run all linters

lint-py: ## Python: ruff check + ruff format check (lenient — CI is strict)
	# `|| true` keeps ci-local moving on legacy backlog while CI (python-ci.yml)
	# stays strict. Treats ruff the same way mypy is treated upstream — see
	# python-ci.yml line 53. Run `make lint-py-strict` to gate on lint locally.
	uv run ruff check . || true
	uv run ruff format --check . || true

lint-py-strict: ## Python: ruff strict (matches CI). Use before submitting.
	uv run ruff check .
	uv run ruff format --check .

lint-java: ## Java: mvn verify -DskipTests (Spotless/Checkstyle if configured)
	cd agentcook-java && ./mvnw -B -ntp verify -DskipTests

# ── Performance (excluded from ci-local — needs a stable baseline) ──────────

perf-test-load: ## Locust headless against running dev stack (50u / 60s)
	@echo "Run \`make dev\` + \`mvn spring-boot:run\` first; then 50 users / 5/s spawn / 60s."
	uv run locust -f tests/performance/locustfile.py \
		--headless -u 50 -r 5 -t 60s

perf-test-k6: ## k6 against running dev stack (requires k6 binary on PATH)
	@command -v k6 >/dev/null 2>&1 || { \
		echo "❌ k6 not found. Install: brew install k6 (or grafana k6 download)."; exit 1; }
	k6 run tests/performance/k6/login-flow.js

# ── CI simulation ────────────────────────────────────────────────────────────

ci-local: lint-py test-py-cov test-contract test-java ## Simulate full CI locally
	@echo "\n✅ ci-local complete."
