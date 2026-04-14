---
sidebar_position: 3
title: 自動化任務
---

# 自動化任務

## 概覽

Automation 功能讓你可以排程定時執行 Agent workflow，實現自動化 AI 工作流。目前以 Claude Code 的整合最完整，其他 agent 的自動化能力將逐步補齊。

## 技術棧

| 元件 | 說明 |
|------|------|
| Celery | 分散式任務佇列 |
| Redis | Broker + Backend |
| Celery Beat | 定時排程 |
| Flower | 任務監控 UI |

## 建立自動化任務

透過前端 Automation Dashboard 建立任務：

1. 選擇目標 workspace
2. 設定 Cron 表達式（排程時間）
3. 輸入 Agent prompt、工作流草稿或執行指令
4. 設定 Permission Mode
5. 儲存並啟用

## Cron 表達式

標準 cron 格式：

```
# 分 時 日 月 星期
0 9 * * 1-5    # 每工作日上午 9 點
*/30 * * * *   # 每 30 分鐘
0 0 * * 0      # 每週日午夜
```

## 任務監控

### Flower UI

```
http://localhost:5555
```

Flower 提供：
- 即時任務執行狀態
- 歷史執行記錄
- Worker 狀態
- 任務重試

### API

```bash
# 查詢自動化任務列表
GET /api/v1/automation/tasks

# 查詢特定任務執行記錄
GET /api/v1/automation/tasks/{task_id}/runs

# 手動觸發任務
POST /api/v1/automation/tasks/{task_id}/trigger
```

## 使用場景

- **每日程式碼審查**：排程 Claude 定期審查新提交的程式碼
- **文件更新**：自動更新 API 文件或 README
- **測試執行**：定時執行測試套件並回報結果
- **程式碼重構**：週期性優化指定模組
- **Changelog 生成**：自動整理 git log 產生 release notes

## 目前狀態

目前 Automation 主要與 Claude Code 工作流配合最佳。隨著平台持續補齊 OpenCode、Gemini、Codex 等 agent 能力，後續也會逐步擴展更多跨 agent 的自動化情境。
