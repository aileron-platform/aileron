.PHONY: help test test-unit test-coverage test-watch test-ui test-local clean-test

.DEFAULT_GOAL := help

CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m

help: ## 顯示幫助信息
	@echo "$(CYAN)Frontend - 測試命令$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(CYAN)%-20s$(NC) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

##@ Container 測試

test: ## 執行所有測試 (Container內)
	@echo "$(GREEN)🧪 執行前端測試 (Container)...$(NC)"
	@docker-compose -f docker-compose.test.yml build frontend-test
	@docker-compose -f docker-compose.test.yml run --rm frontend-test

test-unit: ## 執行單元測試 (Container內)
	@echo "$(GREEN)🧪 執行單元測試 (Container)...$(NC)"
	@docker-compose -f docker-compose.test.yml build frontend-test
	@docker-compose -f docker-compose.test.yml run --rm frontend-test

test-coverage: ## 生成覆蓋率報告 (Container內)
	@echo "$(GREEN)📊 生成覆蓋率報告 (Container)...$(NC)"
	@docker-compose -f docker-compose.test.yml build frontend-test
	@docker-compose -f docker-compose.test.yml run --rm frontend-test sh -c "npm run test:coverage"
	@echo "$(GREEN)📁 報告位置: coverage/index.html$(NC)"

##@ 本地測試

test-local: ## 在本地執行測試
	@echo "$(GREEN)🏃 執行本地測試...$(NC)"
	@npm run test:run

test-watch: ## 監視模式 (本地)
	@echo "$(GREEN)👀 進入測試監視模式...$(NC)"
	@npm run test

test-ui: ## 打開測試 UI (本地)
	@echo "$(GREEN)🎨 打開測試 UI...$(NC)"
	@npm run test:ui

##@ 清理

clean-test: ## 清理測試文件
	@echo "$(YELLOW)🧹 清理測試文件...$(NC)"
	@rm -rf coverage/ .vitest/
	@echo "$(GREEN)✅ 清理完成$(NC)"
