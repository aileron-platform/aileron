.PHONY: help test-all test-unit test-integration test-frontend test-backend \
        test-runtime test-manager test-coverage test-setup test-teardown \
        test-status clean-test sync-init-schema \
        build-codex-universal push-codex-universal rebuild-codex-universal \
        build-runtime-base-lite push-runtime-base-lite rebuild-runtime-base-lite \
        build-runtime-base rebuild-runtime-base \
        build-workspace-ui push-workspace-ui rebuild-workspace-ui \
        build-workspace-chrome push-workspace-chrome rebuild-workspace-chrome \
        build-workspace-manager push-workspace-manager rebuild-workspace-manager \
        build-workspace-runtime push-workspace-runtime rebuild-workspace-runtime \
        build-workspace-nextjs push-workspace-nextjs rebuild-workspace-nextjs \
        build-workspace-operator push-workspace-operator rebuild-workspace-operator \
        rebuild-platform-images

.DEFAULT_GOAL := help

# 顏色定義
CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

# Image build / push 預設設定
REGISTRY ?= docker.io
NAMESPACE ?= ailerondocker
IMAGE_TAG ?= latest
CODEX_UNIVERSAL_TAG ?= custom
RUNTIME_BASE_LITE_TAG ?= custom
RUNTIME_BASE ?= universal
CODEX_UNIVERSAL_IMAGE ?= $(REGISTRY)/$(NAMESPACE)/codex-universal:$(CODEX_UNIVERSAL_TAG)
RUNTIME_BASE_LITE_IMAGE ?= $(REGISTRY)/$(NAMESPACE)/workspace-runtime-base-lite:$(RUNTIME_BASE_LITE_TAG)
WORKSPACE_UI_IMAGE ?= $(REGISTRY)/$(NAMESPACE)/workspace-ui:$(IMAGE_TAG)
WORKSPACE_CHROME_IMAGE ?= $(REGISTRY)/$(NAMESPACE)/workspace-chrome:$(IMAGE_TAG)
WORKSPACE_MANAGER_IMAGE ?= $(REGISTRY)/$(NAMESPACE)/workspace-manager:$(IMAGE_TAG)
WORKSPACE_RUNTIME_IMAGE ?= $(REGISTRY)/$(NAMESPACE)/workspace-runtime:$(IMAGE_TAG)
WORKSPACE_NEXTJS_IMAGE ?= $(REGISTRY)/$(NAMESPACE)/workspace-nextjs:$(IMAGE_TAG)
WORKSPACE_OPERATOR_IMAGE ?= $(REGISTRY)/$(NAMESPACE)/workspace-operator:$(IMAGE_TAG)

ifeq ($(RUNTIME_BASE),lite)
WORKSPACE_RUNTIME_BASE_IMAGE ?= $(RUNTIME_BASE_LITE_IMAGE)
else
WORKSPACE_RUNTIME_BASE_IMAGE ?= $(CODEX_UNIVERSAL_IMAGE)
endif

help: ## 顯示幫助信息
	@echo "$(CYAN)╔══════════════════════════════════════════════╗$(NC)"
	@echo "$(CYAN)║   Aileron - 統一測試執行系統        ║$(NC)"
	@echo "$(CYAN)╚══════════════════════════════════════════════╝$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(CYAN)%-25s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ 測試環境管理

test-setup: ## 🚀 啟動測試環境 (PostgreSQL + Redis)
	@echo "$(GREEN)🚀 啟動測試環境...$(NC)"
	@docker-compose -f docker-compose.test.yml up -d postgres-test redis-test
	@echo "$(YELLOW)⏳ 等待服務健康檢查...$(NC)"
	@for i in 1 2 3 4 5 6 7 8 9 10; do \
		if docker-compose -f docker-compose.test.yml ps | grep -q "healthy"; then \
			echo "$(GREEN)✅ 測試環境就緒$(NC)"; \
			echo "  - PostgreSQL: localhost:5433"; \
			echo "  - Redis: localhost:6380"; \
			exit 0; \
		fi; \
		sleep 3; \
	done; \
	echo "$(RED)❌ 服務啟動超時$(NC)"; \
	exit 1

test-teardown: ## 🧹 清理測試環境
	@echo "$(YELLOW)🧹 清理測試環境...$(NC)"
	@docker-compose -f docker-compose.test.yml down -v --remove-orphans
	@echo "$(GREEN)✅ 清理完成$(NC)"

test-status: ## 📊 檢查測試環境狀態
	@echo "$(CYAN)📊 測試環境狀態:$(NC)"
	@docker-compose -f docker-compose.test.yml ps

##@ 執行所有測試

test-all: test-setup ## 🧪 執行所有項目的所有測試 (Container內)
	@echo "$(GREEN)╔════════════════════════════════════════╗$(NC)"
	@echo "$(GREEN)║     執行所有項目測試 (Container)       ║$(NC)"
	@echo "$(GREEN)╚════════════════════════════════════════╝$(NC)"
	@status=0; \
	$(MAKE) _test-runtime || status=$$?; \
	$(MAKE) _test-manager || status=$$?; \
	$(MAKE) _test-frontend || status=$$?; \
	$(MAKE) test-teardown; \
	if [ $$status -eq 0 ]; then echo "$(GREEN)✅ 所有測試完成$(NC)"; fi; \
	exit $$status

##@ 按測試類型執行

test-unit: test-setup ## 🧪 執行所有單元測試
	@echo "$(GREEN)🧪 執行所有單元測試...$(NC)"
	@cd workspace-runtime && $(MAKE) test-unit || true
	@cd workspace-manager && $(MAKE) test-unit || true
	@cd frontend && $(MAKE) test-unit || true
	@$(MAKE) test-teardown

test-integration: test-setup ## 🧪 執行所有整合測試
	@echo "$(GREEN)🧪 執行所有整合測試...$(NC)"
	@cd workspace-runtime && $(MAKE) test-integration || true
	@cd workspace-manager && $(MAKE) test-integration || true
	@$(MAKE) test-teardown

##@ 按項目執行

test-runtime: test-setup ## 🧪 執行 workspace-runtime 測試
	@cd workspace-runtime && $(MAKE) test-all
	@$(MAKE) test-teardown

test-manager: test-setup ## 🧪 執行 workspace-manager 測試
	@cd workspace-manager && $(MAKE) test-all
	@$(MAKE) test-teardown

test-frontend: ## 🧪 執行前端測試
	@cd frontend && $(MAKE) test

test-backend: test-setup ## 🧪 執行後端測試 (runtime + manager)
	@echo "$(GREEN)🧪 執行後端測試...$(NC)"
	@cd workspace-runtime && $(MAKE) test-all || true
	@cd workspace-manager && $(MAKE) test-all || true
	@$(MAKE) test-teardown

##@ 覆蓋率報告

test-coverage: test-setup ## 📊 生成所有項目的覆蓋率報告
	@echo "$(GREEN)📊 生成覆蓋率報告...$(NC)"
	@cd workspace-runtime && $(MAKE) test-coverage || true
	@cd workspace-manager && $(MAKE) test-coverage || true
	@cd frontend && $(MAKE) test-coverage || true
	@$(MAKE) test-teardown
	@echo "$(GREEN)📁 查看報告:$(NC)"
	@echo "  Runtime:  $(CYAN)workspace-runtime/htmlcov/index.html$(NC)"
	@echo "  Manager:  $(CYAN)workspace-manager/htmlcov/index.html$(NC)"
	@echo "  Frontend: $(CYAN)frontend/coverage/index.html$(NC)"

##@ 清理

clean-test: ## 🧹 清理所有測試文件
	@echo "$(YELLOW)🧹 清理測試文件...$(NC)"
	@cd workspace-runtime && $(MAKE) clean-test 2>/dev/null || true
	@cd workspace-manager && $(MAKE) clean-test 2>/dev/null || true
	@cd frontend && $(MAKE) clean-test 2>/dev/null || true
	@echo "$(GREEN)✅ 清理完成$(NC)"

##@ 開發輔助

sync-init-schema: ## 🔁 同步共用 init schema 到 Helm chart 內嵌副本
	@./scripts/db/sync-init-schema-to-helm.sh

##@ Image 建置

build-codex-universal: ## 🏗️ 建置 codex-universal image
	@echo "$(GREEN)🏗️ 建置 codex-universal image...$(NC)"
	@echo "  Image: $(CYAN)$(CODEX_UNIVERSAL_IMAGE)$(NC)"
	@docker build -t $(CODEX_UNIVERSAL_IMAGE) -f workspace-runtime/codex-universal/Dockerfile workspace-runtime/codex-universal
	@echo "$(GREEN)✅ codex-universal 建置完成$(NC)"

push-codex-universal: ## 📤 推送 codex-universal image
	@echo "$(GREEN)📤 推送 codex-universal image...$(NC)"
	@echo "  Image: $(CYAN)$(CODEX_UNIVERSAL_IMAGE)$(NC)"
	@docker push $(CODEX_UNIVERSAL_IMAGE)
	@echo "$(GREEN)✅ codex-universal 推送完成$(NC)"

rebuild-codex-universal: build-codex-universal push-codex-universal ## 🔁 重建並推送 codex-universal image
	@echo "$(GREEN)✅ codex-universal rebuild 完成$(NC)"

build-runtime-base-lite: ## 🏗️ 建置 workspace-runtime base-lite image
	@echo "$(GREEN)🏗️ 建置 workspace-runtime base-lite image...$(NC)"
	@echo "  Image: $(CYAN)$(RUNTIME_BASE_LITE_IMAGE)$(NC)"
	@docker build -t $(RUNTIME_BASE_LITE_IMAGE) -f workspace-runtime/base-lite/Dockerfile workspace-runtime/base-lite
	@echo "$(GREEN)✅ workspace-runtime base-lite 建置完成$(NC)"

push-runtime-base-lite: ## 📤 推送 workspace-runtime base-lite image
	@echo "$(GREEN)📤 推送 workspace-runtime base-lite image...$(NC)"
	@echo "  Image: $(CYAN)$(RUNTIME_BASE_LITE_IMAGE)$(NC)"
	@docker push $(RUNTIME_BASE_LITE_IMAGE)
	@echo "$(GREEN)✅ workspace-runtime base-lite 推送完成$(NC)"

rebuild-runtime-base-lite: build-runtime-base-lite push-runtime-base-lite ## 🔁 重建並推送 workspace-runtime base-lite image
	@echo "$(GREEN)✅ workspace-runtime base-lite rebuild 完成$(NC)"

build-runtime-base: ## 🏗️ 依 RUNTIME_BASE 建置 workspace-runtime base image
	@if [ "$(RUNTIME_BASE)" = "lite" ]; then \
		$(MAKE) build-runtime-base-lite; \
	elif [ "$(RUNTIME_BASE)" = "universal" ]; then \
		$(MAKE) build-codex-universal; \
	else \
		echo "$(RED)❌ 不支援的 RUNTIME_BASE: $(RUNTIME_BASE)$(NC)"; \
		exit 1; \
	fi

rebuild-runtime-base: ## 🔁 依 RUNTIME_BASE 重建並推送 workspace-runtime base image
	@if [ "$(RUNTIME_BASE)" = "lite" ]; then \
		$(MAKE) rebuild-runtime-base-lite; \
	elif [ "$(RUNTIME_BASE)" = "universal" ]; then \
		$(MAKE) rebuild-codex-universal; \
	else \
		echo "$(RED)❌ 不支援的 RUNTIME_BASE: $(RUNTIME_BASE)$(NC)"; \
		exit 1; \
	fi

build-workspace-ui: ## 🏗️ 建置 workspace-ui image
	@echo "$(GREEN)🏗️ 建置 workspace-ui image...$(NC)"
	@echo "  Image: $(CYAN)$(WORKSPACE_UI_IMAGE)$(NC)"
	@docker build -t $(WORKSPACE_UI_IMAGE) -f frontend/Dockerfile frontend
	@echo "$(GREEN)✅ workspace-ui 建置完成$(NC)"

push-workspace-ui: ## 📤 推送 workspace-ui image
	@echo "$(GREEN)📤 推送 workspace-ui image...$(NC)"
	@echo "  Image: $(CYAN)$(WORKSPACE_UI_IMAGE)$(NC)"
	@docker push $(WORKSPACE_UI_IMAGE)
	@echo "$(GREEN)✅ workspace-ui 推送完成$(NC)"

rebuild-workspace-ui: build-workspace-ui push-workspace-ui ## 🔁 重建並推送 workspace-ui image
	@echo "$(GREEN)✅ workspace-ui rebuild 完成$(NC)"

build-workspace-chrome: ## 🏗️ 建置 workspace-chrome image
	@echo "$(GREEN)🏗️ 建置 workspace-chrome image...$(NC)"
	@echo "  Image: $(CYAN)$(WORKSPACE_CHROME_IMAGE)$(NC)"
	@docker build -t $(WORKSPACE_CHROME_IMAGE) -f workspace-chrome/Dockerfile.webrtc workspace-chrome
	@echo "$(GREEN)✅ workspace-chrome 建置完成$(NC)"

push-workspace-chrome: ## 📤 推送 workspace-chrome image
	@echo "$(GREEN)📤 推送 workspace-chrome image...$(NC)"
	@echo "  Image: $(CYAN)$(WORKSPACE_CHROME_IMAGE)$(NC)"
	@docker push $(WORKSPACE_CHROME_IMAGE)
	@echo "$(GREEN)✅ workspace-chrome 推送完成$(NC)"

rebuild-workspace-chrome: build-workspace-chrome push-workspace-chrome ## 🔁 重建並推送 workspace-chrome image
	@echo "$(GREEN)✅ workspace-chrome rebuild 完成$(NC)"

build-workspace-manager: ## 🏗️ 建置 workspace-manager image
	@echo "$(GREEN)🏗️ 建置 workspace-manager image...$(NC)"
	@echo "  Image: $(CYAN)$(WORKSPACE_MANAGER_IMAGE)$(NC)"
	@docker build -t $(WORKSPACE_MANAGER_IMAGE) -f workspace-manager/Dockerfile --target production workspace-manager
	@echo "$(GREEN)✅ workspace-manager 建置完成$(NC)"

push-workspace-manager: ## 📤 推送 workspace-manager image
	@echo "$(GREEN)📤 推送 workspace-manager image...$(NC)"
	@echo "  Image: $(CYAN)$(WORKSPACE_MANAGER_IMAGE)$(NC)"
	@docker push $(WORKSPACE_MANAGER_IMAGE)
	@echo "$(GREEN)✅ workspace-manager 推送完成$(NC)"

rebuild-workspace-manager: build-workspace-manager push-workspace-manager ## 🔁 重建並推送 workspace-manager image
	@echo "$(GREEN)✅ workspace-manager rebuild 完成$(NC)"

build-workspace-runtime: ## 🏗️ 建置 workspace-runtime image
	@echo "$(GREEN)🏗️ 建置 workspace-runtime image...$(NC)"
	@echo "  Image: $(CYAN)$(WORKSPACE_RUNTIME_IMAGE)$(NC)"
	@echo "  Base:  $(CYAN)$(WORKSPACE_RUNTIME_BASE_IMAGE)$(NC)"
	@echo "  Flavor: $(CYAN)$(RUNTIME_BASE)$(NC)"
	@docker build \
		-t $(WORKSPACE_RUNTIME_IMAGE) \
		-f workspace-runtime/Dockerfile \
		--target production \
		--build-context runtime-base=docker-image://$(WORKSPACE_RUNTIME_BASE_IMAGE) \
		.
	@echo "$(GREEN)✅ workspace-runtime 建置完成$(NC)"

push-workspace-runtime: ## 📤 推送 workspace-runtime image
	@echo "$(GREEN)📤 推送 workspace-runtime image...$(NC)"
	@echo "  Image: $(CYAN)$(WORKSPACE_RUNTIME_IMAGE)$(NC)"
	@docker push $(WORKSPACE_RUNTIME_IMAGE)
	@echo "$(GREEN)✅ workspace-runtime 推送完成$(NC)"

rebuild-workspace-runtime: rebuild-runtime-base build-workspace-runtime push-workspace-runtime ## 🔁 重建並推送 workspace-runtime image
	@echo "$(GREEN)✅ workspace-runtime rebuild 完成$(NC)"

build-workspace-nextjs: ## 🏗️ 建置 workspace-nextjs image
	@echo "$(GREEN)🏗️ 建置 workspace-nextjs image...$(NC)"
	@echo "  Image: $(CYAN)$(WORKSPACE_NEXTJS_IMAGE)$(NC)"
	@docker build -t $(WORKSPACE_NEXTJS_IMAGE) -f workspace-nextjs/Dockerfile workspace-nextjs
	@echo "$(GREEN)✅ workspace-nextjs 建置完成$(NC)"

push-workspace-nextjs: ## 📤 推送 workspace-nextjs image
	@echo "$(GREEN)📤 推送 workspace-nextjs image...$(NC)"
	@echo "  Image: $(CYAN)$(WORKSPACE_NEXTJS_IMAGE)$(NC)"
	@docker push $(WORKSPACE_NEXTJS_IMAGE)
	@echo "$(GREEN)✅ workspace-nextjs 推送完成$(NC)"

rebuild-workspace-nextjs: build-workspace-nextjs push-workspace-nextjs ## 🔁 重建並推送 workspace-nextjs image
	@echo "$(GREEN)✅ workspace-nextjs rebuild 完成$(NC)"

build-workspace-operator: ## 🏗️ 建置 workspace-operator image
	@echo "$(GREEN)🏗️ 建置 workspace-operator image...$(NC)"
	@echo "  Image: $(CYAN)$(WORKSPACE_OPERATOR_IMAGE)$(NC)"
	@docker build -t $(WORKSPACE_OPERATOR_IMAGE) -f workspace-operator/Dockerfile workspace-operator
	@echo "$(GREEN)✅ workspace-operator 建置完成$(NC)"

push-workspace-operator: ## 📤 推送 workspace-operator image
	@echo "$(GREEN)📤 推送 workspace-operator image...$(NC)"
	@echo "  Image: $(CYAN)$(WORKSPACE_OPERATOR_IMAGE)$(NC)"
	@docker push $(WORKSPACE_OPERATOR_IMAGE)
	@echo "$(GREEN)✅ workspace-operator 推送完成$(NC)"

rebuild-workspace-operator: build-workspace-operator push-workspace-operator ## 🔁 重建並推送 workspace-operator image
	@echo "$(GREEN)✅ workspace-operator rebuild 完成$(NC)"

rebuild-platform-images: rebuild-workspace-manager rebuild-workspace-runtime rebuild-workspace-chrome rebuild-workspace-nextjs rebuild-workspace-ui rebuild-workspace-operator ## 🔁 重建並推送所有平台 image
	@echo "$(GREEN)✅ 所有平台 image rebuild 完成$(NC)"

##@ 內部命令 (不要直接調用)

_test-runtime:
	@echo "\n$(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo "$(CYAN)   Testing: workspace-runtime$(NC)"
	@echo "$(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@cd workspace-runtime && $(MAKE) test-all

_test-manager:
	@echo "\n$(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo "$(CYAN)   Testing: workspace-manager$(NC)"
	@echo "$(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@cd workspace-manager && $(MAKE) test-all

_test-frontend:
	@echo "\n$(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@echo "$(CYAN)   Testing: frontend$(NC)"
	@echo "$(CYAN)━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━$(NC)"
	@cd frontend && $(MAKE) test
