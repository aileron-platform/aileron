---
title: 使用者管理
---

# 使用者管理

## 目的與入口

Platform admin 由 `/user-management` 管理本地使用者快照、群組、平台角色與帳號狀態；
資源授權模型仍以[權限與角色](/features/platform/permissions-and-roles)為 canonical。

## 身分與本地帳號

OIDC provider 負責登入與 credential。Manager 以 `(oidc_issuer, oidc_subject)` 作為外部
canonical identity，首次成功登入時 JIT 建立 member snapshot，並同步 username、email 與
display name 等 optional claims。LDAP 與 Keycloak 只可能是外部 provider，
不是 UI 或 API 的管理依賴。

## 角色與操作

所有 user-management Operation ID 都是 platform-admin-only。平台 `admin`／`member` 角色
由 Manager 本地資料管理；Workspace／Knowledge Base 的 `reader`、`manager`、`owner` 與
group share 屬 resource authorization。

## 畫面與失敗行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與 disabled
mutation controls；缺少讀取操作時不啟動受保護 query、Provider 或 WebSocket。同步或資料庫
失敗維持可診斷狀態，不宣告部分成功為完成。

## 原始碼依據

- `frontend/src/features/user-management/UserManagementModule.tsx`
- `workspace-manager/app/modules/identity/admin.py::UserAdminService`
- `workspace-manager/app/modules/identity/snapshot_sync.py`

## 相關文件與 API

- [身分同步與 OIDC](/architecture/backend/workspace-manager/identity-and-access)
- [身分與存取控制](/architecture/overview/identity-and-access)
- [Manager API](/api/manager-api)
