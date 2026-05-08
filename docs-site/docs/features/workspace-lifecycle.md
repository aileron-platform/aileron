---
sidebar_position: 1
title: Workspace 生命週期
---

# Workspace 生命週期管理

## 生命週期狀態

```
          ┌──────────┐
          │ creating │  ← POST /workspaces
          └────┬─────┘
               │
          ┌────▼─────┐
          │ running  │  ← 容器/Pod 就緒
          └────┬─────┘
               │
     ┌─────────┼─────────┐
     │         │         │
┌────▼──┐ ┌───▼────┐ ┌──▼──────┐
│stopped│ │restarting│ │deleting│
└───────┘ └────────┘ └─────────┘
```

## Provisioner 支援

| Provisioner | 說明 |
|-------------|------|
| `docker` | 使用 Docker 建立容器（本地開發預設） |
| `kubernetes` | 使用 Kubernetes 建立 Pod 與相關資源 |
| `podman` | 使用 Podman 建立容器 |

每個 workspace 建立時可選擇使用哪個 provisioner。

## 建立 Workspace

透過前端介面或直接呼叫 API：

```bash
curl -X POST http://localhost:3001/api/v1/workspaces \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-workspace",
    "provisioner": "docker"
  }'
```

## 容器組成

每個 workspace 包含以下容器/服務：

| 服務 | 說明 |
|------|------|
| `workspace-runtime` | 主要執行環境（FastAPI + Claude Code） |
| `workspace-terminal` | 瀏覽器終端機 |
| `workspace-chrome` | Headless Chrome（browser preview） |
| `workspace-nextjs`（可選） | Next.js dev server |

## 防火牆設定

每個 workspace 可設定：

| 設定項 | 說明 |
|--------|------|
| `workspace_firewall_network_access_enabled` | 是否啟用 workspace 網路存取 |
| `workspace_firewall_domain_access_mode` | Domain 存取模式（allowlist / deny） |
| `workspace_firewall_allowed_domains` | Workspace 允許存取的 domain 清單 |
| `browser_firewall_network_access_enabled` | 是否啟用 browser 網路存取 |
| `browser_firewall_domain_access_mode` | Browser domain 存取模式 |
| `browser_firewall_allowed_domains` | Browser 允許存取的 domain 清單 |

:::note
Kubernetes 模式下，防火牆政策由 Cilium NetworkPolicy 實作。系統預設的 allowedDomains 與 workspace 自訂設定在 reconcile 階段合併，產生最終有效政策。
:::

## 生命週期操作

### 停止 Workspace

停止 workspace 容器，資料保留。

### 啟動（重啟）Workspace

重新啟動已停止的 workspace。

### 刪除 Workspace

刪除 workspace 及所有相關資源。Docker 模式與 Kubernetes 模式皆可從前端 UI 一致操作。

### 重啟個別服務

可針對以下服務單獨重啟：
- `runtime`
- `browser`
- `nextjs`

## Kubernetes Workspace 資源

Kubernetes 模式下，workspace-operator 會為每個 workspace reconcile 以下資源：

- Runtime Pod / Deployment
- Browser Pod / Deployment
- Next.js Pod / Deployment（可選）
- Services
- PersistentVolumeClaim（PVC）
- Cilium NetworkPolicy（防火牆）
- `Workspace` Custom Resource（CR）
