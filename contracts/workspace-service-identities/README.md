# Workspace Service identity 契約

`registry.json` 是 Runtime、Terminal、Browser 與 Canvas 在 Kubernetes 內部的
Service component、主要 port、Service name、FQDN 與 URL 的唯一權威來源。

Operator container suite 會從 registry 重新產生 Go 與 Python artifacts 並逐位元組
比對；Manager 與 Operator 的 public behavior tests 也會共同執行同一組 vectors。
變更 identity 時必須同步通過兩種語言的 contract tests，禁止在 consumer 另設 prefix。

在 container 中只產生暫存 artifacts：

```bash
docker compose -f workspace-operator/docker-compose.test.yml run --rm \
  workspace-operator-test go run ./cmd/generate-workspace-service-identities \
  --contract /contracts/workspace-service-identities/registry.json \
  --go-out /tmp/registry_generated.go \
  --python-out /tmp/service_identities_generated.py
```
