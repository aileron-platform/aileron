---
title: Kubernetes 儲存設計
description: Aileron 各類資料的 RWX、RWO、Delete、Retain 與 POSIX 契約
---

# Kubernetes 儲存設計

## Volume 矩陣

| 資料 | 掛載元件 | 掛載路徑 | 模式 | 回收 |
| --- | --- | --- | --- | --- |
| Workspace working tree | Runtime、Browser、Canvas | `/workspace` | RWX | Workspace 刪除時 Delete |
| Runtime HOME | 僅 Runtime | `/home/developer` | 預設 RWO，可選 RWX | Workspace 刪除時 Delete |
| Knowledge Base | Manager RW；Runtime attachment RO | `/host/knowledge-bases`、`/knowledge/<alias>` | RWX | Retain |
| Manager state | Manager、worker、beat | `/state` | RWO | Retain |
| PostgreSQL | PostgreSQL | image data path | RWO | Retain |
| Redis | Redis | image data path | RWO | Retain |

Browser 與 Canvas 不得掛載 Runtime HOME。Operator 為每個 Workspace 建立
`workspace-runtime-home-pvc-<workspace-id>`，直接掛載 `/home/developer`，保存 CLI
登入與設定、XDG data/state、Maven state、bootstrap journal 與一次性 agent defaults
marker；working tree 則保存使用者 repository 與檔案。

`/home/developer/.codex/tmp` 是唯一刻意覆蓋的暫存子路徑，使用 16 MiB memory
`emptyDir`。Codex 會自行建立並將 `tmp/arg0` 設成目前 Runtime UID 擁有的 `0700`
目錄；不得把 volume root 直接掛到 `tmp/arg0`，否則非 root Runtime 無法調整權限。
此路徑只放程序期 helper alias，不包含登入、設定或 session 等持久狀態。

Runtime HOME 只有一個 Runtime writer，且 Runtime Deployment 使用 Recreate 與 Pod UID
fencing，因此 `ReadWriteOnce` 是預設且最小權限的模式。需要共享 filesystem 的平台可將
`kubernetes.runtimeHome.accessMode` 設為 `ReadWriteMany`；Chart 只接受這兩種單一值。

## 跨平台映射原則

| 平台 | Workspace／Knowledge Base（RWX） | Runtime HOME／平台狀態（RWO 預設） |
| --- | --- | --- |
| EKS | EFS CSI | EBS CSI |
| GKE | Filestore multishare CSI | Persistent Disk CSI |
| AKS | Azure Files NFS CSI 自訂 StorageClass | Azure Disk CSI |
| OCP | CephFS | Ceph RBD |
| 原生 Kubernetes | NFS CSI、CephFS 或其他 POSIX RWX CSI | block CSI；測試環境才可使用 node-local CSI |

表中的後端只是能力映射，不是程式碼內的固定名稱。每個環境要以自己的 StorageClass
注入；SMB、固定 GID、NFS root squash 或 node-local volume 都不能被當成所有平台共有的
產品契約。

`helm/aileron/tests/values/platform-*.yaml` 只用來驗證 Helm 能否正確 render 各平台契約，
不是可直接部署的 provider profile，也不代表該平台已通過認證。GKE fixture 使用
GKE 提供的 `enterprise-multishare-rwx`；AKS fixture 中的
`azurefile-nfs-premiumv2-custom` 則代表管理者自行建立、明確設定 `protocol: nfs` 的
Azure Files StorageClass，不是 AKS 內建的 SMB class。原生 Kubernetes fixture 的
`csi-rwo` 也是能力占位名稱，部署時必須替換成叢集實際的 RWO CSI class。

平台細節以
[GKE Filestore multishare](https://cloud.google.com/kubernetes-engine/docs/concepts/multishares)
與
[AKS Azure Files NFS](https://learn.microsoft.com/azure/aks/create-volume-azure-files#use-nfs-protocol-with-azure-files)
等 provider 官方文件為準。

fixture render 成功只證明 value 能流入正確 PVC 與 workload。正式宣告 EKS、GKE、AKS、
OCP、RKE2 或原生 Kubernetes 可用之前，仍須在目標叢集以實際 CSI、CNI、admission 與
安全政策執行完整 conformance。

## NFS CSI 與 POSIX 契約

- 使用 NFS CSI StorageClass；不需要修改共用的 NFS subdirectory provisioner。
- export 保持 `root_squash`。
- NFS base root 的 group 必須等於 `kubernetes.platformStorageGid`。
- base root 建議 mode `2770`，保留 setgid，且不得 other-write。
- 應用程式以 non-root UID 與共用 fsGroup 寫入，不修改 volume root。
- Helm 宣告 fsGroup、StorageClass、access mode 與 reclaim intent。
- CSI/StorageClass 負責建立與回收 volume 或子目錄。
- NFS server/平台管理者負責 base root 的 GID、mode、setgid 與 export policy。

## Helm storage verification

`kubernetes.storageVerification.enabled=true` 時，Chart 使用可拋棄的 Delete StorageClass
執行安裝期檢查。這個 Job 只驗證，不建立平台 root，也不修復權限。失敗時應調整
StorageClass、NFS base root 或 `platformStorageGid`，不能在應用 workload 增加 root 權限。

Workspace RWX 與 Manager state RWO 的驗證容量分別由
`kubernetes.storageVerification.workspaceSize` 與
`kubernetes.storageVerification.managerStateSize` 控制，預設各為 `1Gi`。兩者接受正值
Kubernetes quantity，例如 `1Gi` 或 `100Gi`。雲端後端的最低容量可能不同，必須依實際
tier 分別覆寫；例如 AKS Azure Files NFS premium profile 可能需要比 Azure Disk 更大的
最小容量，不能用單一共同 size 推算。AKS render fixture 因此示範 RWX probe 使用
`100Gi`、RWO probe 使用 `1Gi`；部署時仍須依當下選用的 Azure Files tier 校正。

正式 provider profile 的兩個 `*StorageClassName` 都必須指向專供驗證、
`reclaimPolicy: Delete` 的 class，且不得與正式 Workspace 或 Manager state class 同名。
fixture 名稱以 `-delete` 結尾只是在 render 契約中明示用途；安裝前仍須由平台管理者建立
並檢查該 StorageClass 的真實 reclaim policy。測試環境設定不是雲端或正式原生 Kubernetes
profile 的設計基準。

## Workspace PVC 擴充

Workspace Project Data 與 Runtime HOME 使用各自的 dedicated PVC。若要允許 Platform Admin 擴容，對應 StorageClass 必須設定 `allowVolumeExpansion: true`。系統只允許增加 request；PVC status capacity 達到 requested bytes 前維持 `applying`，不會提早回報完成。Docker profile 不提供 per-workspace hard quota。
