---
name: web-canvas-nextjs-builder
description: Build HTML or Next.js 15 App Router websites directly in /workspace for Aileron Web Canvas preview. Use when creating or modifying agent-generated web pages, static HTML canvases, or Next.js sites that must sync into Web Canvas instead of starting package managers or dev servers.
license: MIT
metadata:
  author: aileron
  version: "1.0"
---

# Web Canvas Next.js Builder

Use this skill when the user asks to create, regenerate, or modify a website, web page, static HTML canvas, or Next.js application for Web Canvas preview.

## Core Rules

- Work directly in `/workspace`.
- Keep all project files at the project root.
- Do not scaffold frameworks into subdirectories.
- Do not create nested app folders such as `my-app/`, `new-app/`, or `next-app/`.
- Do not run package managers.
- Do not start dev servers.
- Do not override ports.
- Rely on the managed Web Canvas preview service.
- The platform installs dependencies and manages the preview renderer.
- When sharing a preview URL, read the actual `NEXT_PUBLIC_APP_URL` from `.env`, `.env.local`, or project metadata. Do not assume a default port.
- Prefer giving the user the live preview link that is actually running.
- After file changes, use the platform Web Canvas sync/reset flow when available so `/workspace` is copied into the isolated `/web-canvas` snapshot.

## Web Canvas Runtime Contract

Web Canvas renders from an isolated snapshot:

```text
/workspace  --sync-->  /web-canvas  --renderer-->  preview
```

The renderer never runs directly from `/workspace`.

Canvas detection order:

1. Valid `/workspace/route.json` chooses `route.json.type`.
2. Invalid `/workspace/route.json` is a manifest error.
3. Missing manifest plus `package.json` with `next` becomes `nextjs`.
4. Missing manifest plus HTML files becomes `html`.
5. Otherwise Web Canvas shows the default canvas.

Supported renderer types:

- `html`
- `nextjs`

## Next.js Defaults

When building a Next.js site:

- Use Next.js 15 App Router.
- Use TypeScript.
- Use Tailwind CSS.
- Write clean, production-ready code.
- Use `app/` routes.
- Use `app/layout.tsx`, `app/page.tsx`, and route folders as needed.
- Keep config files in `/workspace` root.
- Do not run `create-next-app` into a child directory.
- Do not run `npm install`, `pnpm install`, `yarn install`, `npm run dev`, `pnpm dev`, `yarn dev`, or `next dev`.
- Prefer the Canvas standard dependency set unless the user explicitly needs extra packages.
- Extra packages move the project onto the Canvas extended dependency path and may require a runtime package install.

Use these exact versions for the Canvas standard dependency set:

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

Expected root-level files may include:

```text
package.json
next.config.ts
tsconfig.json
postcss.config.mjs
tailwind.config.ts
app/
components/
lib/
public/
route.json
```

Example `route.json` for Next.js:

```json
{
  "version": 1,
  "type": "nextjs",
  "defaultPath": "/",
  "routes": [
    { "path": "/", "title": "Home" },
    { "path": "/dashboard", "title": "Dashboard" }
  ]
}
```

## HTML Canvas Defaults

When building static HTML:

- Put HTML, CSS, JS, and assets directly under `/workspace` or clear root-level folders.
- Use `route.json` for multi-page route mapping.
- Keep route files stable and explicit.
- Prefer explicit route mappings over relying on file scanning when there is more than one page.

Example `route.json` for HTML:

```json
{
  "version": 1,
  "type": "html",
  "defaultPath": "/",
  "routes": [
    { "path": "/", "file": "index.html", "title": "Home" },
    { "path": "/about", "file": "about.html", "title": "About" }
  ]
}
```

## i18n Requirement

For frontend text inside generated apps:

- Do not hard-code Chinese or English UI strings directly in components.
- Put display text behind i18n dictionaries, translation helpers, or local message maps.
- Keep route titles, labels, buttons, empty states, validation messages, and errors translatable.
- If the app is simple, create a small local i18n helper rather than scattering strings through JSX.
- When modifying an existing app, follow its existing i18n structure and key naming.

## Preview Workflow

After implementation:

1. Ensure files are in `/workspace`.
2. Ensure `route.json` is valid when present.
3. Let Web Canvas sync the workspace into `/web-canvas`.
4. Check the running preview URL from `NEXT_PUBLIC_APP_URL`.
5. Report the actual live preview link if available.

Do not tell the user to run package-manager commands, start a server, or open a guessed localhost port.
