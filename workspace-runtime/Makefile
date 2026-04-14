.PHONY: help test-setup test-run test-teardown test-all test-unit test-integration test-coverage test-local clean-test

# 默認目標
.DEFAULT_GOAL := help

COMPOSE_FILE := docker-compose.test.yml
COMPOSE := docker compose -f $(COMPOSE_FILE)

# 顏色定義
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

##@ General

help: ## 顯示幫助信息
	@echo "$(CYAN)Workspace Runtime Test Makefile$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make $(CYAN)<target>$(NC)\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Test Infrastructure

test-setup: ## 設置測試環境（啟動PostgreSQL和Redis）
	@echo "$(GREEN)🚀 設置測試環境...$(NC)"
	@$(COMPOSE) up -d postgres-test redis-test
	@echo "$(YELLOW)⏳ 等待服務健康檢查...$(NC)"
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if $(COMPOSE) ps | grep -q "healthy"; then \
			echo "$(GREEN)✅ 測試環境就緒$(NC)"; \
			echo "  - PostgreSQL: localhost:5435"; \
			echo "  - Redis: localhost:6382"; \
			exit 0; \
		fi; \
		sleep 3; \
	done; \
	echo "$(RED)❌ 服務啟動超時$(NC)"; \
	exit 1

test-teardown: ## 清理測試環境
	@echo "$(YELLOW)🧹 清理測試環境...$(NC)"
	@$(COMPOSE) down -v --remove-orphans
	@echo "$(GREEN)✅ 清理完成$(NC)"

test-status: ## 檢查測試環境狀態
	@echo "$(CYAN)📊 測試環境狀態:$(NC)"
	@$(COMPOSE) ps

##@ Test Execution

test-all: test-setup ## 執行所有測試（單元+整合）
	@echo "$(GREEN)🧪 執行所有測試...$(NC)"
	@$(COMPOSE) run --rm workspace-runtime-test || ($(MAKE) test-teardown && exit 1)
	@$(MAKE) test-teardown

test-run: ## 執行測試（假設環境已啟動）
	@echo "$(GREEN)🧪 執行所有測試（使用現有環境）...$(NC)"
	@$(COMPOSE) run --rm workspace-runtime-test

test-unit: test-setup ## 僅執行單元測試
	@echo "$(GREEN)🧪 執行單元測試...$(NC)"
	@$(COMPOSE) run --rm workspace-runtime-test \
		sh -c "uv sync --all-extras && uv run pytest tests/unit/ -v --cov=app --cov-report=term-missing" || ($(MAKE) test-teardown && exit 1)
	@$(MAKE) test-teardown

test-integration: test-setup ## 僅執行整合測試
	@echo "$(GREEN)🧪 執行整合測試...$(NC)"
	@$(COMPOSE) run --rm workspace-runtime-test \
		sh -c "uv sync --all-extras && uv run pytest tests/integration/ -v --cov=app --cov-report=term-missing" || ($(MAKE) test-teardown && exit 1)
	@$(MAKE) test-teardown

test-coverage: test-setup ## 生成覆蓋率報告
	@echo "$(GREEN)📊 生成覆蓋率報告...$(NC)"
	@$(COMPOSE) run --rm workspace-runtime-test \
		sh -c "uv sync --all-extras && uv run pytest tests/ --cov=app --cov-report=html --cov-report=term-missing --cov-report=json:test-results/coverage.json" || ($(MAKE) test-teardown && exit 1)
	@echo "$(GREEN)📁 覆蓋率報告生成於: htmlcov/index.html$(NC)"
	@echo "$(CYAN)💡 使用 'make open-coverage' 打開報告$(NC)"
	@$(MAKE) test-teardown

test-watch: test-setup ## 監視模式運行測試（文件變更時自動重新運行）
	@echo "$(GREEN)👀 進入測試監視模式...$(NC)"
	@echo "$(YELLOW)⚠️  按 Ctrl+C 退出$(NC)"
	@$(COMPOSE) run --rm workspace-runtime-test \
		sh -c "uv sync --all-extras && uv run pytest-watch tests/ -- -v" || ($(MAKE) test-teardown && exit 1)

test-specific: test-setup ## 執行特定測試文件（使用 TEST_FILE=path/to/test.py）
ifndef TEST_FILE
	@echo "$(RED)❌ 請指定測試文件: make test-specific TEST_FILE=tests/unit/test_example.py$(NC)"
	@$(MAKE) test-teardown
	@exit 1
endif
	@echo "$(GREEN)🧪 執行測試: $(TEST_FILE)$(NC)"
	@$(COMPOSE) run --rm workspace-runtime-test \
		sh -c "uv sync --all-extras && uv run pytest $(TEST_FILE) -v --cov=app --cov-report=term-missing" || ($(MAKE) test-teardown && exit 1)
	@$(MAKE) test-teardown

##@ Local Testing

test-local: ## 在本地執行測試（假設環境已設置）
	@echo "$(GREEN)🏃 執行本地測試...$(NC)"
	@echo "$(YELLOW)⚠️  確保PostgreSQL (5435) 和 Redis (6382) 正在運行$(NC)"
	@uv run pytest tests/ -v --cov=app --cov-report=term-missing

test-local-unit: ## 在本地執行單元測試
	@echo "$(GREEN)🏃 執行本地單元測試...$(NC)"
	@uv run pytest tests/unit/ -v --cov=app --cov-report=term-missing

test-local-integration: ## 在本地執行整合測試
	@echo "$(GREEN)🏃 執行本地整合測試...$(NC)"
	@echo "$(YELLOW)⚠️  確保PostgreSQL (5435) 和 Redis (6382) 正在運行$(NC)"
	@uv run pytest tests/integration/ -v --cov=app --cov-report=term-missing

##@ Reports & Analysis

open-coverage: ## 打開覆蓋率報告（macOS）
	@if [ -f "htmlcov/index.html" ]; then \
		echo "$(GREEN)📖 打開覆蓋率報告...$(NC)"; \
		open htmlcov/index.html; \
	else \
		echo "$(RED)❌ 覆蓋率報告不存在。請先運行 'make test-coverage'$(NC)"; \
	fi

coverage-summary: ## 顯示覆蓋率摘要
	@if [ -f "test-results/coverage.json" ]; then \
		echo "$(CYAN)📊 覆蓋率摘要:$(NC)"; \
		python3 -c "import json; data=json.load(open('test-results/coverage.json')); print(f\"總覆蓋率: {data['totals']['percent_covered']:.2f}%\")"; \
	else \
		echo "$(RED)❌ 覆蓋率數據不存在。請先運行 'make test-coverage'$(NC)"; \
	fi

##@ Cleanup

clean-test: ## 清理測試生成的文件
	@echo "$(YELLOW)🧹 清理測試文件...$(NC)"
	@rm -rf htmlcov/
	@rm -rf test-results/
	@rm -rf .pytest_cache/
	@rm -rf .coverage
	@rm -rf coverage.xml
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "$(GREEN)✅ 清理完成$(NC)"

clean-all: clean-test test-teardown ## 清理所有（測試文件+Docker容器）
	@echo "$(GREEN)✅ 所有清理完成$(NC)"

##@ Development

install-test-deps: ## 安裝測試依賴
	@echo "$(GREEN)📦 安裝測試依賴...$(NC)"
	@uv sync --all-extras
	@echo "$(GREEN)✅ 依賴安裝完成$(NC)"

lint: ## 執行代碼檢查
	@echo "$(CYAN)🔍 執行代碼檢查...$(NC)"
	@uv run ruff check app/ tests/
	@uv run black --check app/ tests/
	@uv run mypy app/

format: ## 格式化代碼
	@echo "$(CYAN)✨ 格式化代碼...$(NC)"
	@uv run black app/ tests/
	@uv run isort app/ tests/
	@echo "$(GREEN)✅ 格式化完成$(NC)"

##@ CI/CD

ci-test: ## CI環境測試（假設服務已啟動）
	@echo "$(GREEN)🤖 執行CI測試...$(NC)"
	@uv run pytest tests/ \
		--cov=app \
		--cov-report=xml \
		--cov-report=term-missing \
		--junit-xml=test-results/junit.xml \
		-v \
		--maxfail=5

ci-setup: ## CI環境設置
	@echo "$(GREEN)🤖 設置CI環境...$(NC)"
	@uv sync --all-extras

##@ Quick Commands

quick-test: ## 快速測試（僅運行失敗的測試）
	@echo "$(GREEN)⚡ 快速測試...$(NC)"
	@uv run pytest tests/ --lf -v

quick-changed: ## 測試變更的文件
	@echo "$(GREEN)⚡ 測試變更的文件...$(NC)"
	@uv run pytest tests/ --picked -v
