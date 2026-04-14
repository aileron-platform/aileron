---
sidebar_position: 3
title: OpenSpec 工作流
---

# OpenSpec 工作流

## 概覽

OpenSpec 已整合為 Aileron 的 workspace 內建能力，而不只是附屬 slash command 或外部文件流程。它把變更提案、設計、任務拆解與實作推進，整合到同一個 workspace 工作流中。

在 Aileron 中，OpenSpec 的定位是：

- 在 workspace 中原生瀏覽 `openspec/` 文件
- 在 chat composer 中直接發動 workflow actions
- 在 runtime 內可靠地提供 OpenSpec CLI 執行能力

## 內建能力

### OpenSpec Browser

Workspace 側欄中的 `OpenSpec` 功能可直接讀取專案根目錄下的 `openspec/`，讓你快速查看：

- `proposal.md`
- `design.md`
- `tasks.md`
- 各 capability 的 `spec.md`

這讓 OpenSpec 不再只是檔案樹中的一組 Markdown，而是具備專用導覽、狀態與上下文的 workspace 原生能力。

### OpenSpec Actions

Chat composer 內建 `OpenSpec Actions` 入口，可直接插入對應 workflow 草稿，協助你從目前上下文快速進入下一步，例如：

- `propose`
- `explore`
- `apply`
- `archive`
- `continue`
- `verify`

這些 action 不再被視為 generic slash command 的附屬選項，而是被建模成具備狀態、推薦與分組的 workflow actions。

### Runtime CLI Foundation

`workspace-runtime` 會內建 OpenSpec CLI，確保每個 workspace 都能在一致的環境下執行 OpenSpec workflow，而不需要專案額外安裝或手動補齊依賴。

## 為什麼這很重要

OpenSpec 在 Aileron 裡的價值，不只是讓文件「看得到」，而是讓使用者能把以下事情串成同一條工作流：

1. 看目前的 change 與 spec 狀態
2. 確認下一步應該做 proposal、explore、apply 或 archive
3. 直接從 chat composer 發動對應動作
4. 回到 workspace 持續編輯與追蹤變更

## 目前狀態

OpenSpec 已經是平台內建能力，並且已與 workspace 導覽、chat composer 與 runtime CLI 整合。不過推薦邏輯、狀態感知與更多 workflow 細節仍會持續強化。

## 後續方向

- 強化 change-aware 與 profile-aware 的推薦邏輯
- 持續補齊更多 workflow actions 的體驗一致性
- 與多 Agent 工作流整合得更自然
- 與團隊協作、worktree 導向的開發流程進一步結合
