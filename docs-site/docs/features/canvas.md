---
sidebar_position: 1
title: Canvas
---

# Canvas

Canvas tab 顯示 workspace 目前的 active canvas。Active canvas 由 `/workspace/.aileron/canvas.json` 宣告；沒有 manifest 時會顯示 default canvas。

## 狀態

| 狀態 | 含義 |
|---|---|
| Active skill canvas | `canvas.json` 存在且 `owner.type=skill`。畫面由 skill 產生，例如 PPT 預覽或候選方案選擇器。 |
| Active user canvas | `canvas.json` 存在且 `owner.type=user`。畫面由使用者或 agent 建立的 canvas 內容提供。 |
| Default canvas | `canvas.json` 不存在。平台顯示預設說明畫面。 |
| Invalid manifest | `canvas.json` 存在但欄位、路徑或 renderer 前置條件不合法。平台顯示錯誤 notice，iframe 回到 default canvas。 |
| Runtime unhealthy | Manifest 合法，但 renderer 啟動或執行失敗。平台會以 runtime 狀態提示與 manifest 錯誤分開呈現。 |

## Status Notice

Canvas tab 上方的 status notice 會說明目前內容來源：

- Skill canvas 會顯示 manifest 的 `title` 與 `owner.skillName`。
- User canvas 會顯示 manifest 的 `title`。
- Default canvas 會提示目前沒有 active canvas，以及如何建立 `canvas.json`。
- Invalid manifest 會指出 manifest 錯誤類型。
- Runtime unhealthy 會顯示 renderer 啟動失敗或執行異常。

平台 chrome 文案會跟隨目前語系；manifest 內的 `title` 與 `owner.skillName` 視為使用者或 skill 提供的資料，不會被翻譯。

## 停用 Active Canvas

工具列的停用按鈕會呼叫：

```http
DELETE /api/v1/canvases/{workspaceId}/manifest
```

這個操作會刪除 `/workspace/.aileron/canvas.json`，觸發 canvas sync，然後回到 default canvas。重複執行是 idempotent；manifest 已不存在時也會成功。

## Route Picker

Canvas route picker 來自 `canvas.json.routes`。每個 route 需要：

- `path`：例如 `/` 或 `/review`。
- `label`：顯示在 route picker 中的名稱。

`defaultPath` 必須對應其中一個 route。Static canvas 會把 route path 對應到 `contentDir` 內的 HTML；Next.js canvas 則交給 Next.js dev server 處理。

## Review Note

Canvas 內會載入 `/__aileron/bridge.js`。Review mode 使用同一條 bridge 傳遞目標選取、目標框線與 route 變更事件。

使用者可以在 Canvas tab 進入 review mode，點選 iframe 內元素並建立 review note。Review note 可送回 chat，讓 agent 根據具體元素位置與描述調整內容。

## Skill 互動

Skill-owned canvas 可以呼叫：

```js
window.aileron.bridge.emit("STYLE_SELECTED", { direction: "B" });
```

若 frontend 沒有針對該 event 註冊 handler，事件會被轉成 chat draft。這讓 skill shell 可以把使用者在畫面上的選擇帶回 agent 對話。
