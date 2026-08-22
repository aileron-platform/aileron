# Aileron 資料服務

本文件定義 Aileron 安裝與執行期間使用的資料服務邊界，避免將服務位置、資料所有權與部署生命週期混為一談。

## 語言

**外部資料服務**：
由 Aileron 安裝範圍之外提供並維運的資料服務；Aileron 只依約定的連線、權限與生命週期契約使用它。
_避免：外部資料庫、遠端資料庫_

**平台資料庫**：
由 Aileron 專用、保存 control plane 資料及 Workspace Runtime 狀態的 PostgreSQL database；可由內建或外部 PostgreSQL service 提供，Runtime 狀態依 Workspace 隔離。
_避免：Manager 資料庫、Runtime 資料庫_

**身分資料庫**：
使用 Aileron Identity Plane 時，由身分提供者專用且不與平台資料庫或其他應用共用的 PostgreSQL database；可由內建或外部 PostgreSQL service 提供。
_避免：Keycloak 平台資料庫_

**資料服務模式**：
一條資料服務連線在一次 Aileron 安裝中選定的唯一來源，分為內建與外部；同一條連線不會同時使用兩種來源。
_避免：外部開關、混合模式_

**Runtime login**：
Aileron 為單一 Workspace Runtime generation 擁有的 PostgreSQL cluster role；其生命週期與該 Workspace 的 Runtime 狀態綁定。
_避免：Runtime 使用者、Workspace 資料庫帳號_

**Workspace generation**：
Workspace 執行平面一次可被辨識、啟用與替換的生命週期實體；其執行資源、控制授權與資料存取授權必須屬於同一個 generation，且同一 Workspace 同一時間最多只有一個 generation 擁有有效資料存取授權。
_避免：Runtime instance、單一工作負載版本_

**Runtime database connection**：
單一 Workspace generation 用來存取平台資料庫內專屬 Runtime 狀態的連線契約；它使用該 generation 的 Runtime login，且不代表對整個平台資料庫的存取權。
_避免：平台資料庫 URL、共用 Runtime 連線_

**一般 Redis 連線**：
提供 Manager 快取與協調用途的 Redis logical connection 與 keyspace，與工作佇列及工作結果連線分開配置。
_避免：共用 Redis URL_

**工作佇列 Redis 連線**：
提供非同步工作傳遞用途的 Redis logical connection 與 keyspace，可與其他 Redis 連線指向相同或不同服務。
_避免：Celery Redis_

**工作結果 Redis 連線**：
提供非同步工作結果保存用途的 Redis logical connection 與 keyspace，可與其他 Redis 連線指向相同或不同服務。
_避免：Celery Redis_

**備份產物**：
由 Aileron 明確 backup 操作建立、可用於還原平台或身分資料的檔案；其保存、加密、retention 與異地複本由部署契約指定，Helm uninstall 不會刪除。
_避免：暫存 dump、解除安裝備份_

**資料服務 revision**：
部署者在 Secret、CA 或 endpoint material 變更時同步更新的非秘密版本識別；它用來觸發需要的 workload rollout，不代表 projected file 更新會自動重建既有 connection pool。
_避免：Secret 版本、自動換線_

**資料服務營運者**：
在 Aileron 安裝範圍之外建立、備份、還原及維運外部資料服務的一方；不負責 Aileron 擁有的資料結構與 Workspace 隔離資源。
_避免：資料庫擁有者_

**Aileron 資料邊界**：
Aileron 在指定資料服務內擁有的平台資料結構、Identity Plane 資料、Workspace schema、Runtime login、Redis keyspace 與備份產物；擁有這些資源不代表可以刪除承載它們的外部 service、cluster 或 database。
_避免：外部資料庫管理權_

**外部資料清除**：
經明確確認後刪除 Aileron 資料邊界內資源的獨立操作；一般解除安裝會保留外部資料，不等同外部資料清除。
_避免：解除安裝清理、隱含清除_
