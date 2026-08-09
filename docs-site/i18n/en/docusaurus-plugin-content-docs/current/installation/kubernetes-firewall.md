---
title: Kubernetes Workspace Firewall
description: Creation-time seeds, domains removable in the UI, and Cilium apply status
---

# Kubernetes Workspace Firewall

## Single Source of Truth

When a new Workspace is created, Manager writes Helm `firewall.seed` into the database. After creation, the Workspace firewall desired state stored in the database is the single source of truth.

- A seed is an initial value, not a permanent rule.
- Users can add or remove any seeded domain in the UI.
- Restarting Manager, Operator, or Runtime does not restore removed domains.
- Changes to the seed in a Helm upgrade affect only Workspaces created afterward.
- Copying a Workspace copies its complete firewall configuration at that moment.

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

## Network Semantics

| Setting | Meaning |
| --- | --- |
| `egressMode=blocked` | Block external network traffic while retaining required platform traffic |
| `egressMode=allowlist` | Allow at least one exact hostname from `allowedDomains` |
| `egressMode=unrestricted` | Allow all external network traffic |

Infrastructure policies explicitly manage required platform traffic such as DNS, Manager, the OIDC provider, PostgreSQL, and TURN. This traffic does not appear in the UI domain list and cannot be removed accidentally by deleting seeds.

`blocked` and `unrestricted` require an empty `allowedDomains` array. `allowlist`
requires at least one domain. The UI exposes these three modes directly instead
of using double-negative firewall enablement controls.

## Apply Flow

1. The UI updates the complete firewall desired state using the current revision.
2. Manager updates the data and durable command in the same transaction.
3. The Kubernetes worker updates the complete `spec.firewall` on the Workspace CR.
4. Operator updates the Cilium policy.
5. The state becomes `applied` after the observed revision catches up with the desired revision.

A firewall-only update does not modify the Runtime, Browser, or Canvas Pod template and must not cause a Pod rollout.

## Acceptance Checks

After creating a test Workspace:

1. Confirm through the Manager firewall API that the seed was stored.
2. Remove a seeded domain in the UI and save.
3. Confirm that the API revision increases and the status changes from `applying` to `applied`.
4. Compare the Workspace CR and Cilium policy to confirm that the domain was removed.
5. Confirm that the UIDs of all three component Pods are unchanged.
6. Restart Manager, Operator, and Runtime, then run an unrelated Helm upgrade and confirm that the domain is not restored.

If a revision conflict occurs, read the latest state before editing again. For an `error` state, diagnose the error code and Operator logs; do not force application by rebuilding every Workspace component.
