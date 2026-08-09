---
title: Open Source Acknowledgements
---

# Open Source Acknowledgements

Aileron stands on the shoulders of many excellent open source projects. This page lists the third-party software actually used by Aileron and credits their upstream maintainers. Entries are grouped by **the role they play inside Aileron**, with links to the upstream project and license.

> If something is missing, please open an issue — we'll add it.

## 🤖 AI Agents & Browser Automation

| Project | Role | License |
|---------|------|---------|
| [Claude Code CLI](https://docs.claude.com/en/docs/claude-code/overview) | Built-in agent CLI in the workspace | Anthropic TOS |
| [OpenAI Codex CLI](https://github.com/openai/codex) | Built-in agent CLI in the workspace | Apache-2.0 |
| [OpenCode](https://github.com/sst/opencode) | Built-in agent CLI in the workspace | MIT |
| [Terragon OSS](https://github.com/terragon-labs/terragon-oss) | Open source reference project for multi-agent cloud coding orchestration and workspace UX | Apache-2.0 |
| [`claude-agent-sdk` (Python)](https://github.com/anthropics/claude-agent-sdk-python) | Python SDK used by workspace-runtime | MIT |
| [`agent-client-protocol`](https://pypi.org/project/agent-client-protocol/) | Protocol and Python client between workspace-runtime and the OpenCode ACP subprocess | MIT |
| [Playwright CLI](https://github.com/microsoft/playwright) | Browser automation tool that connects to workspace-browser over CDP | Apache-2.0 |

## 🌐 Remote Browser / WebRTC

| Project | Role | License |
|---------|------|---------|
| [m1k1o/neko](https://github.com/m1k1o/neko) | WebRTC browser streaming container powering workspace-chrome (`ghcr.io/m1k1o/neko/chromium`) | Apache-2.0 |
| [Chromium](https://www.chromium.org/) | The actual browser controlled inside neko, exposed to agents via DevTools Protocol | BSD-3-Clause |
| [Chrome DevTools Protocol (CDP)](https://chromedevtools.github.io/devtools-protocol/) | Control channel: Playwright CLI ↔ `cdp-proxy` ↔ Chromium | — |
| [WXT](https://wxt.dev/) | Build toolchain for the Chrome Extension (MV3) | MIT |

## ⚙️ Orchestrator / Backend (Python)

FastAPI services behind workspace-manager and workspace-runtime.

| Project | Role | License |
|---------|------|---------|
| [FastAPI](https://fastapi.tiangolo.com/) | Web framework | MIT |
| [Uvicorn](https://www.uvicorn.org/) | ASGI server | BSD-3-Clause |
| [Pydantic](https://docs.pydantic.dev/) | Data validation & settings | MIT |
| [SQLAlchemy](https://www.sqlalchemy.org/) | ORM | MIT |
| [Alembic](https://alembic.sqlalchemy.org/) | DB migrations | MIT |
| [asyncpg](https://github.com/MagicStack/asyncpg) / [psycopg2](https://www.psycopg.org/) | PostgreSQL drivers | Apache-2.0 / LGPL |
| [Redis-py](https://github.com/redis/redis-py) | Redis client (cache, pub/sub) | MIT |
| [Celery](https://docs.celeryq.dev/) + [Flower](https://github.com/mher/flower) + [Kombu](https://github.com/celery/kombu) | Durable Workspace Runtime jobs and periodic Knowledge Base maintenance | BSD-3-Clause |
| [croniter](https://github.com/kiorky/croniter) | Cron expression parsing | MIT |
| [Docker SDK for Python](https://github.com/docker/docker-py) | Workspace provisioner in Docker mode | Apache-2.0 |
| [Kubernetes Python Client](https://github.com/kubernetes-client/python) | Workspace provisioner in K8s mode | Apache-2.0 |
| [python-jose](https://github.com/mpdavis/python-jose) / [PyJWT](https://github.com/jpadilla/pyjwt) | JWT verification | MIT |
| [GitPython](https://github.com/gitpython-developers/GitPython) | Git operations | BSD-3-Clause |
| [pexpect](https://github.com/pexpect/pexpect) | Terminal interaction | ISC |
| [Supervisor](http://supervisord.org/) | In-container process manager | BSD-derived |
| [Jinja2](https://palletsprojects.com/p/jinja/) | Templating | BSD-3-Clause |
| [httpx](https://www.python-httpx.org/) / [aiohttp](https://docs.aiohttp.org/) | HTTP clients | BSD-3-Clause / Apache-2.0 |

## 🖥️ Frontend (React)

| Project | Role | License |
|---------|------|---------|
| [React 19](https://react.dev/) | UI framework | MIT |
| [Vite](https://vitejs.dev/) | Build tool & dev server | MIT |
| [TypeScript](https://www.typescriptlang.org/) | Type system | Apache-2.0 |
| [TanStack Query](https://tanstack.com/query) | Server-state management | MIT |
| [Radix UI](https://www.radix-ui.com/) | Unstyled component primitives (Dialog, Menu, Tabs, ...) | MIT |
| [shadcn/ui](https://ui.shadcn.com/) | Component styling system on top of Radix + Tailwind | MIT |
| [Tailwind CSS](https://tailwindcss.com/) | Utility-first CSS | MIT |
| [Monaco Editor](https://microsoft.github.io/monaco-editor/) | Code editor (file explorer / diff views) | MIT |
| [xterm.js](https://xtermjs.org/) | In-browser terminal rendering | MIT |
| [Framer Motion](https://www.framer.com/motion/) | Animations | MIT |
| [Mermaid](https://mermaid.js.org/) | Flow/architecture diagrams | MIT |
| [socket.io-client](https://socket.io/) | Realtime bidirectional messaging | MIT |
| [lucide-react](https://lucide.dev/) | Icon set | ISC |
| [i18next](https://www.i18next.com/) / [react-i18next](https://react.i18next.com/) | i18n | MIT |
| [Zod](https://zod.dev/) | Schema validation | MIT |
| [react-hook-form](https://react-hook-form.com/) | Forms | MIT |
| [react-markdown](https://github.com/remarkjs/react-markdown) + [remark-gfm](https://github.com/remarkjs/remark-gfm) | Markdown rendering (chat panel) | MIT |
| [Recharts](https://recharts.org/) | Charts | MIT |

## 🐹 workspace-terminal (Go)

| Project | Role | License |
|---------|------|---------|
| [Gin](https://gin-gonic.com/) | HTTP framework | MIT |
| [gorilla/websocket](https://github.com/gorilla/websocket) | WebSocket | BSD-2-Clause |
| [creack/pty](https://github.com/creack/pty) | PTY support | MIT |
| [go-redis](https://github.com/redis/go-redis) | Redis client | BSD-2-Clause |
| [Zap](https://github.com/uber-go/zap) | Structured logger | MIT |

## ☸️ workspace-operator (Go)

| Project | Role | License |
|---------|------|---------|
| [controller-runtime](https://github.com/kubernetes-sigs/controller-runtime) | Kubebuilder-style operator SDK | Apache-2.0 |
| [client-go](https://github.com/kubernetes/client-go) | K8s API client | Apache-2.0 |
| [apimachinery](https://github.com/kubernetes/apimachinery) | CRD schema definitions | Apache-2.0 |

## 🧱 Infrastructure & Platform

| Project | Role | License |
|---------|------|---------|
| [PostgreSQL](https://www.postgresql.org/) | Primary database | PostgreSQL License |
| [Redis](https://redis.io/) | Cache, pub/sub, Celery broker | BSD-3-Clause (≤ 7.2) |
| [Docker](https://www.docker.com/) / [Docker Compose](https://docs.docker.com/compose/) | Local deployment runtime | Apache-2.0 |
| [Kubernetes](https://kubernetes.io/) | Production runtime | Apache-2.0 |
| [Helm](https://helm.sh/) | K8s package management | Apache-2.0 |
| [Cilium](https://cilium.io/) | Network policy for workspace and browser allowlists in Kubernetes mode | Apache-2.0 |
| [drawio (jgraph/drawio)](https://github.com/jgraph/drawio) | Bundled diagramming service container | Apache-2.0 |
| [mise](https://mise.jdx.dev/) | Multi-version toolchain manager inside workspace-runtime | MIT |

## 📚 Documentation Site (this site)

| Project | Role | License |
|---------|------|---------|
| [Docusaurus](https://docusaurus.io/) | Docs site generator (v3) | MIT |
| [MDX](https://mdxjs.com/) | Markdown + JSX | MIT |
| [Prism](https://prismjs.com/) | Code syntax highlighting | MIT |

---

Thanks to every upstream maintainer. If you are the author of one of these projects and spot an incorrect license label, please open an issue or PR.
