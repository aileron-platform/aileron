---
title: 使用者
---

# 使用者

## 目的與入口

Users、role issues 與 disabled 檢視搜尋本地帳號快照，並提供 platform admin 可用的角色與
帳號狀態治理。Aileron 不提供 provider 密碼、臨時密碼或 provider admin API。

## 核心欄位

`oidcIssuer` + `oidcSubject` 是外部 canonical identity；local user ID、username、email、
platform role 與 account state 是獨立欄位。Provider profile claim 更新不會改變 identity。

## 主要流程

登入時由 Manager JIT sync snapshot。Platform admin 可查詢使用者、替換本地平台角色或處理
disabled／role issue；每個 mutation 完成後刷新列表與 `/api/v1/oauth2/session` 的 `allowedOperations`。

## 限制與安全

不可刪除或降級造成平台沒有可用 admin。Token、provider credential 與秘密不寫入 log；所有
錯誤訊息使用 i18n key。

## 原始碼依據

- `frontend/src/features/user-management/`
- `workspace-manager/app/modules/identity/admin_router.py`
- `workspace-manager/app/modules/identity/admin.py::UserAdminService`
- `workspace-manager/app/modules/identity/snapshot_sync.py`

## 相關文件與 API

- [身分同步與 OIDC](/architecture/backend/workspace-manager/identity-and-access)
- [Manager API](/api/manager-api)
