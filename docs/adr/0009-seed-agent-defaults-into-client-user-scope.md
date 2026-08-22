---
status: accepted
---

# 將 Agent Defaults 初始化至 Client User Scope

Aileron 在 Workspace Runtime HOME 首次初始化時，將 Agent Defaults 分別複製到 Codex、Claude 與 OpenCode 的 Client User Scope。三個 Target Clients 各自擁有獨立副本，不共用 project-scope 目錄、symbolic link 或 hard link。初始化只建立缺少的預設 Skill；同名既有 Skill 由 Workspace 擁有並保持不變。

正式目標路徑為 `$CODEX_HOME/skills`、`${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills` 與 `$HOME/.config/opencode/skills`。初始化器與 user-scope path resolver 必須遵循相同路徑契約。任何 scope root 或目標的 symbolic link、非目錄或不安全路徑都使整次初始化失敗，且不得寫入完成 marker。

## Consequences

- Agent Defaults 對 Workspace 的所有使用者與 sessions 可見，但不等同於單一 human user 的 personal scope。
- 初始化完成後，各 Target Client 的副本是 Workspace-owned standalone resources；修改或刪除不會被 Runtime 重啟或映像升級自動還原。
- Agent Defaults 不建立安裝、升級、解除安裝或持續 reconciliation lifecycle。
- Runtime project scope 不承載 Agent Defaults；project-level client settings 仍屬不同契約。
- 實作不提供舊 project-scope layout、marker 或既有 Workspace 內容的相容與遷移流程。
