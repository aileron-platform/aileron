---
name: aileron-playwright-cli-connect
description: "How to connect playwright-cli to the workspace-browser container via CDP (Chrome DevTools Protocol). Use this skill whenever you need to establish a browser connection before running Playwright CLI browser commands, including when the user mentions CDP, workspace-browser, browser automation setup, cdp-proxy, connecting to a remote Chromium instance, or when a browser command fails because no connection exists."
---

# Connecting playwright-cli to workspace-browser

This skill covers establishing a CDP connection between `playwright-cli` and the Chromium browser in `workspace-browser`.

## How to Connect

The browser service name is platform-owned. Read the canonical injected values instead of deriving it.

```bash
playwright-cli attach --cdp="$AILERON_BROWSER_CDP_URL"
```

Use the required canonical CDP URL directly:

```bash
playwright-cli attach --cdp="$AILERON_BROWSER_CDP_URL"
```

## Verify Reachability

Before connecting, you can confirm the CDP endpoint is reachable:

```bash
curl -s "$AILERON_BROWSER_CDP_URL/json/version"
```

## Environment Variables

- `AILERON_BROWSER_CDP_URL`: Required. Full internal CDP URL injected by the platform.

## Troubleshooting

1. Check `AILERON_BROWSER_CDP_URL`.
2. Confirm `workspace-browser` is running and healthy.
3. Confirm port `9223` is reachable from `workspace-runtime`.
4. Retry the `attach --cdp` command with `AILERON_BROWSER_CDP_URL`.
