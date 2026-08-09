---
title: Automation Runner 復原
---

# Automation Runner 復原

本手冊用於處理 workspace Runtime 重複執行、Automation Runner 卡住或節點失聯。復原目標是先確認舊 Runtime 與殘留 Agent 已完全停止，再啟動唯一一個 replacement Runtime。

## 告警條件

值班人員收到下列任一訊號時必須介入：

- 同一個 workspace 同時存在兩個以上 Runtime。
- Automation execution 維持 `running` 超過 1830 秒。
- Runtime 所在節點失聯，無法確認 Runtime 與其 Agent process 已停止。

## 復原原則

1. 先暫停該 workspace 的排程觸發，避免新增 execution。
2. 記錄 workspace ID、execution ID、Runtime 名稱、節點與告警時間。
3. 節點失聯時，必須先在基礎設施層完成 fencing，確認失聯節點無法繼續執行 workload；在 fencing 完成前，不得 force-delete Pod 或啟動 replacement Runtime。
4. 發現雙 Runtime 或雙 Runner 時，先停止兩個 Runtime，並清除兩者遺留的 Agent process。
5. 確認舊 Runtime、Runner 與 Agent process 均不存在後，才啟動單一 Runtime。
6. 確認 Runtime `/health` 恢復成功，並確認同一 workspace 只有一個 Runtime 與一個 Runner。
7. 解除排程暫停，持續觀察至少一個 execution 週期。

## Kubernetes 操作

目前的 Workspace CR 沒有 suspend 欄位；刪除 Workspace CR 會觸發 finalizer 清理受管資源，因此不得用刪除 CR 暫停 reconcile。現行可執行方式是在維護窗內暫停 workspace-operator。這會暫停所有 Workspace CR 的 reconcile，必須先通知其他 workspace 的維運人員，且維護結束時務必恢復原 replica 數。

1. 設定本次操作變數，確認 operator 與目標 Runtime Deployment 都存在：

   ```bash
   export OPERATOR_NAMESPACE=<platform-namespace>
   export OPERATOR_INSTANCE=<helm-release-name>
   export OPERATOR_DEPLOYMENT=<helm-release-fullname>-workspace-operator
   export RUNTIME_NAMESPACE=<workspace-target-namespace>
   export WORKSPACE_ID=<workspace-id>
   export RUNTIME_DEPLOYMENT=workspace-runtime-${WORKSPACE_ID}

   kubectl -n "${OPERATOR_NAMESPACE}" get deployment "${OPERATOR_DEPLOYMENT}"
   kubectl -n "${RUNTIME_NAMESPACE}" get deployment "${RUNTIME_DEPLOYMENT}"
   ```

2. 若節點失聯，先依平台程序完成節點 fencing。未取得 fencing 完成證據前停止操作。
3. 記錄 workspace-operator 原 replica 數，將 operator scale 到 0，並確認 operator Pod 已完全停止。完成這一步後，operator 才不會把 Runtime 自動 reconcile 回 1：

   ```bash
   export OPERATOR_REPLICAS=$(kubectl -n "${OPERATOR_NAMESPACE}" get deployment "${OPERATOR_DEPLOYMENT}" -o jsonpath='{.spec.replicas}')
   test "${OPERATOR_REPLICAS}" -gt 0

   kubectl -n "${OPERATOR_NAMESPACE}" scale deployment/"${OPERATOR_DEPLOYMENT}" --replicas=0
   kubectl -n "${OPERATOR_NAMESPACE}" wait --for=delete pod -l app.kubernetes.io/component=workspace-operator,app.kubernetes.io/instance="${OPERATOR_INSTANCE}" --timeout=120s
   kubectl -n "${OPERATOR_NAMESPACE}" get pods -l app.kubernetes.io/component=workspace-operator,app.kubernetes.io/instance="${OPERATOR_INSTANCE}"
   ```

4. 在 operator 已停止的狀態下，將目標 Runtime scale 到 0，等待該 workspace 的所有 Runtime Pod 完全消失：

   ```bash
   kubectl -n "${RUNTIME_NAMESPACE}" scale deployment/"${RUNTIME_DEPLOYMENT}" --replicas=0
   kubectl -n "${RUNTIME_NAMESPACE}" wait --for=delete pod -l aileron.io/component=workspace-runtime,aileron.io/workspace-id="${WORKSPACE_ID}" --timeout=120s
   kubectl -n "${RUNTIME_NAMESPACE}" get pods -l aileron.io/component=workspace-runtime,aileron.io/workspace-id="${WORKSPACE_ID}"
   ```

5. 檢查原節點與外部執行環境，終止該 workspace 遺留的 Agent process；確認 Runtime、Runner 與 Agent 都不存在後才能繼續。
6. 在 operator 尚未恢復前，只啟動一個 Runtime，確認單一 Pod Ready 與 `/health` 正常：

   ```bash
   kubectl -n "${RUNTIME_NAMESPACE}" scale deployment/"${RUNTIME_DEPLOYMENT}" --replicas=1
   kubectl -n "${RUNTIME_NAMESPACE}" rollout status deployment/"${RUNTIME_DEPLOYMENT}" --timeout=300s
   kubectl -n "${RUNTIME_NAMESPACE}" get pods -l aileron.io/component=workspace-runtime,aileron.io/workspace-id="${WORKSPACE_ID}" -o wide
   ```

7. 恢復 workspace-operator 原 replica 數並等待可用，讓所有 Workspace CR 恢復 reconcile。若前述任何復原步驟失敗，也必須執行這個恢復動作後再離開維護窗：

   ```bash
   kubectl -n "${OPERATOR_NAMESPACE}" scale deployment/"${OPERATOR_DEPLOYMENT}" --replicas="${OPERATOR_REPLICAS}"
   kubectl -n "${OPERATOR_NAMESPACE}" rollout status deployment/"${OPERATOR_DEPLOYMENT}" --timeout=300s
   ```

8. 確認目標 Runtime 仍只有一個 Pod，再解除該 workspace 的排程暫停。

## Docker 操作

1. 列出該 workspace 的 Runtime container，記錄 container ID 與狀態。
2. 停止所有重複 Runtime，等待停止完成後重新 inspect，確認均非 `running`。
3. 移除已停止的 Runtime，並清除宿主機上該 workspace 遺留的 Agent process。
4. 只透過正常 provisioning 流程啟動一個 Runtime；不得手動保留第二個 Runtime。
5. 重新 inspect 並檢查 `/health`，確認只有單一 Runtime 正常執行。

## 復原完成條件

- 同一 workspace 只有一個 Runtime。
- 同一 execution 只有一個 Runner，且不存在殘留 Agent process。
- Runtime `/health` 回傳成功。
- 後續 execution 能正常離開 `queued` 與 `running`，且不再觸發 1830 秒告警。
