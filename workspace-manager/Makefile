.PHONY: \
	help \
	test-setup test-teardown test-status \
	test-all test-run test-unit test-integration test-coverage \
	clean-test test-workspaces lint-workspaces verify-workspaces

.DEFAULT_GOAL := help

CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

help: ## Show help
	@echo "$(CYAN)Workspace Manager - test commands$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

##@ Test environment

test-setup: ## Start test environment
	@echo "$(GREEN)🚀 Starting test environment...$(NC)"
	@docker compose -f docker-compose.test.yml up -d postgres-test redis-test
	@echo "$(YELLOW)⏳ Waiting for service health checks...$(NC)"
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if docker compose -f docker-compose.test.yml exec -T postgres-test \
				pg_isready -U test_user -d test_workspace_manager >/dev/null 2>&1 && \
			[ "$$(docker compose -f docker-compose.test.yml exec -T redis-test \
				redis-cli ping 2>/dev/null | tr -d '\r\n')" = "PONG" ]; then \
			echo "$(GREEN)✅ Test environment is ready$(NC)"; \
			exit 0; \
		fi; \
		sleep 3; \
	done; \
	echo "$(RED)❌ Service startup timed out$(NC)"; \
	exit 1

test-teardown: ## Clean up test environment
	@echo "$(YELLOW)🧹 Cleaning up test environment...$(NC)"
	@docker compose -f docker-compose.test.yml down -v
	@echo "$(GREEN)✅ Cleanup complete$(NC)"

test-status: ## Check test environment status
	@docker compose -f docker-compose.test.yml ps

##@ Run tests

test-all: test-setup ## Run all tests in the container
	@echo "$(GREEN)🧪 Running all tests...$(NC)"
	@docker compose -f docker-compose.test.yml run --rm workspace-manager-test
	@$(MAKE) test-teardown

test-run: ## Run tests using an already-started environment
	@echo "$(GREEN)🧪 Running all tests with the existing environment...$(NC)"
	@docker compose -f docker-compose.test.yml run --rm workspace-manager-test

test-workspaces: test-setup ## Run workspace / workspace_setup tests in the container
	@echo "$(GREEN)🧪 Running workspace domain tests...$(NC)"
	@docker compose -f docker-compose.test.yml run --rm workspace-manager-test \
		sh -lc "uv sync --dev && uv run pytest tests/unit/modules/workspace/test_workspace_service.py tests/unit/modules/workspace/test_workspace_setup_service.py tests/unit/modules/workspace/test_workspace_lifecycle_service.py tests/integration/modules/workspace/test_workspaces_api.py tests/integration/modules/workspace/test_workspace_setup_api.py -q"
	@$(MAKE) test-teardown

lint-workspaces: test-setup ## Run workspace-related lint and type checks in the container
	@echo "$(GREEN)🔍 Running workspace domain lint and type checks...$(NC)"
	@docker compose -f docker-compose.test.yml run --rm workspace-manager-test \
		sh -lc "uv sync --dev && uv run flake8 --extend-ignore=E501,E402,W293 app/modules/workspace/router.py app/modules/workspace/setup_router.py tests/conftest.py tests/unit/modules/workspace/test_workspace_service.py tests/unit/modules/workspace/test_workspace_lifecycle_service.py tests/unit/modules/workspace/test_workspace_setup_service.py tests/integration/modules/workspace/test_workspaces_api.py tests/integration/modules/workspace/test_workspace_setup_api.py && python -m py_compile app/modules/workspace/router.py app/modules/workspace/setup_router.py app/modules/workspace/catalog.py app/modules/workspace/lifecycle.py app/modules/workspace/setup.py tests/conftest.py tests/unit/modules/workspace/test_workspace_service.py tests/unit/modules/workspace/test_workspace_lifecycle_service.py tests/unit/modules/workspace/test_workspace_setup_service.py tests/integration/modules/workspace/test_workspaces_api.py tests/integration/modules/workspace/test_workspace_setup_api.py"
	@$(MAKE) test-teardown

verify-workspaces: ## Run workspace tests and lint/type checks in sequence in the container
	@$(MAKE) test-workspaces
	@$(MAKE) lint-workspaces

test-unit: test-setup ## Run unit tests
	@echo "$(GREEN)🧪 Running unit tests...$(NC)"
	@docker compose -f docker-compose.test.yml run --rm workspace-manager-test \
		uv run pytest tests/unit/ -v --cov=app --cov-report=term-missing
	@$(MAKE) test-teardown

test-integration: test-setup ## Run integration tests
	@echo "$(GREEN)🧪 Running integration tests...$(NC)"
	@docker compose -f docker-compose.test.yml run --rm workspace-manager-test \
		uv run pytest tests/integration/ -v --cov=app --cov-report=term-missing
	@$(MAKE) test-teardown

test-coverage: test-setup ## Generate coverage report
	@echo "$(GREEN)📊 Generating coverage report...$(NC)"
	@docker compose -f docker-compose.test.yml run --rm workspace-manager-test \
		uv run pytest tests/ --cov=app --cov-report=html --cov-report=term-missing
	@echo "$(GREEN)📁 Report location: htmlcov/index.html$(NC)"
	@$(MAKE) test-teardown

##@ Cleanup

clean-test: ## Clean test files
	@echo "$(YELLOW)🧹 Cleaning test files...$(NC)"
	@rm -rf htmlcov/ .pytest_cache/ .coverage coverage.xml
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✅ Cleanup complete$(NC)"
