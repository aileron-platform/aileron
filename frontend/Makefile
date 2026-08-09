.PHONY: help test test-unit test-coverage test-watch test-ui test-local clean-test

.DEFAULT_GOAL := help

CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

help: ## Show help
	@echo "$(CYAN)Frontend - 測試命令$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

##@ Container tests

test: ## Run all tests in the container
	@echo "$(GREEN)🧪 執行前端測試 (Container)...$(NC)"
	@docker compose -f docker-compose.test.yml run --rm frontend-test

test-unit: ## Run unit tests in the container
	@echo "$(GREEN)🧪 執行單元測試 (Container)...$(NC)"
	@docker compose -f docker-compose.test.yml run --rm frontend-test

test-coverage: ## Generate coverage in the container
	@echo "$(GREEN)📊 生成覆蓋率報告 (Container)...$(NC)"
	@docker compose -f docker-compose.test.yml run --rm frontend-test sh -c "npm run test:coverage"
	@echo "$(GREEN)📁 報告位置: coverage/index.html$(NC)"

##@ Local tests

test-local: ## Run tests on the host
	@echo "$(GREEN)🏃 執行本地測試...$(NC)"
	@npm run test:run

test-watch: ## Run host tests in watch mode
	@echo "$(GREEN)👀 進入測試監視模式...$(NC)"
	@npm run test

test-ui: ## Open the host test UI
	@echo "$(GREEN)🎨 打開測試 UI...$(NC)"
	@npm run test:ui

##@ Cleanup

clean-test: ## Remove test artifacts
	@echo "$(YELLOW)🧹 清理測試文件...$(NC)"
	@rm -rf coverage/ .vitest/
	@echo "$(GREEN)✅ 清理完成$(NC)"
