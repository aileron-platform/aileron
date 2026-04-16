.PHONY: test test-container test-container-clean

test:
	go test -v ./...

test-container:
	docker compose -f docker-compose.test.yml run --build --rm workspace-operator-test

test-container-clean:
	docker compose -f docker-compose.test.yml down -v --remove-orphans
