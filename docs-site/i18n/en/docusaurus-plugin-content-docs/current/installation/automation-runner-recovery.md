---
title: Automation Runner Recovery
---

# Automation Runner Recovery

Use this runbook when a workspace Runtime is duplicated, an Automation Runner is stuck, or a node becomes unreachable. The recovery goal is to verify that the old Runtime and all remaining Agents have stopped completely before starting exactly one replacement Runtime.

## Alert Conditions

On-call staff must intervene when any of the following signals occurs:

- More than one Runtime exists for the same workspace.
- An Automation execution remains `running` for more than 1,830 seconds.
- The node hosting the Runtime is unreachable, so it is impossible to confirm that the Runtime and its Agent processes have stopped.

## Recovery Principles

1. Pause scheduled triggers for the workspace first to prevent new executions.
2. Record the workspace ID, execution ID, Runtime name, node, and alert time.
3. If a node is unreachable, complete infrastructure-level fencing first and verify that the unreachable node can no longer run workloads. Do not force-delete a Pod or start a replacement Runtime before fencing is complete.
4. If duplicate Runtimes or Runners are found, stop both Runtimes first and terminate any Agent processes left by either one.
5. Start one Runtime only after confirming that the old Runtime, Runner, and Agent processes no longer exist.
6. Confirm that the Runtime `/health` check succeeds and that the workspace has exactly one Runtime and one Runner.
7. Resume scheduled triggers and observe at least one execution cycle.

## Kubernetes Procedure

The current Workspace CR has no suspend field. Deleting a Workspace CR triggers its finalizer to clean up managed resources, so do not delete the CR to pause reconciliation. The current supported procedure is to pause the workspace-operator during a maintenance window. This pauses reconciliation for every Workspace CR. Notify the operators of other workspaces first, and always restore the original replica count when maintenance ends.

1. Set variables for this operation and confirm that both the operator and target Runtime Deployments exist:

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

2. If the node is unreachable, complete node fencing according to the platform procedure. Stop here until evidence confirms that fencing is complete.
3. Record the original workspace-operator replica count, scale the operator to 0, and confirm that all operator Pods have stopped. Only after this step will the operator stop automatically reconciling the Runtime back to one replica:

   ```bash
   export OPERATOR_REPLICAS=$(kubectl -n "${OPERATOR_NAMESPACE}" get deployment "${OPERATOR_DEPLOYMENT}" -o jsonpath='{.spec.replicas}')
   test "${OPERATOR_REPLICAS}" -gt 0

   kubectl -n "${OPERATOR_NAMESPACE}" scale deployment/"${OPERATOR_DEPLOYMENT}" --replicas=0
   kubectl -n "${OPERATOR_NAMESPACE}" wait --for=delete pod -l app.kubernetes.io/component=workspace-operator,app.kubernetes.io/instance="${OPERATOR_INSTANCE}" --timeout=120s
   kubectl -n "${OPERATOR_NAMESPACE}" get pods -l app.kubernetes.io/component=workspace-operator,app.kubernetes.io/instance="${OPERATOR_INSTANCE}"
   ```

4. With the operator stopped, scale the target Runtime to 0 and wait until every Runtime Pod for that workspace has disappeared:

   ```bash
   kubectl -n "${RUNTIME_NAMESPACE}" scale deployment/"${RUNTIME_DEPLOYMENT}" --replicas=0
   kubectl -n "${RUNTIME_NAMESPACE}" wait --for=delete pod -l aileron.io/component=workspace-runtime,aileron.io/workspace-id="${WORKSPACE_ID}" --timeout=120s
   kubectl -n "${RUNTIME_NAMESPACE}" get pods -l aileron.io/component=workspace-runtime,aileron.io/workspace-id="${WORKSPACE_ID}"
   ```

5. Inspect the original node and external execution environments. Terminate any remaining Agent processes for the workspace. Continue only after confirming that no Runtime, Runner, or Agent remains.
6. Before restoring the operator, start exactly one Runtime and confirm that a single Pod is Ready and `/health` succeeds:

   ```bash
   kubectl -n "${RUNTIME_NAMESPACE}" scale deployment/"${RUNTIME_DEPLOYMENT}" --replicas=1
   kubectl -n "${RUNTIME_NAMESPACE}" rollout status deployment/"${RUNTIME_DEPLOYMENT}" --timeout=300s
   kubectl -n "${RUNTIME_NAMESPACE}" get pods -l aileron.io/component=workspace-runtime,aileron.io/workspace-id="${WORKSPACE_ID}" -o wide
   ```

7. Restore the workspace-operator's original replica count and wait until it is available so every Workspace CR resumes reconciliation. If any earlier recovery step fails, you must still perform this restoration before leaving the maintenance window:

   ```bash
   kubectl -n "${OPERATOR_NAMESPACE}" scale deployment/"${OPERATOR_DEPLOYMENT}" --replicas="${OPERATOR_REPLICAS}"
   kubectl -n "${OPERATOR_NAMESPACE}" rollout status deployment/"${OPERATOR_DEPLOYMENT}" --timeout=300s
   ```

8. Confirm that the target Runtime still has exactly one Pod, then resume scheduled triggers for the workspace.

## Docker Procedure

1. List the Runtime containers for the workspace and record their container IDs and states.
2. Stop every duplicate Runtime. After they stop, inspect them again and confirm that none is `running`.
3. Remove the stopped Runtimes and terminate any Agent processes left for that workspace on the host.
4. Start exactly one Runtime through the normal provisioning flow. Do not manually retain a second Runtime.
5. Inspect the workspace again and check `/health` to confirm that only one Runtime is running normally.

## Recovery Completion Criteria

- The workspace has exactly one Runtime.
- The execution has exactly one Runner, with no remaining Agent process.
- Runtime `/health` succeeds.
- Subsequent executions leave both `queued` and `running` normally and no longer trigger the 1,830-second alert.
