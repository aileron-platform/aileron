# Workspace Execution Access Contract

本目錄是 Workspace Execution Access Grant 的唯一宣告式契約來源。Manager 簽發器、
Runtime verifier 與 Terminal verifier 必須通過相同的 `conformance-vectors.json`，不得各自
維護 audience、action 或 claims 變體。

- `claims.schema.json`：Grant claims 與 audience/action 限制。
- `route-inventory.json`：execution-plane 公開入口可要求的 action 集合。
- `conformance-vectors.json`：跨 Python／Go 的簽發與驗證案例。
- `generate_contract_bundle.py`：產生並檢查 committed bundle。
- `generated/contract-bundle.json`：產生物，禁止手動修改。

更新來源後執行：

```bash
docker run --rm -v "$PWD:/repo" -w /repo python:3.12-alpine \
  python contracts/workspace-execution-access/generate_contract_bundle.py
docker run --rm -v "$PWD:/repo:ro" -w /repo python:3.12-alpine \
  python contracts/workspace-execution-access/generate_contract_bundle.py --check
```
