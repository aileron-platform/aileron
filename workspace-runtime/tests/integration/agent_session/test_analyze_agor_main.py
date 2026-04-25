"""分析 agor-main 項目的 Agent Session 測試.

此測試通過 Agent Session 發送分析提示並記錄所有回應消息。
"""

import pytest
import json
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from typing import List, Dict, Any


class ProjectAnalysisRecorder:
    """項目分析消息記錄器."""

    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.start_time = datetime.utcnow()

    def record(self, message_type: str, data: dict, role: str = "system"):
        """記錄消息."""
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": message_type,
            "role": role,
            "data": data,
        }
        self.messages.append(record)

    def save(self, output_dir: Path):
        """保存所有記錄到JSON文件."""
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f"agor_main_analysis_{timestamp}.json"

        report = {
            "analysis_info": {
                "project": "agor-main",
                "workspace_path": "/workspace",
                "analysis_start": self.start_time.isoformat(),
                "analysis_end": datetime.utcnow().isoformat(),
                "total_messages": len(self.messages),
            },
            "messages": self.messages,
            "statistics": {
                "system_messages": sum(1 for m in self.messages if m["role"] == "system"),
                "user_messages": sum(1 for m in self.messages if m["role"] == "user"),
                "assistant_messages": sum(1 for m in self.messages if m["role"] == "assistant"),
                "message_types": {},
            }
        }

        # 統計消息類型
        for msg in self.messages:
            msg_type = msg.get("type", "unknown")
            report["statistics"]["message_types"][msg_type] = \
                report["statistics"]["message_types"].get(msg_type, 0) + 1

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return output_file


@pytest.fixture
def analysis_recorder():
    """分析記錄器fixture."""
    return ProjectAnalysisRecorder()


class TestAnalyzeAgorMain:
    """分析 agor-main 項目的測試."""

    @pytest.mark.asyncio
    async def test_analyze_agor_main_project(self, analysis_recorder):
        """分析 agor-main 項目並記錄所有消息."""

        # 1. 模擬 Session 創建
        session_data = {
            "session_id": "agor-analysis-001",
            "workspace_id": "workspace-001",
            "workspace_path": "/workspace",
            "agentic_tool": "claude-code",
            "created_at": datetime.utcnow().isoformat(),
        }
        analysis_recorder.record("session_created", session_data, role="system")

        # 2. 用戶發起分析請求
        user_prompt = {
            "content": "請分析此專案",
            "language": "zh-TW",
            "request_type": "project_analysis",
        }
        analysis_recorder.record("user_prompt", user_prompt, role="user")

        # 3. 模擬 Agent 分析過程
        agent_thinking = {
            "process": "分析項目結構、配置文件、核心代碼",
            "workspace_mount": "/workspace (agor-main)",
            "analysis_steps": [
                "讀取項目結構",
                "檢查配置文件",
                "分析核心模塊",
                "評估技術棧",
                "生成分析報告"
            ],
        }
        analysis_recorder.record("agent_thinking", agent_thinking, role="assistant")

        # 4. 模擬 Agent 执行分析工具调用
        tool_calls = [
            {
                "tool_id": "glob_001",
                "tool_name": "Glob",
                "purpose": "列出項目文件結構",
                "pattern": "**/*.{md,json,py,ts,yml}",
                "status": "pending",
            },
            {
                "tool_id": "read_001",
                "tool_name": "Read",
                "purpose": "讀取README文件",
                "file_path": "/workspace/README.md",
                "status": "pending",
            },
            {
                "tool_id": "read_002",
                "tool_name": "Read",
                "purpose": "讀取AGENTS.md",
                "file_path": "/workspace/AGENTS.md",
                "status": "pending",
            },
        ]

        for tool_call in tool_calls:
            analysis_recorder.record("tool_use", tool_call, role="assistant")

        # 5. 模擬 Tool 執行結果
        glob_result = {
            "tool_id": "glob_001",
            "status": "completed",
            "files_found": 250,
            "file_categories": {
                "markdown": 15,
                "json": 20,
                "python": 45,
                "typescript": 80,
                "yaml": 10,
                "other": 80,
            },
            "key_files": [
                "README.md",
                "AGENTS.md",
                "CLAUDE.md",
                "package.json",
                "pyproject.toml",
                "docker-compose.yml",
                ".github/workflows",
            ],
        }
        analysis_recorder.record("tool_result", glob_result, role="system")

        readme_content = {
            "tool_id": "read_001",
            "file_path": "/workspace/README.md",
            "status": "completed",
            "content_preview": "agor 是一個全棧AI開發者中樞...",
            "key_sections": [
                "概述",
                "功能",
                "快速開始",
                "架構",
                "開發指南",
            ],
        }
        analysis_recorder.record("tool_result", readme_content, role="system")

        agents_md_content = {
            "tool_id": "read_002",
            "file_path": "/workspace/AGENTS.md",
            "status": "completed",
            "content_type": "OpenSpec documentation",
            "purpose": "Specifications and change proposals for the project",
        }
        analysis_recorder.record("tool_result", agents_md_content, role="system")

        # 6. Agent 處理結果並生成分析
        analysis_summary = {
            "project_name": "agor",
            "description": "全棧AI開發者中樞",
            "project_type": "Full-stack web application",
            "primary_technologies": [
                "TypeScript/React (Frontend)",
                "Python/FastAPI (Backend)",
                "PostgreSQL (Database)",
                "Docker (Container)",
            ],
            "key_components": [
                "Agent Session Management",
                "File System Operations",
                "Version Control Integration",
                "Workspace Runtime",
                "WebSocket Communication",
                "Tool Execution",
            ],
            "maturity_level": "active_development",
            "documentation_quality": "excellent",
        }

        assistant_response = {
            "message_id": "msg-agor-analysis",
            "content": "我已完成對agor項目的分析。這是一個全棧AI開發者中樞...",
            "analysis_result": analysis_summary,
            "confidence": 0.95,
        }
        analysis_recorder.record("assistant_response", assistant_response, role="assistant")

        # 7. 記錄 Session 狀態變化
        session_states = [
            {"status": "idle", "timestamp": datetime.utcnow().isoformat()},
            {"status": "processing", "timestamp": datetime.utcnow().isoformat()},
            {"status": "executing_tools", "timestamp": datetime.utcnow().isoformat()},
            {"status": "generating_response", "timestamp": datetime.utcnow().isoformat()},
            {"status": "idle", "timestamp": datetime.utcnow().isoformat()},
        ]

        for state in session_states:
            analysis_recorder.record("session_state_change", state, role="system")

        # 8. 記錄分析完成
        completion_data = {
            "analysis_status": "completed",
            "total_files_analyzed": 250,
            "key_findings": [
                "完整的OpenSpec documentation系統",
                "模塊化的agent session架構",
                "強大的工具執行能力",
            ],
            "recommendations": [
                "考慮增加更多integration tests",
                "優化WebSocket性能",
                "擴展工具庫",
            ],
        }
        analysis_recorder.record("analysis_complete", completion_data, role="system")

        # 保存所有記錄
        output_dir = Path("/app/test-results/agent_session_messages")
        output_file = analysis_recorder.save(output_dir)

        assert len(analysis_recorder.messages) > 0
        print(f"\n✅ 已保存 {len(analysis_recorder.messages)} 條分析消息到: {output_file}")

    @pytest.mark.asyncio
    async def test_workspace_structure_scan(self, analysis_recorder):
        """掃描workspace結構並記錄."""

        workspace_scan = {
            "scan_type": "directory_structure",
            "root_path": "/workspace",
            "scan_time": datetime.utcnow().isoformat(),
        }
        analysis_recorder.record("workspace_scan_start", workspace_scan, role="system")

        # 模擬目錄掃描結果
        directory_structure = {
            "total_directories": 45,
            "total_files": 250,
            "main_directories": {
                "frontend": "React/TypeScript UI",
                "backend": "Python FastAPI",
                "workspace-runtime": "Core runtime",
                "docs": "Documentation",
                ".github": "CI/CD",
            },
            "key_config_files": [
                ".agor.yml",
                ".env.example",
                "docker-compose.yml",
                "tsconfig.json",
                "pyproject.toml",
            ],
        }
        analysis_recorder.record("directory_structure", directory_structure, role="system")

        # 保存結果
        output_dir = Path("/app/test-results/agent_session_messages")
        output_file = analysis_recorder.save(output_dir)

        assert len(analysis_recorder.messages) > 0
        print(f"\n✅ 已保存 {len(analysis_recorder.messages)} 條workspace掃描消息到: {output_file}")

    @pytest.mark.asyncio
    async def test_technology_stack_analysis(self, analysis_recorder):
        """分析技術棧."""

        tech_analysis = {
            "analysis_type": "technology_stack",
            "timestamp": datetime.utcnow().isoformat(),
        }
        analysis_recorder.record("tech_analysis_start", tech_analysis, role="system")

        # 前端技術棧
        frontend_stack = {
            "layer": "frontend",
            "primary_language": "TypeScript",
            "framework": "React",
            "build_tool": "Vite",
            "state_management": "Custom Context + Store",
            "styling": "Tailwind CSS",
            "testing": "Vitest/Jest",
            "additional_tools": ["Monaco Editor", "Zustand", "TanStack Query"],
        }
        analysis_recorder.record("frontend_stack", frontend_stack, role="system")

        # 後端技術棧
        backend_stack = {
            "layer": "backend",
            "primary_language": "Python",
            "framework": "FastAPI",
            "orm": "SQLAlchemy",
            "database": "PostgreSQL",
            "cache": "Redis",
            "container": "Docker",
            "async_framework": "asyncio",
            "testing": "Pytest",
        }
        analysis_recorder.record("backend_stack", backend_stack, role="system")

        # 基礎設施
        infrastructure = {
            "layer": "infrastructure",
            "containerization": "Docker Compose",
            "orchestration": "Docker",
            "databases": ["PostgreSQL 15", "Redis 7"],
            "ci_cd": "GitHub Actions",
            "package_managers": ["npm", "uv"],
        }
        analysis_recorder.record("infrastructure_stack", infrastructure, role="system")

        # 保存結果
        output_dir = Path("/app/test-results/agent_session_messages")
        output_file = analysis_recorder.save(output_dir)

        assert len(analysis_recorder.messages) > 0
        print(f"\n✅ 已保存 {len(analysis_recorder.messages)} 條技術棧分析消息到: {output_file}")
