---
title: Aileron MCP 工具
---

# Aileron MCP 工具

Aileron 提供給 agent 使用的內建 MCP 工具，目前有兩個，都由 `workspace-runtime/app/modules/thread/mcp/server.py` 註冊：

| 工具 | 用途 | 是否暫停回合 |
| --- | --- | --- |
| `mcp__aileron__ask_user_question` | 提出結構化選項表單，收集使用者答案 | 是，呼叫後必須立即結束該回合 |
| `mcp__aileron__show_canvas_artifact` | 顯示一張卡片，通知使用者 Canvas artifact 已產出 | 否，呼叫後可繼續輸出 |

`ask_user_question` 用途與適用情境請見 [Question Form](/features/workspace/ai-agent/ai-chat)。本頁記錄兩個工具完整的呼叫規則與 JSON schema。

## ask_user_question

### ask_user_question 呼叫規則

當 agent 決定使用表單時，應呼叫：

```text
mcp__aileron__ask_user_question
```

呼叫後必須立即結束該回合，不要再輸出任何 assistant 文字。使用者送出表單後，平台會以後續 user message resume agent。

`questions` 至少 1 題、最多 5 題。Agent 應在呼叫前刪除不會改變結果的問題，並在有合理推測依據時為每題提供 `default`。

範例參數：

```json
{
  "id": "ppt-output-format",
  "title": "請選擇輸出格式",
  "questions": [
    {
      "id": "output_formats",
      "label": "輸出格式",
      "type": "radio",
      "options": [
        ".pptx",
        "HTML 簡報",
        "兩者都要"
      ],
      "default": ".pptx",
      "required": true
    }
  ]
}
```

### 欄位建議

| 欄位 | 說明 |
| --- | --- |
| `id` | 穩定識別碼，用於後續解析回答。使用 snake_case 或 kebab-case。 |
| `title` | 表單標題，應以使用者看得懂的方式描述這次選擇。 |
| `questions[].id` | 問題識別碼，應對應 workflow 需要的設定或分支。 |
| `questions[].label` | 問題標籤，保持簡短。 |
| `questions[].type` | 支援的型式：`radio`、`checkbox`、`select`、`text`、`textarea`、`number`、`date`、`yes-no`、`option-cards`、`color`。 |
| `questions[].options` | `radio` / `checkbox` / `select` 用的固定選項。文字應可直接呈現給使用者。 |
| `questions[].default` | 選填的預填答案。單選與文字類型使用字串；`checkbox` 或 `multiple` 類型使用字串陣列。預填值會參與 `show_if` 與 `options_by`。 |
| `questions[].required` | 必填問題設為 `true`。 |
| `questions[].show_if` | 條件顯示。`{ "q": "<前面題目的 id>", "eq": "值" }`，另支援 `in`（值清單）與 `not_empty`（有作答即顯示），三者擇一。條件不成立時隱藏該題，隱藏題不計必填、答案不會送出。 |
| `questions[].options_by` | 動態選項。`{ "q": "<前面題目的 id>", "map": { "來源答案": ["選項"] } }`，僅適用 `radio` / `checkbox` / `select`。來源尚未作答或 map 未命中時退回 `options`。 |

### 答案格式

平台送回 agent 的答案以 `[form answers — <id>]` 開頭，並為每個可見問題輸出一個 `- ` 項目。未作答問題輸出 `(skipped)`；`option-cards` 在 card id 與 label 不同時輸出 `Label [value: card-id]`。隱藏問題不會送出。

### 欄位型式

#### `radio` / `checkbox` / `select`

固定選項的單選 / 多選 / 下拉選單，搭配 `options`。

#### `text` / `textarea`

開放式單行 / 多行輸入。可帶 `placeholder`。

#### `number`

數字輸入。支援欄位：

| 欄位 | 說明 |
| --- | --- |
| `min` / `max` | 數值範圍。送出時會 clamp 至範圍內。 |
| `step` | 步進值，預設 `1`。 |
| `unit` | 顯示在輸入框右側的單位標示（純呈現，不會出現在答案中）。 |

```json
{
  "id": "ppt-page-count",
  "title": "請設定簡報頁數",
  "questions": [
    {
      "id": "page_count",
      "label": "頁數",
      "type": "number",
      "min": 1,
      "max": 30,
      "step": 1,
      "unit": "頁",
      "required": true
    }
  ]
}
```

#### `date`

日期或日期時間輸入。

| 欄位 | 說明 |
| --- | --- |
| `mode` | `"date"`（預設）或 `"datetime"`。 |
| `min` / `max` | ISO 字串，限制可選範圍。 |

```json
{
  "id": "project-deadline",
  "title": "請選擇截止日",
  "questions": [
    {
      "id": "deadline",
      "label": "Deadline",
      "type": "date",
      "required": true
    }
  ]
}
```

#### `yes-no`

是非確認。

| 欄位 | 說明 |
| --- | --- |
| `yes_label` / `no_label` | 自訂兩顆按鈕的文字。省略時使用系統 locale 預設。 |

```json
{
  "id": "allow-subagent",
  "title": "是否允許使用 subagent",
  "questions": [
    {
      "id": "allow_subagent",
      "label": "允許 subagent",
      "type": "yes-no",
      "yes_label": "允許",
      "no_label": "拒絕",
      "required": true
    }
  ]
}
```

#### `option-cards`

卡片式選項，比 `radio` / `select` 有更豐富的呈現。

| 欄位 | 說明 |
| --- | --- |
| `multiple` | 設為 `true` 啟用多選，預設單選。 |
| `cards[].id` | 卡片識別碼。 |
| `cards[].label` | 顯示文字，也是送出的答案。 |
| `cards[].description` | 卡片次標說明。 |
| `cards[].icon` | 圖示名稱（[lucide-react](https://lucide.dev/icons) 名稱）。 |
| `cards[].mood` | 選用的情緒／語氣標籤，用於呈現風格變化。 |
| `cards[].palette` | 顏色陣列；當 `icon` 沒指定時顯示為色塊。 |
| `cards[].displayFont` / `cards[].bodyFont` | 卡片標題 / 描述的字型（設計風格用）。 |

當 `icon` 與 `palette` 同時存在時優先顯示 icon。

```json
{
  "id": "doc-type",
  "title": "請選擇文件類型",
  "questions": [
    {
      "id": "doc_type",
      "label": "文件類型",
      "type": "option-cards",
      "required": true,
      "cards": [
        {
          "id": "blog",
          "label": "Blog",
          "description": "口語、有故事性",
          "icon": "feather"
        },
        {
          "id": "api",
          "label": "API 文件",
          "description": "結構化、可搜尋",
          "icon": "code"
        },
        {
          "id": "tutorial",
          "label": "Tutorial",
          "description": "一步一步引導",
          "icon": "book-open"
        }
      ]
    }
  ]
}
```

##### 設計風格（保留 `palette` / 字型）

```json
{
  "id": "visual-direction",
  "title": "請選擇視覺方向",
  "questions": [
    {
      "id": "style",
      "label": "視覺方向",
      "type": "option-cards",
      "required": true,
      "cards": [
        {
          "id": "minimal",
          "label": "Minimal — 乾淨 / 克制",
          "description": "大量留白、嚴謹的字型層次。",
          "palette": [
            "#FFFFFF",
            "#F5F5F5",
            "#1A1A1A",
            "#0066FF"
          ],
          "displayFont": "Inter, sans-serif",
          "bodyFont": "Inter, sans-serif"
        },
        {
          "id": "editorial",
          "label": "Editorial — 雜誌 / 深度",
          "description": "襯線字體搭配精心排版。",
          "palette": [
            "#F8F4EF",
            "#2C1810",
            "#8B4513",
            "#D4A853"
          ],
          "displayFont": "'Playfair Display', serif",
          "bodyFont": "'Lora', serif"
        }
      ]
    }
  ]
}
```

#### `color`

顏色選擇器。

| 欄位 | 說明 |
| --- | --- |
| `swatches` | 預設色票陣列（hex 字串）。 |
| `allow_custom` | 預設 `true`，是否顯示自訂顏色選擇器。 |

送出值會正規化為小寫 7 字元 hex（例：`#ff6b6b`）。

```json
{
  "id": "brand-color",
  "title": "請選擇品牌主色",
  "questions": [
    {
      "id": "brand_color",
      "label": "品牌主色",
      "type": "color",
      "swatches": [
        "#FF6B6B",
        "#4ECDC4",
        "#FFE66D",
        "#1A1A1A"
      ],
      "required": true
    }
  ]
}
```

### 條件邏輯

`show_if` 與 `options_by` 只能參照排序在前的題目；參照錯誤時條件會被忽略（照常顯示、使用固定 `options`），表單不會因此失效。被隱藏題目的答案在評估其他條件時視為空，因此條件會連鎖生效。

```json
{
  "id": "deploy-survey",
  "title": "部署調查",
  "questions": [
    {
      "id": "target",
      "label": "部署方式",
      "type": "radio",
      "options": [
        "Cloud",
        "On-premise"
      ],
      "required": true
    },
    {
      "id": "region",
      "label": "區域",
      "type": "select",
      "show_if": {
        "q": "target",
        "eq": "Cloud"
      },
      "options_by": {
        "q": "target",
        "map": {
          "Cloud": [
            "ap-northeast-1",
            "us-west-2"
          ]
        }
      }
    },
    {
      "id": "notes",
      "label": "機房備註",
      "type": "textarea",
      "show_if": {
        "q": "target",
        "eq": "On-premise"
      }
    }
  ]
}
```

### PPT Skill 範例

#### 流程選擇

```json
{
  "id": "ppt-flow-choice",
  "title": "請選擇簡報製作流程",
  "questions": [
    {
      "id": "flow",
      "label": "流程模式",
      "type": "radio",
      "options": [
        "詳細 flow",
        "快速 flow"
      ],
      "required": true
    }
  ]
}
```

#### 預覽方式

```json
{
  "id": "ppt-preview-mode",
  "title": "請選擇風格預覽方式",
  "questions": [
    {
      "id": "preview_mode",
      "label": "預覽方式",
      "type": "radio",
      "options": [
        "SVG 快速預覽",
        "imagegen 高擬真預覽"
      ],
      "required": true
    }
  ]
}
```

#### 輸出格式

```json
{
  "id": "ppt-output-format",
  "title": "請選擇輸出格式",
  "questions": [
    {
      "id": "output_formats",
      "label": "輸出格式",
      "type": "radio",
      "options": [
        ".pptx",
        "HTML 簡報",
        "兩者都要"
      ],
      "required": true
    }
  ]
}
```

## show_canvas_artifact

### show_canvas_artifact 呼叫規則

agent 完成 Canvas artifact（`canvas.json` 與內容檔案）產出後，應呼叫：

```text
mcp__aileron__show_canvas_artifact
```

與 `ask_user_question` 不同，呼叫這個工具不會暫停回合，agent 可以在呼叫後繼續輸出文字。

範例參數：

```json
{
  "title": "Next.js Demo",
  "route": "/"
}
```

### 欄位

| 欄位 | 說明 |
| --- | --- |
| `title` | 必填。顯示在通知卡片上的 artifact 名稱。 |
| `route` | 選用。對應 `canvas.json` 中的路由路徑，例如 `/landing`。 |

### 行為

前端會在對話中顯示一張卡片（標題＋開啟連結），使用者點擊後開啟 Canvas 面板檢視 artifact；卡片本身不會中斷或暫停 agent 的執行。完整 `canvas.json` manifest 契約請見 [Canvas Protocol](/architecture/overview/canvas/protocol)。
