---
title: 群組
---

# 群組

## 目的與入口

Platform admin 由 user-management 的 groups 與 group members route 建立本地群組並管理成員。

## 核心概念

Provider-side groups（若 provider 提供）與 Aileron local groups 是不同層次。Resource
`group_share` 只引用 Aileron local group，不複製 provider membership；LDAP group 不會自動
成為 resource share。

## 主要流程

建立或選擇 local group、加入／移除成員，完成後刷新使用者與 resource authorization。所有
操作都需要 platform admin Operation ID。

## 失敗與安全

群組變更可能立即改變 resource effective role；Frontend 必須重新查詢後端授權。讀取受限時
保留可讀內容與 disabled mutation controls，錯誤使用 i18n key。

## 原始碼依據

- `frontend/src/features/user-management/`
- `workspace-manager/app/modules/identity/groups.py`
- `workspace-manager/app/modules/identity/group_router.py`

## 相關文件與 API

- [身分與存取控制](/architecture/overview/identity-and-access)
- [Manager API](/api/manager-api)
