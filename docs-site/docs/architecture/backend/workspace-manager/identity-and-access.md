---
title: Manager OIDC BFF 與 Session
---

# Manager OIDC BFF 與 Session

## OIDC Core

`workspace-manager/app/modules/auth` 是外部 OIDC 的唯一 trust boundary。OIDC Core 負責
Authorization Code + PKCE、state、nonce、Discovery、JWKS、ID／Access Token validation、
optional UserInfo 與 end-session。完成 External Principal 與本地使用者快照後，不保存
provider access token、ID token 或 refresh token。

靜態設定錯誤會使 Manager 啟動失敗。啟動必須取得 canonical Discovery 文件與至少一把
可用 signing key 才可 ready。Provider 暫時不可達時，新登入流程 fail closed，但既有有效
Manager Session 與本機授權不會因此失效。OIDC flow 只使用未過期的記憶體 cache，未知
`kid` 最多觸發一次 refresh。

## External Principal 與本地授權

External Principal 的 identity key 是 `(canonical issuer, sub)`。首次登入才建立本地 member；
不同 issuer 或相同 email 不會自動合併。成功 callback 建立 Manager Session 後，有效
Session 期間不呼叫 IdP、UserInfo、introspection 或 Provider Token refresh。每個 Manager
request 都以本機 Session 與 User snapshot 計算 `allowedOperations`；本機停用、非法角色或
Session 撤銷會在下一個 request 生效。

`ManagerRequestAuthentication` 是受保護 HTTP request 的單一認證 Module。它以一次 indexed
projected JOIN 取得 Session 與 User 所需欄位，驗證 Session 證據、Local User Authorization
Policy、Origin／CSRF，視固定內部 touch window 執行 atomic conditional update，並在關閉
認證資料庫連線後產生 immutable request context 與 Authorization Actor。Session Bootstrap、
Logout 與 operation policy 使用同一份 context，不再次解析 Cookie 或查詢 Session／User。

## Session 與 CSRF

- `GET /api/v1/oauth2/login`：建立 state、nonce、PKCE verifier，並 redirect provider。
- `GET /api/v1/oauth2/callback`：由 Manager 交換 code、驗證 provider 回應並建立 session。
- `GET /api/v1/oauth2/session`：回傳本地 user、`allowedOperations`、absolute expiry 與 Session 綁定的 CSRF token。
- `POST /api/v1/oauth2/logout`：要求 session、Origin 與 CSRF，先刪除本地 session。

Cookie 只含 opaque handle；資料庫保存 SHA-256 hash、`user_id`、issuer、subject、
authentication context 與時間欄位。CSRF token 只保留在 Frontend memory，資料庫保存目前
Session 綁定 token 供 mutation 驗證。GET／HEAD／OPTIONS 不得執行 mutation。

Session 證據缺少、過期、撤銷或 principal binding 不一致時回傳
`401 MANAGER_SESSION_REQUIRED`；Frontend 才可啟動一次 OIDC 重新登入。Session 證據有效，
但 Local User Authorization Policy 或平台 operation 不允許時回傳
`403 PLATFORM_AUTHORIZATION_DENIED`，保留 Session 且不得重新登入。Origin 與 CSRF 拒絕也
使用各自的 403 錯誤碼。

Session activity touch 與 absolute expiry cleanup 使用固定內部 window、週期與有限 batch；
request 熱路徑不會同步刪除過期 Session。這兩項生命週期參數不提供環境變數、Compose
設定或 Helm value。

## Execution Grant issuance seam

`POST /api/v1/workspaces/{workspaceId}/execution-grants` 接受 runtime instance、單一 audience
與明確 actions。Manager 對每個 action 呼叫 `WorkspaceRuntimeAccessService.authorize`，再由
`RuntimeAssertionService.sign_execution_grant` 使用目前 instance 與 access revision 簽發。
沒有 `all`、隱含 action 展開或跨 audience Grant。

正式 claims、七個 actions、audience constraint 與測試向量由
`contracts/workspace-execution-access/` 管理；Manager、Runtime 與 Terminal 不得另外定義
不同的 public contract。

## Container 驗證

```bash
docker compose -f workspace-manager/docker-compose.test.yml run --rm workspace-manager-test \
  uv run pytest tests/unit/modules/auth \
  tests/unit/modules/workspace/runtime/test_execution_grant.py \
  tests/unit/modules/workspace/runtime/test_execution_grant_contract.py
```

## 相關文件

- [身分與存取控制](/architecture/overview/identity-and-access)
- [外部 OIDC 安裝](/installation/oidc)
- [Manager API](/api/manager-api)
