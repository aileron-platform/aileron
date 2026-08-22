# 使用 postgres.enabled 選擇 PostgreSQL 資料服務模式

Core 與 Identity chart 各自只使用 `postgres.enabled` 選擇 PostgreSQL 來源：`true` 使用內建 PostgreSQL，`false` 使用外部資料服務。這項決策避免 `enabled` 與另一個 `external` 開關形成矛盾狀態；values schema 必須依此開關驗證條件式必填與禁止欄位。
