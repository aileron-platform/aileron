.PHONY: help test-setup test-teardown test-all test-unit test-integration test-coverage test-local clean-test test-workspaces lint-workspaces verify-workspaces

.DEFAULT_GOAL := help

CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

help: ## 顯示幫助信息
	@echo "$(CYAN)Workspace Manager - 測試命令$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

##@ 測試環境

test-setup: ## 啟動測試環境
	@echo "$(GREEN)🚀 啟動測試環境...$(NC)"
	@docker-compose -f docker-compose.test.yml up -d
	@echo "$(YELLOW)⏳ 等待服務健康檢查...$(NC)"
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if docker-compose -f docker-compose.test.yml ps | grep -q "healthy"; then \
			echo "$(GREEN)✅ 測試環境就緒$(NC)"; \
			exit 0; \
		fi; \
		sleep 3; \
	done; \
	echo "$(RED)❌ 服務啟動超時$(NC)"; \
	exit 1

test-teardown: ## 清理測試環境
	@echo "$(YELLOW)🧹 清理測試環境...$(NC)"
	@docker-compose -f docker-compose.test.yml down -v
	@echo "$(GREEN)✅ 清理完成$(NC)"

test-status: ## 檢查測試環境狀態
	@docker-compose -f docker-compose.test.yml ps

##@ 執行測試

test-all: test-setup ## 執行所有測試 (Container內)
	@echo "$(GREEN)🧪 執行所有測試...$(NC)"
	@docker-compose -f docker-compose.test.yml run --rm workspace-manager-test
	@$(MAKE) test-teardown

test-run: ## 執行測試（假設環境已啟動）
	@echo "$(GREEN)🧪 執行所有測試（使用現有環境）...$(NC)"
	@docker-compose -f docker-compose.test.yml run --rm workspace-manager-test

test-workspaces: test-setup ## 在容器內執行 workspace / workspace_setup 測試
	@echo "$(GREEN)🧪 執行 workspace 領域測試...$(NC)"
	@docker-compose -f docker-compose.test.yml run --rm workspace-manager-test \
		sh -lc "uv sync --dev && uv run pytest tests/unit/services/workspaces/test_workspace_service.py tests/unit/services/workspaces/test_workspace_setup_service.py tests/unit/services/workspaces/test_workspace_lifecycle_service.py tests/integration/workspaces/test_workspaces_api.py tests/integration/workspace_setup/test_workspace_setup_api.py tests/integration/test_workspaces_api_basic.py -q"
	@$(MAKE) test-teardown

lint-workspaces: test-setup ## 在容器內執行 workspace 相關 lint/型別檢查
	@echo "$(GREEN)🔍 執行 workspace 領域 lint 與型別檢查...$(NC)"
	@docker-compose -f docker-compose.test.yml run --rm workspace-manager-test \
		sh -lc "uv sync --dev && uv run flake8 --extend-ignore=E501,E402,W293 app/routers/workspaces.py app/routers/workspace_setup.py tests/conftest.py tests/unit/services/workspaces/test_workspace_service.py tests/unit/services/workspaces/test_workspace_lifecycle_service.py tests/unit/services/workspaces/test_workspace_setup_service.py tests/integration/workspaces/test_workspaces_api.py tests/integration/workspace_setup/test_workspace_setup_api.py tests/integration/test_workspaces_api_basic.py && python -m py_compile app/routers/workspaces.py app/routers/workspace_setup.py app/services/workspace_service.py app/services/workspace_lifecycle_service.py app/services/workspace_setup_service.py tests/conftest.py tests/unit/services/workspaces/test_workspace_service.py tests/unit/services/workspaces/test_workspace_lifecycle_service.py tests/unit/services/workspaces/test_workspace_setup_service.py tests/integration/workspaces/test_workspaces_api.py tests/integration/workspace_setup/test_workspace_setup_api.py tests/integration/test_workspaces_api_basic.py"
	@$(MAKE) test-teardown

verify-workspaces: ## 在容器內依序執行 workspace 測試與 lint/型別檢查
	@$(MAKE) test-workspaces
	@$(MAKE) lint-workspaces

test-unit: test-setup ## 執行單元測試
	@echo "$(GREEN)🧪 執行單元測試...$(NC)"
	@docker-compose -f docker-compose.test.yml run --rm workspace-manager-test \
		uv run pytest tests/unit/ -v --cov=app --cov-report=term-missing
	@$(MAKE) test-teardown

test-integration: test-setup ## 執行整合測試
	@echo "$(GREEN)🧪 執行整合測試...$(NC)"
	@docker-compose -f docker-compose.test.yml run --rm workspace-manager-test \
		uv run pytest tests/integration/ -v --cov=app --cov-report=term-missing
	@$(MAKE) test-teardown

test-coverage: test-setup ## 生成覆蓋率報告
	@echo "$(GREEN)📊 生成覆蓋率報告...$(NC)"
	@docker-compose -f docker-compose.test.yml run --rm workspace-manager-test \
		uv run pytest tests/ --cov=app --cov-report=html --cov-report=term-missing
	@echo "$(GREEN)📁 報告位置: htmlcov/index.html$(NC)"
	@$(MAKE) test-teardown

##@ 本地測試

test-local: ## 在本地執行測試 (需要本地環境)
	@echo "$(GREEN)🏃 執行本地測試...$(NC)"
	@uv run pytest tests/ -v --cov=app --cov-report=term-missing

test-local-unit: ## 本地執行單元測試
	@uv run pytest tests/unit/ -v

test-local-integration: ## 本地執行整合測試
	@uv run pytest tests/integration/ -v

##@ 清理

clean-test: ## 清理測試文件
	@echo "$(YELLOW)🧹 清理測試文件...$(NC)"
	@rm -rf htmlcov/ .pytest_cache/ .coverage coverage.xml
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)✅ 清理完成$(NC)"
