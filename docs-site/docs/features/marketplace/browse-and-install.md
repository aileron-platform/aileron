---
title: 瀏覽與安裝
---

# 瀏覽與安裝

## 目的與入口

由應用市集 catalog 或套件詳情進入，搜尋、篩選、匯出並安裝套件。

## 角色與允許操作

member 與 admin 可瀏覽、匯出及安裝；以 platform Operation ID 做最終檢查。

## 核心概念

provider 與 package ID 共同形成 route identity；安裝產生 user copy，不修改 catalog source。

## 主要流程

開啟詳情、選擇安裝目標、建立 user copy，完成後以 canonical identity 重新整理清單。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

clone_failed、衝突與不支援 provider 需明確顯示；不得產生兩份同一 canonical resource。

## 原始碼依據

- `frontend/src/features/marketplace/`
- `workspace-manager/app/modules/marketplace/user_copy.py`
- `packages/aileron-marketplace-core/`

## 相關架構與 API

- [version-control](/architecture/overview/version-control)
- [manager-api](/api/manager-api)
