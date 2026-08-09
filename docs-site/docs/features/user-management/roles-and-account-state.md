---
title: 平台角色與帳號狀態
---

# 平台角色與帳號狀態

## 目的與入口

Platform admin 在 user-management 調整本地 `admin`／`member` 平台角色，並處理 role issue、
enabled／disabled account state。

## 核心概念

平台角色只展開 platform operations；停用帳號會讓後續請求立即被本機授權政策拒絕；兩者都不直接改寫
Workspace 或 Knowledge Base resource share。Provider 的 role claim 可作為登入輸入，但
本地 role 是授權的 authoritative state。

## 主要流程

替換本地平台角色或帳號狀態後，下一個 Manager request 直接套用本機
`UserAuthorizationPolicy`，`/api/v1/oauth2/session` 也會依目前角色回傳 `allowedOperations`。
最後一位可用 admin 不能被停用、刪除或降權。

## 失敗與安全

未知或多重受管平台角色視為 role issue 並 fail closed。所有管理操作需要 platform admin；
秘密、token 與 provider response 不寫入 log，顯示文字使用 i18n key。

## 原始碼依據

- `workspace-manager/app/modules/identity/platform_role.py::PlatformRole`
- `workspace-manager/app/modules/identity/authorization.py::PlatformAuthorizationService`
- `workspace-manager/app/modules/identity/admin_router.py`

## 相關文件與 API

- [身分與存取控制](/architecture/overview/identity-and-access)
- [平台權限與角色](/features/platform/permissions-and-roles)
- [Manager API](/api/manager-api)
