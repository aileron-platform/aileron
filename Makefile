.PHONY: help bootstrap build build-test-support build-k3s-e2e \
        build-kubernetes-contract build-release push-release \
        start up down full-reset verify-local test-manager-cli \
        test-all test-unit test-integration test-runtime test-manager \
        test-frontend test-backend test-coverage test-status clean-test \
        sync-init-schema \
        build-runtime-base-lite build-runtime-base \
        build-workspace-ui build-workspace-chrome-development \
        build-workspace-chrome-kubernetes build-workspace-manager \
        build-workspace-manager-kubernetes build-workspace-runtime \
        build-workspace-runtime-kubernetes build-workspace-canvas \
        build-workspace-operator rebuild-platform-images \
        _test-runtime _test-manager _test-frontend

.DEFAULT_GOAL := help

BAKE := docker buildx bake
COMPOSE := docker compose
LOCAL_COMPOSE := $(COMPOSE) -f docker-compose.yml -f docker-compose.bundled-data-services.yml
# ops.py is the single startup path: it creates the mounted inputs before compose runs.
OPS := python3 scripts/dev/docker/ops.py

CYAN := \033[0;36m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m

help: ## Show available commands
	@echo "$(CYAN)Aileron 本機建置、測試與啟動$(NC)"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(CYAN)%-30s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) }' $(MAKEFILE_LIST)

##@ Standard Docker workflow

build: ## Build and load the complete local image set once with Docker Bake
	@$(BAKE) --load local

build-test-support: ## Build the Operator and Terminal test-support images
	@$(BAKE) --load test-support

build-k3s-e2e: ## Build the complete k3s E2E image set
	@$(BAKE) --load k3s-e2e

build-kubernetes-contract: ## Build the arbitrary-UID contract image set
	@$(BAKE) --load kubernetes-arbitrary-uid

build-release: ## Build and load release images into the local image store
	@$(BAKE) --load release

push-release: ## Push release images with an immutable RELEASE_TAG
	@$(BAKE) --push release

bootstrap: ## Create the operator-supplied inputs the local stack mounts
	@$(OPS) bootstrap

start: ## Start the local stack from existing images without building
	@$(OPS) up

up: ## Build once and then start the local stack
	@$(OPS) up --build

down: ## Stop the local stack
	@$(OPS) down

full-reset: ## Remove the stack, dynamic workspaces, and local data
	@$(OPS) full-reset

verify-local: build test-all start ## Build once, reuse images for tests, and start the final stack

test-manager-cli: ## Run Manager tests in the active container
	@python3 scripts/dev/docker/ops.py test manager

##@ Container tests

test-all: build ## Run Runtime, Manager, and Frontend container tests
	@status=0; \
	$(MAKE) _test-runtime || status=1; \
	$(MAKE) _test-manager || status=1; \
	$(MAKE) _test-frontend || status=1; \
	if [ $$status -eq 0 ]; then echo "$(GREEN)所有 container 測試完成$(NC)"; fi; \
	exit $$status

test-unit: build ## Run Runtime and Manager unit tests followed by Frontend tests
	@status=0; \
	$(MAKE) -C workspace-runtime test-unit || status=1; \
	$(MAKE) -C workspace-manager test-unit || status=1; \
	$(MAKE) -C frontend test-unit || status=1; \
	exit $$status

test-integration: build ## Run Runtime and Manager integration tests
	@status=0; \
	$(MAKE) -C workspace-runtime test-integration || status=1; \
	$(MAKE) -C workspace-manager test-integration || status=1; \
	exit $$status

test-runtime: build ## Run workspace-runtime container tests
	@$(MAKE) -C workspace-runtime test-all

test-manager: build ## Run workspace-manager container tests
	@$(MAKE) -C workspace-manager test-all

test-frontend: build ## Run frontend container tests
	@$(MAKE) -C frontend test

test-backend: build ## Run Runtime and Manager container tests
	@status=0; \
	$(MAKE) _test-runtime || status=1; \
	$(MAKE) _test-manager || status=1; \
	exit $$status

test-coverage: build ## Generate Runtime, Manager, and Frontend coverage
	@status=0; \
	$(MAKE) -C workspace-runtime test-coverage || status=1; \
	$(MAKE) -C workspace-manager test-coverage || status=1; \
	$(MAKE) -C frontend test-coverage || status=1; \
	exit $$status

test-status: ## Show the state of each test Compose project
	@$(COMPOSE) -f workspace-runtime/docker-compose.test.yml ps
	@$(COMPOSE) -f workspace-manager/docker-compose.test.yml ps
	@$(COMPOSE) -f frontend/docker-compose.test.yml ps

clean-test: ## Remove test artifacts and containers
	@$(MAKE) -C workspace-runtime clean-all
	@$(MAKE) -C workspace-manager clean-test
	@$(MAKE) -C frontend clean-test

##@ Database

sync-init-schema: ## Synchronize the shared init schema into the Helm chart
	@./scripts/db/sync-init-schema-to-helm.sh

##@ Focused Bake targets

build-runtime-base-lite: ## Build the Runtime lite base
	@$(BAKE) --load runtime-base-lite

build-runtime-base: ## Build the Runtime lite and Java bases
	@$(BAKE) --load runtime-base-lite runtime-base-java

build-workspace-ui: ## Build the local Frontend image
	@$(BAKE) --load workspace-ui

build-workspace-chrome-development: ## Build the local Browser image
	@$(BAKE) --load workspace-browser

build-workspace-chrome-kubernetes: ## Build the Kubernetes Browser image
	@$(BAKE) --load workspace-browser-kubernetes

build-workspace-manager: ## Build the local Manager image
	@$(BAKE) --load workspace-manager

build-workspace-manager-kubernetes: ## Build the Kubernetes Manager image
	@$(BAKE) --load workspace-manager-kubernetes

build-workspace-runtime: ## Build the local lite Runtime image
	@$(BAKE) --load workspace-runtime-lite

build-workspace-runtime-kubernetes: ## Build the Kubernetes Runtime image
	@$(BAKE) --load workspace-runtime-kubernetes

build-workspace-canvas: ## Build the local Canvas image
	@$(BAKE) --load workspace-canvas

build-workspace-operator: ## Build the Kubernetes Operator image
	@$(BAKE) --load workspace-operator-kubernetes

rebuild-platform-images: build ## Build the complete local image set

##@ Internal targets

_test-runtime:
	@$(MAKE) -C workspace-runtime test-all

_test-manager:
	@$(MAKE) -C workspace-manager test-all

_test-frontend:
	@$(MAKE) -C frontend test
