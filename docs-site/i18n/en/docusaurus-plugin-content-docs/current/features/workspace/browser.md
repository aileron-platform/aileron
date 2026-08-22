---
title: Browser
---

# Browser

## Purpose and Entry Point

Enter Browser from Workspace navigation to start or attach a browser automation session.

## Roles and Allowed Operations

Requires `workspace.browser_automation.use`; without it no provisioning or connection starts.

## Core Concepts

The Browser view, Neko WebSocket/WebRTC session, access credential generation, and extension pairing
have separate lifecycles. Leaving the Browser feature closes the current Neko client completely.
Entering it again must call `POST /api/v1/workspaces/{workspace_id}/browser/access`. The client, timer,
and credential belong only to that visibility period.

Kubernetes deployments also expose TURN path state as `browserConnectivity`:

| State | Admission | Meaning |
| --- | --- | --- |
| `pending` | `denied` | Browser or probes have not completed observation |
| `ready` | `allowed` | Backend and every required frontend vantage have matching, unexpired relay evidence |
| `degraded` | `allowed` | Backend is successful; a frontend latest attempt failed while its same-producer, same-revision last success is still fresh |
| `not_ready` | `denied` | Required evidence is missing, expired, revision-mismatched, or the data path failed |
| `unavailable` | `denied` | The profile, probe, or evidence service cannot provide authoritative evidence |

## Primary Workflow

Manager consumes only `browserConnectivity.admission`. `ready`, or `degraded` with still-valid evidence
and an `allowed` projection, can issue new Browser access. Manager does not reinterpret state or expiry;
the projection writer changes an expired projection to `not_ready` / `denied`. A `denied` projection in
`pending` or `not_ready`, including expiry at admission time, returns
`409 BROWSER_CONNECTIVITY_NOT_READY`. Only `unavailable` returns
`503 BROWSER_CONNECTIVITY_UNAVAILABLE`. The Browser view displays the projected
state directly and does not recalculate evidence freshness. It creates one Neko generation from that access.
If WebSocket, ICE, WebRTC, or the data channel fails, it closes the whole generation, requests fresh
access, and then creates the next one.
Every access under a `turnRest` profile contains fresh short-lived `iceServers`. That generation's
`RTCPeerConnection` overrides the Neko startup ICE list, and credentials are never reused across
generations.
A Browser session is ready only after the Neko WebSocket and WebRTC connection are established, a video
track in the `live` state has arrived, and the data channel is open. A close, cleanup, or video-track
`ended` event immediately clears the corresponding readiness. Reaching the page or Workspace URL alone
does not prove that Browser is usable.

The Evidence Authority stamps `acceptedAt` and derives `expiresAt` from its own clock. Producer
`measuredAt` is diagnostic only. Latest attempt and last success are retained per producer and exact
profile/credential revision; a projection never falls back across revisions or to an older projection.

Only one recovery request can run at a time. Automatic recovery allows at most five attempts within a
two-minute budget, uses jittered exponential backoff capped at 30 seconds, pauses while offline, and
resumes after the `online` event. The user-triggered retry is shown only after the budget is exhausted;
there is no unbounded background reconnect loop.

## View States and Read-only Behavior

The view handles preparing, connecting, connected, recovering, retry-exhausted, and denied states
separately. Every message uses a `workspace.browser.*` i18n key. With read-only operations, readable
content and normal mutation controls remain visible while mutations are disabled with an i18n reason.
Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

`browserConnectivity` gates admission of new sessions; it does not terminate an established and still
healthy WebRTC session. Pairing tokens are short-lived and workspace-scoped. Browser access, TURN
credentials, agent tokens, and Gateway nonces never enter URLs, logs, CR status, or documentation examples.

## Source Basis

- `frontend/src/features/workspace/features/browser/`
- `frontend/src/features/workspace/features/browser/hooks/useBrowserAccessRecovery.ts`
- `workspace-manager/app/modules/workspace/browser_credential_access.py`
- `workspace-runtime/app/modules/client_browser_relay/`
- `workspace-operator/internal/controller/browser_connectivity.go`
- `workspace-operator/internal/controller/connectivity_evidence_gateway.go`

## Related Architecture and APIs

- [execution-plane](/architecture/overview/execution-plane)
- [manager-api](/api/manager-api)
- [runtime-api](/api/runtime-api)
