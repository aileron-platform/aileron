---
title: 應用中心
---

# 應用中心

應用中心只顯示 Aileron Managed Registry working tree 內的 Plugin。這些 Plugin 可由 Platform admin 直接建立，或從 Git repository、ZIP 封存檔匯入；系統不註冊或追蹤外部 Marketplace catalog。

建立或匯入完成後，Plugin 立即出現在應用中心，沒有 Draft、Publish、Sync、Rollback 或獨立 Re-import 狀態。若再次匯入相同 package ID，畫面會要求使用者選擇新版本，或明確確認 Replace。

Plugin 的 package format 在建立後不可變，並決定編輯器可用功能：

- `claude-native`：支援 Claude Code native 資源，包含 Output Styles。
- `codex-native`：支援 Codex native 資源，不包含 Output Styles。
- `agent-plugin/1.0.0`：第一階段只提供 Basic、MCP、Skills 與 Files。

member 與 admin 可瀏覽、匯出及安裝；建立、匯入、編輯與刪除限定 Platform admin。

## 相關文件

- [瀏覽與安裝](./browse-and-install.md)
- [建立與匯入](./author-and-publish.md)
- [Registry 與治理](./registry-and-governance.md)
- [Manager API](/api/manager-api)
