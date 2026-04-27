.PHONY: help test-setup test-run test-teardown test-all test-unit test-integration test-coverage test-local clean-test

# Default target
.DEFAULT_GOAL := help

COMPOSE_FILE := docker-compose.test.yml
COMPOSE := docker compose -f $(COMPOSE_FILE)

# Color definitions
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

##@ General

help: ## Show help
	@echo "$(CYAN)Workspace Runtime Test Makefile$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make $(CYAN)<target>$(NC)\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Test Infrastructure

test-setup: ## Set up test environment (start PostgreSQL and Redis)
	@echo "$(GREEN)🚀 Setting up test environment...$(NC)"
	@$(COMPOSE) up -d postgres-test redis-test
	@echo "$(YELLOW)⏳ Waiting for service health checks...$(NC)"
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if $(COMPOSE) ps | grep -q "healthy"; then \
			echo "$(GREEN)✅ Test environment is ready$(NC)"; \
			echo "  - PostgreSQL: localhost:5435"; \
			echo "  - Redis: localhost:6382"; \
			exit 0; \
		fi; \
		sleep 3; \
	done; \
	echo "$(RED)❌ Timed out while starting services$(NC)"; \
	exit 1

test-teardown: ## Clean up test environment
	@echo "$(YELLOW)🧹 Cleaning up test environment...$(NC)"
	@$(COMPOSE) down -v --remove-orphans
	@echo "$(GREEN)✅ Cleanup complete$(NC)"

test-status: ## Check test environment status
	@echo "$(CYAN)📊 Test environment status:$(NC)"
	@$(COMPOSE) ps

##@ Test Execution

test-all: test-setup ## Run all tests (unit + integration)
	@echo "$(GREEN)🧪 Running all tests...$(NC)"
	@$(COMPOSE) run --rm workspace-runtime-test || ($(MAKE) test-teardown && exit 1)
	@$(MAKE) test-teardown

test-run: ## Run tests with an existing environment
	@echo "$(GREEN)🧪 Running all tests with the existing environment...$(NC)"
	@$(COMPOSE) run --rm workspace-runtime-test

test-unit: test-setup ## Run unit tests only
	@echo "$(GREEN)🧪 Running unit tests...$(NC)"
	@$(COMPOSE) run --rm workspace-runtime-test \
		sh -c "uv sync --all-extras && uv run pytest tests/unit/ -v --cov=app --cov-report=term-missing" || ($(MAKE) test-teardown && exit 1)
	@$(MAKE) test-teardown

test-integration: test-setup ## Run integration tests only
	@echo "$(GREEN)🧪 Running integration tests...$(NC)"
	@$(COMPOSE) run --rm workspace-runtime-test \
		sh -c "uv sync --all-extras && uv run pytest tests/integration/ -v --cov=app --cov-report=term-missing" || ($(MAKE) test-teardown && exit 1)
	@$(MAKE) test-teardown

test-coverage: test-setup ## Generate coverage report
	@echo "$(GREEN)📊 Generating coverage report...$(NC)"
	@$(COMPOSE) run --rm workspace-runtime-test \
		sh -c "uv sync --all-extras && uv run pytest tests/ --cov=app --cov-report=html --cov-report=term-missing --cov-report=json:test-results/coverage.json" || ($(MAKE) test-teardown && exit 1)
	@echo "$(GREEN)📁 Coverage report generated at: htmlcov/index.html$(NC)"
	@echo "$(CYAN)💡 Use 'make open-coverage' to open the report$(NC)"
	@$(MAKE) test-teardown

test-watch: test-setup ## Run tests in watch mode
	@echo "$(GREEN)👀 Entering test watch mode...$(NC)"
	@echo "$(YELLOW)⚠️  Press Ctrl+C to exit$(NC)"
	@$(COMPOSE) run --rm workspace-runtime-test \
		sh -c "uv sync --all-extras && uv run pytest-watch tests/ -- -v" || ($(MAKE) test-teardown && exit 1)

test-specific: test-setup ## Run a specific test file with TEST_FILE=path/to/test.py
ifndef TEST_FILE
	@echo "$(RED)❌ Specify a test file: make test-specific TEST_FILE=tests/unit/test_example.py$(NC)"
	@$(MAKE) test-teardown
	@exit 1
endif
	@echo "$(GREEN)🧪 Running test: $(TEST_FILE)$(NC)"
	@$(COMPOSE) run --rm workspace-runtime-test \
		sh -c "uv sync --all-extras && uv run pytest $(TEST_FILE) -v --cov=app --cov-report=term-missing" || ($(MAKE) test-teardown && exit 1)
	@$(MAKE) test-teardown

##@ Local Testing

test-local: ## Run tests locally with an existing environment
	@echo "$(GREEN)🏃 Running local tests...$(NC)"
	@echo "$(YELLOW)⚠️  Ensure PostgreSQL (5435) and Redis (6382) are running$(NC)"
	@uv run pytest tests/ -v --cov=app --cov-report=term-missing

test-local-unit: ## Run unit tests locally
	@echo "$(GREEN)🏃 Running local unit tests...$(NC)"
	@uv run pytest tests/unit/ -v --cov=app --cov-report=term-missing

test-local-integration: ## Run integration tests locally
	@echo "$(GREEN)🏃 Running local integration tests...$(NC)"
	@echo "$(YELLOW)⚠️  Ensure PostgreSQL (5435) and Redis (6382) are running$(NC)"
	@uv run pytest tests/integration/ -v --cov=app --cov-report=term-missing

##@ Reports & Analysis

open-coverage: ## Open coverage report on macOS
	@if [ -f "htmlcov/index.html" ]; then \
		echo "$(GREEN)📖 Opening coverage report...$(NC)"; \
		open htmlcov/index.html; \
	else \
		echo "$(RED)❌ Coverage report does not exist. Run 'make test-coverage' first$(NC)"; \
	fi

coverage-summary: ## Show coverage summary
	@if [ -f "test-results/coverage.json" ]; then \
		echo "$(CYAN)📊 Coverage summary:$(NC)"; \
		python3 -c "import json; data=json.load(open('test-results/coverage.json')); print(f\"Total coverage: {data['totals']['percent_covered']:.2f}%\")"; \
	else \
		echo "$(RED)❌ Coverage data does not exist. Run 'make test-coverage' first$(NC)"; \
	fi

##@ Cleanup

clean-test: ## Clean test-generated files
	@echo "$(YELLOW)🧹 Cleaning test files...$(NC)"
	@rm -rf htmlcov/
	@rm -rf test-results/
	@rm -rf .pytest_cache/
	@rm -rf .coverage
	@rm -rf coverage.xml
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✅ Cleanup complete$(NC)"

clean-all: clean-test test-teardown ## Clean everything (test files + Docker containers)
	@echo "$(GREEN)✅ Full cleanup complete$(NC)"

##@ Development

install-test-deps: ## Install test dependencies
	@echo "$(GREEN)📦 Installing test dependencies...$(NC)"
	@uv sync --all-extras
	@echo "$(GREEN)✅ Dependencies installed$(NC)"

lint: ## Run code checks
	@echo "$(CYAN)🔍 Running code checks...$(NC)"
	@uv run ruff check app/ tests/
	@uv run black --check app/ tests/
	@uv run mypy app/

format: ## Format code
	@echo "$(CYAN)✨ Formatting code...$(NC)"
	@uv run black app/ tests/
	@uv run isort app/ tests/
	@echo "$(GREEN)✅ Formatting complete$(NC)"

##@ CI/CD

ci-test: ## Run CI tests with services already started
	@echo "$(GREEN)🤖 Running CI tests...$(NC)"
	@uv run pytest tests/ \
		--cov=app \
		--cov-report=xml \
		--cov-report=term-missing \
		--junit-xml=test-results/junit.xml \
		-v \
		--maxfail=5

ci-setup: ## Set up CI environment
	@echo "$(GREEN)🤖 Setting up CI environment...$(NC)"
	@uv sync --all-extras

##@ Quick Commands

quick-test: ## Quick test run for last failures only
	@echo "$(GREEN)⚡ Running quick tests...$(NC)"
	@uv run pytest tests/ --lf -v

quick-changed: ## Test changed files
	@echo "$(GREEN)⚡ Testing changed files...$(NC)"
	@uv run pytest tests/ --picked -v
