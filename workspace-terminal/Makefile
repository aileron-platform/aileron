.PHONY: build run test clean docker-build docker-up docker-down

# 建構應用
build:
	go build -o bin/terminal-service ./cmd/server

# 執行應用
run:
	go run ./cmd/server/main.go

# 執行測試
test:
	go test -v ./...

# 執行測試（帶覆蓋率）
test-coverage:
	go test -v -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out

# 清理建構產物
clean:
	rm -rf bin/
	rm -f coverage.out

# 格式化代碼
fmt:
	go fmt ./...

# 代碼檢查
lint:
	golangci-lint run

# 下載依賴
deps:
	go mod download
	go mod tidy

# Docker 建構
docker-build:
	docker-compose build

# Docker 啟動
docker-up:
	docker-compose up -d

# Docker 停止
docker-down:
	docker-compose down

# Docker 查看日誌
docker-logs:
	docker-compose logs -f terminal-service

# Docker 重啟
docker-restart:
	docker-compose restart terminal-service

# 開發模式（使用 air 熱重載）
dev:
	air

# 安裝開發工具
install-tools:
	go install github.com/cosmtrek/air@latest
	go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest

