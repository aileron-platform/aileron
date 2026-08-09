---
title: Kubernetes Workspace 防火牆
description: 建立時 seed、UI 可刪除網域與 Cilium 套用狀態
---

# Kubernetes Workspace 防火牆

## 唯一真相來源

新 Workspace 建立時，Manager 將 Helm `firewall.seed` 寫入資料庫。建立完成後，資料庫中的
Workspace firewall desired state 是唯一真相來源。

- seed 是初始值，不是永久規則。
- 使用者可在 UI 新增或刪除任何 seed domain。
- Manager、Operator 或 Runtime restart 不會補回已刪除網域。
- Helm upgrade 修改 seed 只影響之後建立的 Workspace。
- 複製 Workspace 時複製來源當下的完整 firewall 設定。

```yaml
firewall:
  seed:
    workspace:
      egressMode: allowlist
      allowedDomains:
        - github.com
        - registry.npmjs.org
        - chatgpt.com
    browser:
      egressMode: allowlist
      allowedDomains:
        - google.com
```

## 網路語意

| 設定 | 語意 |
| --- | --- |
| `egressMode=blocked` | 阻擋外部網路，只保留平台必要流量 |
| `egressMode=allowlist` | 只允許 `allowedDomains` 中至少一個 exact hostname |
| `egressMode=unrestricted` | 允許所有外部網路 |

DNS、Manager、OIDC provider、PostgreSQL 與 TURN 等平台必要流量由 infrastructure policy 明確
管理，不顯示在 UI domain list，也不會被 seed 刪除操作誤移除。

`blocked` 與 `unrestricted` 的 `allowedDomains` 必須是空陣列；`allowlist` 則必須至少包含
一個網域。UI 直接顯示這三種模式，不使用「開啟／關閉防火牆」等雙重否定文字。

## 套用流程

1. UI 以目前 revision 更新完整 firewall desired state。
2. Manager 在同一 transaction 更新資料與 durable command。
3. Kubernetes worker 更新 Workspace CR 的完整 `spec.firewall`。
4. Operator 更新 Cilium policy。
5. observed revision 追上 desired revision 後標記 `applied`。

Firewall-only 更新不會修改 Runtime、Browser 或 Canvas Pod template，也不應造成 Pod
rollout。

## 驗收

建立測試 Workspace 後：

1. 從 Manager firewall API 確認 seed 已寫入。
2. 在 UI 刪除一個 seed domain並儲存。
3. 確認 API revision 增加且狀態由 `applying` 變成 `applied`。
4. 比較 Workspace CR 與 Cilium policy，確認網域已移除。
5. 確認三個 component Pod UID 未改變。
6. 重啟 Manager/Operator/Runtime及執行無關的 Helm upgrade，確認網域不會回填。

revision conflict 必須重新讀取最新狀態後再編輯；`error` 時依 error code 與 Operator log
處理，不要透過重建全部 Workspace 元件強迫套用。
