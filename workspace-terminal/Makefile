.PHONY: build run test test-container test-container-clean clean docker-build docker-up docker-down

# Build application
build:
	go build -o bin/terminal-service ./cmd/server

# Run application
run:
	go run ./cmd/server/main.go

# Run tests
test:
	go test -v ./...

# Run tests in container
test-container:
	docker compose -f docker-compose.test.yml run --rm workspace-terminal-test

test-container-clean:
	docker compose -f docker-compose.test.yml down -v --remove-orphans

# Run tests with coverage
test-coverage:
	go test -v -coverprofile=coverage.out ./...
	go tool cover -html=coverage.out

# Clean build artifacts
clean:
	rm -rf bin/
	rm -f coverage.out

# Format code
fmt:
	go fmt ./...

# Lint code
lint:
	golangci-lint run

# Download dependencies
deps:
	go mod download
	go mod tidy

# Build Docker image
docker-build:
	docker-compose build

# Start Docker containers
docker-up:
	docker-compose up -d

# Stop Docker containers
docker-down:
	docker-compose down

# View Docker logs
docker-logs:
	docker-compose logs -f terminal-service

# Restart Docker container
docker-restart:
	docker-compose restart terminal-service

# Development mode (hot reload with air)
dev:
	air

# Install development tools
install-tools:
	go install github.com/cosmtrek/air@latest
	go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
