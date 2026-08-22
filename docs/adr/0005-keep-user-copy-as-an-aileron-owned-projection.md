---
status: accepted
---

# 保留 User Copy 作為 Aileron-owned projection

Aileron 將 User Copy 與 Target Client CLI 擁有的 Plugin Installation 視為兩種不同 delivery mode。User Copy 由 Aileron 解析指定 Plugin Package Format，將可投影資源 transactionally 寫入指定 Target Client 的 Client User Scope，完成後產生 Standalone Agent Resources，而不是 Installed Plugin。來源解析依 `packageFormat`，目標路徑與轉換依 `targetClient`，兩者不得再以 `provider` 合併表示；這讓 native package 與 `agent-plugin/1.0.0` 共用同一條安全 materialization 流程，又不建立假的 Plugin lifecycle。

## Consequences

- Aileron 是 User Copy preflight、validation、conflict detection、apply、rollback 與結果的權威；Target Client CLI 不參與 User Copy。
- User Copy 不建立 Installed、Enabled、Disabled、Upgrade 或 Uninstall 狀態，也不從 Plugin inventory 推導成功。Target Client 是否在既有 session 重新載入 standalone resource 是另一個事實。
- User Copy request、proof、digest、lock、audit 與 target identity 必須分別包含 `packageFormat` 與 `targetClient`；`provider`、provider adapter 與 provider state root 視為從未存在，不保留相容層。
- Client User Scope 在 Aileron 中由 Workspace 專屬 Runtime HOME 實現並由 Workspace 協作者共用；產品介面不得把它描述為單一 human user 的 personal scope。
- User Copy 一次投影所有可投影資源。component-level invalid 或 unsupported resources 可依 package format 的 failure boundary 略過，但使用者必須對綁定 `projectionDigest` 的 partial copy 明確確認；不得靜默略過或因此阻擋其他獨立資源。
- `agent-plugin/1.0.0` 中引用 `${PLUGIN_DATA}` 的 MCP entry 第一階段不可投影，因為 Standalone Agent Resource 沒有等價的 plugin data lifecycle。第一階段只註冊 `agent-plugin/1.0.0 -> codex`；未來只為正式支援 Agent Plugins 且已有 Aileron projection adapter 的 Target Client 增加 pair。
- 完整設計與重構順序記錄於 `docs/design/marketplace-user-copy-refactor.md`。
