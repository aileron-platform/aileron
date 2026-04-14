# agent-browser 操作 workspace-browser 指南

## 概覽

在 workspace-runtime 容器中，可透過 `agent-browser` CLI（Docker 預設安裝版本為 `0.23.0`）以 CDP（Chrome DevTools Protocol）連線到 workspace-browser 容器內的 Chromium 瀏覽器，實現遠端瀏覽器自動化操作。

### 架構

```
workspace-runtime                          workspace-browser
┌────────────────────┐                    ┌──────────────────────────┐
│  agent-browser CLI │ ── CDP connect ──→ │  cdp-proxy (:9223)       │
│  (Rust daemon)     │                    │    ↓                     │
│                    │ ← WebSocket ─────→ │  Chromium (:9222 內部)   │
└────────────────────┘                    │    ↓                     │
                                          │  neko WebRTC (:6080)     │
                                          └──────────────────────────┘
```

- **agent-browser** 以 daemon 模式運行，首次指令自動啟動，後續指令重複使用已建立的連線
- **cdp-proxy** 監聽 9223 port，轉發至 Chromium 內部的 9222 port，並自動改寫 WebSocket URL
- 容器間透過 Docker network 通訊，使用容器名稱作為 hostname

## 前置條件

| 項目 | 說明 |
|------|------|
| agent-browser CLI | 已在 Dockerfile 中透過 `npm install -g agent-browser` 安裝 |
| workspace-browser 容器 | 需在同一 Docker network 內運行且狀態 healthy |
| CDP proxy | workspace-browser 的 9223 port 需可存取 |

## 連線方式

### 方式一：使用 HTTP CDP URL（推薦）

agent-browser 會自動查詢 `/json/version` 取得 WebSocket debugger URL：

```bash
agent-browser connect "http://aileron-workspace-browser-dev:9223"
# ✓ Done
```

### 方式二：使用完整 WebSocket URL

先手動查詢 WebSocket URL，再直接連線：

```bash
# 1. 取得 WebSocket URL
curl -s http://aileron-workspace-browser-dev:9223/json/version | jq -r .webSocketDebuggerUrl
# ws://aileron-workspace-browser-dev:9223/devtools/browser/<session-id>

# 2. 連線
agent-browser connect "ws://aileron-workspace-browser-dev:9223/devtools/browser/<session-id>"
```

### 動態容器名稱

實際部署時容器名稱為 `workspace-browser-{WORKSPACE_ID}`，可搭配環境變數或 `BrowserContainerDiscovery` 使用：

```bash
# 使用環境變數
agent-browser connect "http://${BROWSER_CONTAINER_NAME:-workspace-browser-${WORKSPACE_ID}}:9223"
```

### 驗證連線

```bash
agent-browser get cdp-url
# ws://aileron-workspace-browser-dev:9223/devtools/browser/<session-id>

agent-browser get url
# 目前頁面的 URL
```

## 指令速查

### 導覽與互動

```bash
# 開啟 URL
agent-browser open "https://example.com"
# ✓ Example Domain
#   https://example.com/

# 點擊元素（使用 CSS 選擇器）
agent-browser click "#submit-button"

# 點擊元素（使用 accessibility ref，從 snapshot 取得）
agent-browser click "@e2"

# 填入文字（會先清除再填入）
agent-browser fill "@e13" "搜尋文字"

# 逐字輸入（模擬鍵盤）
agent-browser type "#input" "Hello World"

# 按鍵
agent-browser press "Enter"
agent-browser press "Tab"
agent-browser press "Escape"

# 懸停
agent-browser hover "@e5"

# 捲動
agent-browser scroll down 500
agent-browser scroll up 300

# 下拉選單
agent-browser select "#dropdown" "option-value"
```

### 取得頁面快照（AI 最常用）

```bash
# 無障礙樹快照 — 回傳帶 ref 的元素結構
agent-browser snapshot
# - heading "Example Domain" [level=1, ref=e1]
# - paragraph
#   - StaticText "This domain is for use in..."
# - paragraph
#   - link "Learn more" [ref=e2]
```

> **AI 工作流程重點**：`snapshot` 回傳的 `ref=eN` 可直接作為後續操作的選擇器（`@e1`, `@e2` 等），這是 AI agent 操作瀏覽器的核心模式。

### 截圖

```bash
# 基本截圖
agent-browser screenshot /tmp/page.png

# 帶元素編號標註的截圖
agent-browser screenshot --annotate /tmp/annotated.png

# 整頁截圖
agent-browser screenshot --full /tmp/full-page.png
```

### 取得資訊

```bash
# 頁面 URL
agent-browser get url

# 頁面標題
agent-browser get title

# 元素文字
agent-browser get text "h1"
agent-browser get text "@e1"

# 元素 HTML
agent-browser get html "#content"

# 輸入框的值
agent-browser get value "#search-input"

# 元素屬性
agent-browser get attr "#link" "href"

# 元素數量
agent-browser get count ".list-item"

# CDP WebSocket URL
agent-browser get cdp-url
```

### 等待

```bash
# 等待元素出現
agent-browser wait "#loading-spinner" --state hidden

# 等待頁面載入完成
agent-browser wait --load networkidle

# 等待文字出現
agent-browser wait --text "載入完成"

# 等待 URL 匹配
agent-browser wait --url "**/dashboard"

# 等待固定時間（毫秒）
agent-browser wait 2000
```

### 分頁管理

```bash
# 列出所有分頁
agent-browser tab
#   [0] Google - https://www.google.com/
# → [1] GitHub - https://github.com

# 開新分頁
agent-browser tab new "https://github.com"

# 切換分頁
agent-browser tab 0

# 關閉分頁
agent-browser tab close 1
```

### JavaScript 執行

```bash
agent-browser eval "document.title"
# "agent-browser test - Google 搜尋"

agent-browser eval "document.querySelectorAll('a').length"
# 42
```

### 批次執行

```bash
echo '[
  ["open", "https://example.com"],
  ["snapshot"],
  ["screenshot", "/tmp/batch-result.png"]
]' | agent-browser batch --json
```

### 斷開連線

```bash
# 關閉目前 session
agent-browser close

# 關閉所有 session
agent-browser close --all
```

## AI Agent 典型工作流程

### 流程：搜尋並擷取結果

```bash
# 1. 連線
agent-browser connect "http://workspace-browser:9223"

# 2. 開啟目標網站
agent-browser open "https://www.google.com"

# 3. 取得頁面結構，找到搜尋框 ref
agent-browser snapshot
# → 搜尋框為 @e13

# 4. 填入搜尋文字
agent-browser fill "@e13" "Aileron"

# 5. 送出搜尋
agent-browser press "Enter"

# 6. 等待結果載入
agent-browser wait --load networkidle

# 7. 取得結果頁面快照
agent-browser snapshot

# 8. 截圖存證
agent-browser screenshot /tmp/search-result.png
```

### 流程：表單自動填寫

```bash
# 1. 開啟表單頁面
agent-browser open "https://example.com/form"

# 2. 快照找到欄位
agent-browser snapshot

# 3. 依序填寫
agent-browser fill "@e3" "使用者名稱"
agent-browser fill "@e4" "user@example.com"
agent-browser fill "@e5" "密碼"
agent-browser select "@e6" "Taiwan"

# 4. 勾選同意
agent-browser click "@e7"

# 5. 送出
agent-browser click "@e8"

# 6. 等待結果
agent-browser wait --text "提交成功"
```

## 與 container_discovery 整合

workspace-runtime 的 `BrowserContainerDiscovery` 可提供連線資訊：

```python
from app.utils.container_discovery import BrowserContainerDiscovery

# 取得 CDP URL
cdp_url = BrowserContainerDiscovery.get_cdp_endpoint()
# → "http://workspace-browser-default:9223"

# 檢查瀏覽器是否可用
available = BrowserContainerDiscovery.is_browser_available()

# 取得完整資訊
info = BrowserContainerDiscovery.get_browser_info()
# → BrowserContainerInfo(
#     container_name="workspace-browser-default",
#     webrtc_internal_url="http://workspace-browser-default:6080",
#     cdp_url="http://workspace-browser-default:9223"
#   )
```

在程式中搭配 subprocess 呼叫：

```python
import asyncio

async def browser_connect():
    cdp_url = BrowserContainerDiscovery.get_cdp_endpoint()
    proc = await asyncio.create_subprocess_exec(
        "agent-browser", "connect", cdp_url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

async def browser_snapshot():
    proc = await asyncio.create_subprocess_exec(
        "agent-browser", "snapshot",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode()
```

## 環境變數

agent-browser 支援以下環境變數進行配置：

| 變數 | 說明 |
|------|------|
| `AGENT_BROWSER_SESSION` | Session 名稱 |
| `AGENT_BROWSER_DEFAULT_TIMEOUT` | 預設操作逾時（毫秒） |
| `AGENT_BROWSER_SCREENSHOT_DIR` | 截圖預設目錄 |
| `AGENT_BROWSER_IDLE_TIMEOUT_MS` | daemon 閒置自動關閉時間 |
| `AGENT_BROWSER_DOWNLOAD_PATH` | 下載檔案路徑 |

## 注意事項

1. **daemon 生命週期**：agent-browser daemon 在首次指令時自動啟動，閒置後自動退出。`close` 指令會關閉 daemon。
2. **session 隔離**：不同 session 維持獨立的 cookies/storage，可用 `--session <name>` 切換。
3. **CDP proxy URL 改寫**：workspace-browser 的 cdp-proxy 會根據請求的 `Host` header 改寫 WebSocket URL，確保跨容器連線正確。
4. **防火牆**：workspace-browser 容器內的 Chromium 可能受 `--disable-file-system` 等啟動參數限制，某些本地檔案操作可能不可用。
5. **`close` vs `disconnect`**：`agent-browser close` 會關閉 daemon 與瀏覽器 session（不會關閉 Chromium 本身），下次操作需重新 `connect`。
