# Browser Connectivity 契約

此目錄是 TURN Reachability Profile、TURN Path Evidence 與 Browser Connectivity Projection 的唯一宣告式契約來源。

- `contractVersion` 固定為 `browser-connectivity/v1`，未知版本直接拒絕。
- `profileRevision` 是通過驗證後之語意正規 Profile 的 `sha256:<hex>`。
- 物件 key 依 JSON canonical order 輸出，整數以 JSON 十進位表示，所有語意字串先去除首尾空白。
- URL 陣列去除各值首尾空白但保留偏好順序；destination values 與 required vantages 視為集合，會去重並排序。
- `credentialRevision` 是 issuer 提供的非機密 opaque rotation identity。
- Evidence freshness 只採 Evidence Authority 寫入的 `acceptedAt`／`expiresAt`；`measuredAt` 只供診斷。
- Projection 是唯一 admission 判斷，只有 `ready` 與 `degraded` 為 `allowed`。

Go Operator 與 Python Docker reconciler 必須逐案通過同一份 digest vectors 與 evaluator cases，不得新增另一份 evaluator 規則。

執行 `generate_contract_bundle.py` 會產生 committed contract bundle，以及 Go／Python 的版本與 enum 常數；`--check` 同時檢查這些輸出及 Helm TURN Profile schema 的關鍵片段是否漂移。
