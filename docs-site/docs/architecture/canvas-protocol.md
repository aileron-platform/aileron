---
sidebar_position: 4
title: Canvas Protocol
---

# Canvas Protocol

Aileron Canvas 只使用一個 active canvas 宣告：`/workspace/.aileron/canvas.json`。檔案存在時，management-server 解析 manifest 並啟動對應 renderer；檔案不存在時，Canvas tab 顯示 default canvas。

## Detection 流程

```text
detectCanvas()
  ├─ /workspace/.aileron/canvas.json exists?
  │    ├─ yes: parse + validate manifest
  │    │    ├─ kind=static: serve contentDir with static handler
  │    │    └─ kind=nextjs: launch Next.js dev server from contentDir
  │    └─ no: serve default-canvas
  └─ return manifestStatus + runtimeStatus
```

平台不再讀取 `/web-canvas/route.json`，也不從 `.next/` 或 `*.html` 推斷 canvas 類型。`canvas.json` 是唯一 source of truth。

## Manifest 欄位

`/workspace/.aileron/canvas.json` 必須符合下列結構：

```json
{
  "version": 1,
  "kind": "static",
  "contentDir": "./canvases/demo",
  "title": "Demo Canvas",
  "owner": {
    "type": "skill",
    "skillName": "ppt-image-first"
  },
  "routes": [
    { "path": "/", "label": "Home" }
  ],
  "defaultPath": "/"
}
```

| 欄位 | 說明 |
|---|---|
| `version` | 目前只接受整數 `1`。 |
| `kind` | Renderer 類型，只接受 `static` 或 `nextjs`。 |
| `contentDir` | Canvas 內容目錄。相對路徑以 `/workspace/.aileron/` 為基準，絕對路徑必須位於 `/workspace/` 之下。 |
| `title` | Canvas 顯示名稱。這是 manifest 資料，frontend 會把它嵌入 i18n 文案，不翻譯字串本身。 |
| `owner.type` | `skill` 或 `user`，只影響 status notice 文案。 |
| `owner.skillName` | `owner.type=skill` 時必填。 |
| `routes` | Route 清單。每筆包含 `path` 與 `label`。 |
| `defaultPath` | 預設 route，必須命中其中一筆 `routes[].path`。 |

## contentDir 安全規則

`contentDir` 必須符合三條安全規則：

- 解析後必須在 `/workspace/` 內。
- 不可包含 `..` traversal。
- 路徑任何一段都不可經過 symlink。

`/__aileron/*` 是平台保留路徑。Skill 或使用者 canvas 不應提供同名檔案。

## kind 選擇

使用 `static` 的情境：

- 內容是 HTML、CSS、JS、圖片等靜態檔案。
- 修改 HTML 後，只需要重新整理 iframe 就能看到變更。
- 不需要 Next.js routing、HMR 或 server-side dev server。

使用 `nextjs` 的情境：

- 內容目錄是一個 Next.js app。
- `package.json` 內有 `next` dependency。
- 需要 Next.js dev server 與 HMR。

### static 範例

```text
/workspace/.aileron/
├── canvas.json
└── canvases/demo/
    ├── index.html
    ├── app.js
    └── styles.css
```

```json
{
  "version": 1,
  "kind": "static",
  "contentDir": "./canvases/demo",
  "title": "Static Demo",
  "owner": { "type": "user" },
  "routes": [
    { "path": "/", "label": "Home" },
    { "path": "/review", "label": "Review" }
  ],
  "defaultPath": "/"
}
```

### nextjs 範例

```text
/workspace/.aileron/
├── canvas.json
└── canvases/next-demo/
    ├── app/page.tsx
    ├── package.json
    └── next.config.js
```

```json
{
  "version": 1,
  "kind": "nextjs",
  "contentDir": "./canvases/next-demo",
  "title": "Next.js Demo",
  "owner": { "type": "user" },
  "routes": [
    { "path": "/", "label": "Home" }
  ],
  "defaultPath": "/"
}
```

## Chat Artifact Tag

完成 `canvas.json` 原子寫入後，在 chat 輸出：

```html
<artifact type="canvas" />
```

這個 tag 只負責切到 Canvas tab 並觸發 sync。實際顯示內容完全由當下的 `canvas.json` 決定。不要使用舊的 `web-canvas`、`preview`、`previewId`、`mode` 或 `target` 屬性。

## Bridge API

management-server 會對 static、nextjs、default canvas 的 HTML 注入：

```html
<script src="/__aileron/bridge.js" data-aileron-canvas-bridge="true"></script>
```

Bridge source 為 `aileron-canvas-bridge`，version 為 `2`。Canvas 內可用：

```js
window.aileron.bridge.emit("STYLE_SELECTED", { direction: "B" });
```

### 內建 review event family

平台保留並處理這些 event：

- `BRIDGE_READY`
- `ROUTE_CHANGED`
- `TARGET_SELECTED`
- `TARGET_RECTS`
- `BRIDGE_ERROR`

### SKILL_EVENT 規則

`window.aileron.bridge.emit(eventType, data)` 會送出 `SKILL_EVENT`。限制如下：

- `eventType` 必須符合 `^[A-Z][A-Z0-9_]*$`。
- serialized payload 不可超過 32 KB。
- 同一個 `eventType` 200ms 內重複 emit 會 debounce，只送最後一次。

Frontend 若沒有註冊 handler，會把 `SKILL_EVENT` 轉成 chat draft。註冊 handler 命中時，不會 fallback 到 chat draft。

## 常見錯誤

| errorCode | 原因 | 處理方式 |
|---|---|---|
| `INVALID_MANIFEST` | JSON 無法解析或 schema 不合規。 | 檢查必填欄位、欄位型別與 enum。 |
| `STATIC_INDEX_MISSING` | `kind=static` 但 `contentDir/index.html` 不存在。 | 補上 `index.html` 或修正 `contentDir`。 |
| `NEXTJS_PROJECT_INVALID` | `kind=nextjs` 但缺 `package.json` 或 `next` dependency。 | 補齊 Next.js 專案結構。 |
| `CONTENT_DIR_TRAVERSAL` | `contentDir` 含 `..`。 | 改用 `/workspace/` 內安全路徑。 |
| `CONTENT_DIR_OUTSIDE_WORKSPACE` | `contentDir` 解析後離開 `/workspace/`。 | 將內容放回 workspace 內。 |
| `CONTENT_DIR_SYMLINK` | `contentDir` 路徑經過 symlink。 | 使用實體目錄，不使用 symlink。 |

## Sync 語義

Renderer 直接 live-read `contentDir`。修改靜態檔案後重新整理 iframe 即可；Next.js app 由 HMR 處理 source 變更。Sync 只用於重新讀取 `canvas.json`，例如 `kind`、`contentDir`、`routes`、`title` 或 owner metadata 變更。
