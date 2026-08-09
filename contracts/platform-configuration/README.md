# 平台設定契約

本目錄是 Aileron 平台設定的 machine-readable 契約，不保存任何安裝值或 Secret material。

- `schema.json`：定義契約 catalog 的結構、Owner、來源類型與允許的處置。
- `contract.json`：列出根 `.env` 安裝輸入、Helm Secret name/key reference、Compose container output env、跨 Adapter 衍生輸出，以及逐項盤點後移除或移回服務預設的項目。
- `conformance-vectors.json`：定義公開 validator CLI 的合法與非法案例。

## 輸入與輸出邊界

根 `.env` 是 Compose 唯一安裝輸入。只有無法從其他值推導、且確實由安裝者決定的名稱會列在 `installationInputs`。根 `docker-compose.yml` 的 `environment` 是 Adapter output；固定 topology、container path 與第三方 image 必要設定不會因此成為使用者可覆寫的輸入。

每個 Compose output 都記錄 `consumer`、必要 `behavior`、`owner`、`sourceKind`、`secret` 與 `disposition`。Secret 只允許唯讀 mounted file reference；契約及 Compose 都不提供明文預設。第三方服務若只能從設定檔讀取 Secret，Adapter 必須在記憶體檔案系統建立權限 `0600` 的暫存設定檔，再以設定檔路徑啟動；長期 process 的 argv 與 environment 不得包含 Secret 值。

Helm Secret 由 `helmSecretReferences` 明確記錄 existing Secret name 與 data key 的 values path。`derivedLogicalOutputs` 分別保存 Compose 與 Helm 的推導模板；Validator 使用同一組 logical input 正規化並比對 Platform Public Origin、OIDC callback 與 Workspace Runtime／Browser／Canvas path，任一 Adapter 漂移即失敗。

只有 `testFixtureOutputs` 明確列出的 disposable 第三方 dependency identity 可以使用 `test-fixture-only` 明文值；Runtime control token、TURN shared secret、Provider credential 等應用層 Secret 即使在測試 Compose 也必須使用臨時 mounted file。

## Validator

正式測試入口只在 Container 內執行：

```sh
docker compose -f scripts/test/platform-configuration/docker-compose.test.yml run --build --rm platform-configuration-validator-test
```

Validator 會檢查 schema、重複 Owner、Helm Secret reference path、Compose／Helm 衍生輸出 parity、根 `.env.example` 的 unknown／derived input、根 Compose output 分類、Secret plaintext、Compose／Helm process `command`／`args`、禁止 alias、fixture path 存在性、產品層持久 Secret fixture，以及測試 Compose 的 host credential 隱式 pass-through。Helm values schema 會拒絕已定義設定面的未知欄位。

## 排除範圍

本契約不檢查 image tag／digest 一致性、不執行跨服務介面相容性檢查，也不提供 runtime contract handshake。舊 alias、fallback 與 migration 不屬於正式契約。
