# Aileron Frontend

This is the standalone frontend application for Aileron. It includes Docker support and runs on port `8082`.

## Structure

```text
frontend/
├── app/
├── features/
├── hubs/
├── pages/
├── shared/
├── src/
├── Dockerfile
├── Dockerfile.dev
├── docker-compose.yml
├── package.json
├── vite.config.ts
└── README.md
```

## Quick Start

### Docker

```bash
docker build -f Dockerfile.dev -t aileron:dev .
docker run -d -p 8082:8082 --name aileron-container aileron:dev
```

Open `http://localhost:8082`.

### Docker Compose

```bash
docker compose up -d
docker compose down
```

### Local Development

```bash
npm install
npm run dev
```

Open `http://localhost:8082`.

## Available Scripts

- `npm run dev`: start the dev server on port `8082`
- `npm run build`: build the production bundle
- `npm run preview`: preview the production bundle
- `npm run lint`: run lint checks
- `npm run test`: run tests

## Container Operations

```bash
docker ps
docker logs aileron-container
docker stop aileron-container
docker rm aileron-container
docker rmi aileron:dev
```

## Production Image

```bash
docker build -t aileron:prod .
docker run -d -p 8082:8082 --name aileron-prod aileron:prod
```

## Stack

- React
- TypeScript
- Vite
- Tailwind CSS
- Radix UI
- Docker

## ACP Widget Support

The frontend includes ACP-specific widgets and tool-decision flows for Codex, Gemini, and OpenCode.

Highlights:

- render decision UI from `tool-decision` payloads, including `options` and `tool_call`
- support common tool mappings such as read, write, and terminal
- show `tool:error` states with `error_message`

If you need to extend tool mappings, update `ACP_TOOL_WIDGET_MAP` and `resolveAcpToolWidgetType` in `frontend/src/features/workspace/components/ChatPanel/agentSessionTypes.ts`.

## Ports

- development: `8082`
- production: `8082`

## Notes

- this app is maintained as a standalone frontend
- path aliases are configured relative to this directory
- full TypeScript and Tailwind CSS support is included
- hot reload is supported in development
