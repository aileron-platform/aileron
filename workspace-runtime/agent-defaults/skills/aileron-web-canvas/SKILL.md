---
name: aileron-web-canvas
description: Build static HTML or Next.js web pages for Aileron Web Canvas preview using /workspace/.aileron/canvas.json and the Aileron MCP artifact tools. Use when creating or modifying agent-generated pages, prototypes, dashboards, decks, or visual web artifacts that must appear in the Aileron Canvas tab.
license: MIT
metadata:
  author: aileron
  version: "1.0"
---

# Aileron Web Canvas

Use this skill when the user asks to create, regenerate, or modify a website, page, static HTML canvas, Next.js app, prototype, dashboard, slide-like page, or visual web artifact for Aileron Web Canvas preview.

## Core Contract

- Work under `/workspace`.
- Do not start package managers or dev servers.
- Do not hand-roll a different preview mechanism: never tell the user to run a
  dev server, share a raw file path, or paste HTML into the chat.
- Canvas is declared only by `/workspace/.aileron/canvas.json`.
- Ask structured questions with `mcp__aileron__ask_user_question`.
- Announce completed canvas artifacts with `mcp__aileron__show_canvas_artifact`.
- Put generated canvas content under `/workspace/.aileron/canvases/aileron-web-canvas/<slug>/`.
- Do not put active canvas content under `/workspace/canvases/...`; relative manifest paths resolve from `/workspace/.aileron/`.
- Set manifest `owner.skillName` to `aileron-web-canvas`.

## Discovery

For a new canvas request whose brief leaves decisions that materially change the
artifact, make the first response one short prose line followed immediately by
`mcp__aileron__ask_user_question`, then end the turn. Before that form call, do
not read files, run Bash, or write files.

Ask no more than five questions. A question earns its place only when its answer
changes what you would build for this brief. Set each question's `default` to
your best inference from the brief so the user confirms rather than fills; omit
`default` only when there is no reasonable basis to infer an answer.

Use `option-cards` or `color` only when visual direction is genuinely undecided. Skip questions already answered by the user.

If the user's brief is already specific enough to build without a
decision-changing answer, skip the form and start the workflow directly.

## Static Canvas

Use static canvas for HTML, CSS, JavaScript, media, diagrams, decks, and prototypes that do not need Next.js.

Expected structure:

```text
/workspace/.aileron/
├── canvas.json
└── canvases/aileron-web-canvas/<slug>/
    ├── index.html
    ├── app.js
    ├── styles.css
    └── assets/
```

Manifest:

```json
{
  "version": 1,
  "kind": "static",
  "contentDir": "./canvases/aileron-web-canvas/<slug>",
  "title": "<user-facing title>",
  "owner": { "skillName": "aileron-web-canvas" },
  "routes": [
    { "path": "/", "label": "Home" }
  ],
  "defaultPath": "/"
}
```

Before activating the manifest, verify `contentDir` resolves to the content directory and `contentDir/index.html` exists.

## Next.js Canvas

Use Next.js only when the artifact needs App Router, React component structure, HMR, or richer app behavior.

Expected structure:

```text
/workspace/.aileron/
├── canvas.json
└── canvases/aileron-web-canvas/<slug>/
    ├── package.json
    ├── app/
    │   ├── layout.tsx
    │   └── page.tsx
    ├── components/
    ├── public/
    ├── next.config.js
    ├── postcss.config.mjs
    ├── tailwind.config.ts
    └── tsconfig.json
```

`package.json` must include `next`.

`next.config.js` 必須啟用 standalone 輸出，讓同一份 Canvas 可以由
`aileron-canvas-publish` 建置成不可變映像：

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
};

module.exports = nextConfig;
```

Use the Canvas standard dependency set unless the user explicitly needs extra packages:

```json
{
  "dependencies": {
    "next": "15.5.15",
    "react": "19.2.5",
    "react-dom": "19.2.5"
  },
  "devDependencies": {
    "@types/node": "22.19.17",
    "@types/react": "19.2.14",
    "@types/react-dom": "19.2.3",
    "autoprefixer": "10.5.0",
    "postcss": "8.5.10",
    "tailwindcss": "3.4.19",
    "typescript": "5.9.3"
  }
}
```

Do not invent newer dependency versions. The Canvas renderer links this exact standard set without running a full custom install.

Manifest:

```json
{
  "version": 1,
  "kind": "nextjs",
  "contentDir": "./canvases/aileron-web-canvas/<slug>",
  "title": "<user-facing title>",
  "owner": { "skillName": "aileron-web-canvas" },
  "routes": [
    { "path": "/", "label": "Home" }
  ],
  "defaultPath": "/"
}
```

## Activation

Write content files first. Write `/workspace/.aileron/canvas.json` last using valid JSON. Keep `defaultPath` equal to one route path.

After files are ready, call:

```text
mcp__aileron__show_canvas_artifact
```

Recommended arguments:

```json
{
  "title": "<user-facing title>",
  "route": "/"
}
```

Do not add assistant prose after the tool call unless the host continues the turn after a non-pausing tool call and the user explicitly needs a brief summary.

## Quality Bar

- Build the actual usable experience as the first screen.
- Use responsive layout and stable dimensions.
- Avoid placeholder filler, decorative blobs, and one-note palettes.
- Text must not overlap or overflow at mobile and desktop sizes.
- Use meaningful visual assets when the user needs to inspect a product, place, object, person, or concrete state.
- Keep comments and code identifiers in English.
