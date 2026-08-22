---
title: 開源軟體致謝
---

# 開源軟體致謝

Aileron 由眾多優秀的開源專案堆疊而成，在此列出專案中實際使用到的開源軟體並致上謝意。
以下清單依照「在 Aileron 內扮演的角色」分組，對照每個軟體的**上游專案**與**授權條款**。

> 若有遺漏請協助回報 issue，我們會盡快補上。

## 🤖 AI Agent 與瀏覽器自動化

| 專案 | 用途 | 授權 |
|------|------|------|
| [Claude Code CLI](https://docs.claude.com/en/docs/claude-code/overview) | workspace 內建 Agent CLI | Anthropic TOS |
| [OpenAI Codex CLI](https://github.com/openai/codex) | workspace 內建 Agent CLI | Apache-2.0 |
| [OpenCode](https://github.com/sst/opencode) | workspace 內建 Agent CLI | MIT |
| [Terragon OSS](https://github.com/terragon-labs/terragon-oss) | 多 Agent cloud coding orchestrator 與 workspace UX 的開源參考專案 | Apache-2.0 |
| [`claude-agent-sdk` (Python)](https://github.com/anthropics/claude-agent-sdk-python) | workspace-runtime 串接 Claude Agent 的 Python SDK | MIT |
| [`agent-client-protocol`](https://pypi.org/project/agent-client-protocol/) | workspace-runtime 與 OpenCode ACP 子行程之間的通訊協定與 Python client | MIT |
| [Playwright CLI](https://github.com/microsoft/playwright) | 透過 CDP 連線 workspace-browser 的瀏覽器自動化工具 | Apache-2.0 |

## 🌐 Remote Browser / WebRTC

| 專案 | 用途 | 授權 |
|------|------|------|
| [m1k1o/neko](https://github.com/m1k1o/neko) | workspace-chrome 的 WebRTC 瀏覽器串流容器（`ghcr.io/m1k1o/neko/chromium`） | Apache-2.0 |
| [Chromium](https://www.chromium.org/) | neko 中實際受控的瀏覽器，搭配 DevTools Protocol 供 Agent 操作 | BSD-3-Clause |
| [Chrome DevTools Protocol (CDP)](https://chromedevtools.github.io/devtools-protocol/) | Playwright CLI ↔ `cdp-proxy` ↔ Chromium 的控制通道 | — |
| [WXT](https://wxt.dev/) | Chrome Extension（MV3）開發工具鏈 | MIT |

## ⚙️ Orchestrator / Backend（Python）

workspace-manager 與 workspace-runtime 的 FastAPI 服務。

| 專案 | 用途 | 授權 |
|------|------|------|
| [FastAPI](https://fastapi.tiangolo.com/) | Web framework | MIT |
| [Uvicorn](https://www.uvicorn.org/) | ASGI server | BSD-3-Clause |
| [Pydantic](https://docs.pydantic.dev/) | 資料驗證與設定管理 | MIT |
| [SQLAlchemy](https://www.sqlalchemy.org/) | ORM | MIT |
| [Alembic](https://alembic.sqlalchemy.org/) | DB migration | MIT |
| [asyncpg](https://github.com/MagicStack/asyncpg) / [psycopg2](https://www.psycopg.org/) | PostgreSQL driver | Apache-2.0 / LGPL |
| [Redis-py](https://github.com/redis/redis-py) | Redis client（快取、發布訂閱） | MIT |
| [Celery](https://docs.celeryq.dev/) + [Flower](https://github.com/mher/flower) + [Kombu](https://github.com/celery/kombu) | Workspace Runtime 持久工作與知識庫週期維護 | BSD-3-Clause |
| [croniter](https://github.com/kiorky/croniter) | Cron 規則解析 | MIT |
| [Docker SDK for Python](https://github.com/docker/docker-py) | 本地 Docker 模式的 workspace provisioner | Apache-2.0 |
| [Kubernetes Python Client](https://github.com/kubernetes-client/python) | K8s 模式的 workspace provisioner | Apache-2.0 |
| [python-jose](https://github.com/mpdavis/python-jose) / [PyJWT](https://github.com/jpadilla/pyjwt) | JWT 驗證 | MIT |
| [GitPython](https://github.com/gitpython-developers/GitPython) | Git 操作 | BSD-3-Clause |
| [pexpect](https://github.com/pexpect/pexpect) | 終端機互動 | ISC |
| [Supervisor](http://supervisord.org/) | 容器內多行程管理 | BSD-derived |
| [Jinja2](https://palletsprojects.com/p/jinja/) | 模板引擎 | BSD-3-Clause |
| [httpx](https://www.python-httpx.org/) / [aiohttp](https://docs.aiohttp.org/) | HTTP 客戶端 | BSD-3-Clause / Apache-2.0 |

## 🖥️ Frontend（React）

| 專案 | 用途 | 授權 |
|------|------|------|
| [React 19](https://react.dev/) | UI framework | MIT |
| [Vite](https://vitejs.dev/) | 建置與 Dev server | MIT |
| [TypeScript](https://www.typescriptlang.org/) | 型別系統 | Apache-2.0 |
| [TanStack Query](https://tanstack.com/query) | 伺服器狀態管理 | MIT |
| [Radix UI](https://www.radix-ui.com/) | 無樣式元件庫（Dialog、Menu、Tabs 等） | MIT |
| [shadcn/ui](https://ui.shadcn.com/) | Radix + Tailwind 的元件樣式系統 | MIT |
| [Tailwind CSS](https://tailwindcss.com/) | Utility-first CSS | MIT |
| [Monaco Editor](https://microsoft.github.io/monaco-editor/) | 程式碼編輯器（檔案總管/Diff 檢視） | MIT |
| [xterm.js](https://xtermjs.org/) | 瀏覽器內終端機渲染 | MIT |
| [Framer Motion](https://www.framer.com/motion/) | 動畫 | MIT |
| [Mermaid](https://mermaid.js.org/) | 流程圖 / 架構圖渲染 | MIT |
| [socket.io-client](https://socket.io/) | Realtime 雙向通訊 | MIT |
| [lucide-react](https://lucide.dev/) | Icon 集 | ISC |
| [i18next](https://www.i18next.com/) / [react-i18next](https://react.i18next.com/) | 多語系 | MIT |
| [Zod](https://zod.dev/) | Schema 驗證 | MIT |
| [react-hook-form](https://react-hook-form.com/) | 表單 | MIT |
| [react-markdown](https://github.com/remarkjs/react-markdown) + [remark-gfm](https://github.com/remarkjs/remark-gfm) | Markdown 渲染（Chat 面板） | MIT |
| [Recharts](https://recharts.org/) | 圖表 | MIT |

## 🐹 workspace-terminal（Go）

| 專案 | 用途 | 授權 |
|------|------|------|
| [Gin](https://gin-gonic.com/) | HTTP framework | MIT |
| [gorilla/websocket](https://github.com/gorilla/websocket) | WebSocket | BSD-2-Clause |
| [creack/pty](https://github.com/creack/pty) | PTY 支援 | MIT |
| [go-redis](https://github.com/redis/go-redis) | Redis 客戶端 | BSD-2-Clause |
| [Zap](https://github.com/uber-go/zap) | 結構化 Logger | MIT |

## ☸️ workspace-operator（Go）

| 專案 | 用途 | 授權 |
|------|------|------|
| [controller-runtime](https://github.com/kubernetes-sigs/controller-runtime) | Kubebuilder 風格的 Operator SDK | Apache-2.0 |
| [client-go](https://github.com/kubernetes/client-go) | K8s API client | Apache-2.0 |
| [apimachinery](https://github.com/kubernetes/apimachinery) | CRD schema 定義 | Apache-2.0 |

## 🧱 Infrastructure & Platform

| 專案 | 用途 | 授權 |
|------|------|------|
| [PostgreSQL](https://www.postgresql.org/) | 主資料庫 | PostgreSQL License |
| [Redis](https://redis.io/) | 快取、Pub/Sub、Celery broker | BSD-3-Clause（≤ 7.2） |
| [Docker](https://www.docker.com/) / [Docker Compose](https://docs.docker.com/compose/) | 本地部署 runtime | Apache-2.0 |
| [Kubernetes](https://kubernetes.io/) | 生產部署 runtime | Apache-2.0 |
| [Helm](https://helm.sh/) | K8s 部署套件管理 | Apache-2.0 |
| [Cilium](https://cilium.io/) | Kubernetes 模式的網路政策（workspace / browser allowlist） | Apache-2.0 |
| [mise](https://mise.jdx.dev/) | workspace-runtime 內的多版本工具管理 | MIT |

## 📚 文件站（本站）

| 專案 | 用途 | 授權 |
|------|------|------|
| [Docusaurus](https://docusaurus.io/) | 文件站產生器（v3） | MIT |
| [MDX](https://mdxjs.com/) | Markdown + JSX | MIT |
| [Prism](https://prismjs.com/) | 程式碼語法 highlight | MIT |

---

感謝所有上游維護者。若你是上述某個專案的作者發現授權標示有誤，歡迎直接提 issue 或 PR 修正。
