---
sidebar_position: 8
title: Question Form
---

# Question Form

`<question-form>` 是 agent 或 skill 在聊天中提出結構化選項的互動表單。它適合用來收集少量明確答案，避免使用者需要手動輸入選項文字，也讓後續 workflow 可以穩定解析回答。

## 使用標準

當問題符合以下條件時，優先使用 `<question-form>`：

- 使用者需要從少量固定選項中選一個或多個答案。
- 答案會直接影響 workflow 分支、設定值或輸出格式。
- 選項本身可以用短文字清楚表達。
- 使用者尚未在前文提供明確答案。

常見適用情境：

- 流程選擇，例如 `詳細 flow` / `快速 flow`。
- 預覽方式，例如 `SVG 快速預覽` / `imagegen 高擬真預覽`。
- 輸出格式，例如 `.pptx` / `HTML 簡報` / `兩者都要`。
- 授權確認，例如是否允許使用 subagent 或 parallel agents。
- 少量固定頁面、模式或策略選擇。

## 不適合使用的情境

不要把所有提問都改成表單。以下情境應使用一般聊天、審閱頁或其他專用介面：

- 自由描述需求、補充背景或開放式 brainstorming。
- slide review、頁面標註、區域圈選或視覺回饋。
- 使用者貼回的 review payload 或系統產生的回饋內容。
- 除錯、錯誤分析、技術說明或需要連續追問的討論。
- 使用者已經明確回答，agent 只需要繼續執行。

## 輸出規則

當 agent 決定使用 `<question-form>` 時，該回合回覆應只包含表單區塊，不要在前後加入額外說明。

```xml
<question-form id="ppt-output-format" title="請選擇輸出格式">
{
  "questions": [
    {
      "id": "output_formats",
      "label": "輸出格式",
      "type": "radio",
      "options": [".pptx", "HTML 簡報", "兩者都要"],
      "required": true
    }
  ]
}
</question-form>
```

## 欄位建議

| 欄位 | 說明 |
| --- | --- |
| `id` | 穩定識別碼，用於後續解析回答。使用 snake_case 或 kebab-case。 |
| `title` | 表單標題，應以使用者看得懂的方式描述這次選擇。 |
| `questions[].id` | 問題識別碼，應對應 workflow 需要的設定或分支。 |
| `questions[].label` | 問題標籤，保持簡短。 |
| `questions[].type` | 常用 `radio`、`select`、`checkbox`、`textarea`、`text`、`direction-cards`。 |
| `questions[].options` | 固定選項。選項文字應可直接呈現給使用者。 |
| `questions[].required` | 必填問題設為 `true`。 |

## PPT Skill 範例

### 流程選擇

```xml
<question-form id="ppt-flow-choice" title="請選擇簡報製作流程">
{
  "questions": [
    {
      "id": "flow",
      "label": "流程模式",
      "type": "radio",
      "options": ["詳細 flow", "快速 flow"],
      "required": true
    }
  ]
}
</question-form>
```

### 預覽方式

```xml
<question-form id="ppt-preview-mode" title="請選擇風格預覽方式">
{
  "questions": [
    {
      "id": "preview_mode",
      "label": "預覽方式",
      "type": "radio",
      "options": ["SVG 快速預覽", "imagegen 高擬真預覽"],
      "required": true
    }
  ]
}
</question-form>
```

### 輸出格式

```xml
<question-form id="ppt-output-format" title="請選擇輸出格式">
{
  "questions": [
    {
      "id": "output_formats",
      "label": "輸出格式",
      "type": "radio",
      "options": [".pptx", "HTML 簡報", "兩者都要"],
      "required": true
    }
  ]
}
</question-form>
```

## 實作原則

`<question-form>` 的目標是讓使用者更容易做選擇，而不是暴露內部 workflow。表單文字應描述使用者看得到、能選擇或能採取行動的內容；不要把工具名稱、檔案路徑、runtime 狀態、manifest、worker metadata 等實作細節放進表單。
