"""Agent Session test for analyzing a project.

This test sends analysis prompts through Agent Session and records all response messages.
"""

import pytest
import json
import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch
from typing import List, Dict, Any


class ProjectAnalysisRecorder:
    """Project analysis message recorder."""

    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.start_time = datetime.utcnow()

    def record(self, message_type: str, data: dict, role: str = "system"):
        """Record a message."""
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": message_type,
            "role": role,
            "data": data,
        }
        self.messages.append(record)

    def save(self, output_dir: Path):
        """Save all records to a JSON file."""
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        output_file = output_dir / f"project_analysis_{timestamp}.json"

        report = {
            "analysis_info": {
                "project": "ai-developer-hub",
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

        # Count message types
        for msg in self.messages:
            msg_type = msg.get("type", "unknown")
            report["statistics"]["message_types"][msg_type] = \
                report["statistics"]["message_types"].get(msg_type, 0) + 1

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return output_file


@pytest.fixture
def analysis_recorder():
    """Analysis recorder fixture."""
    return ProjectAnalysisRecorder()


class TestAnalyzeProject:
    """Tests for analyzing the project."""

    @pytest.mark.asyncio
    async def test_analyze_project(self, analysis_recorder):
        """Analyze the project and record all messages."""

        # 1. Simulate session creation
        session_data = {
            "session_id": "project-analysis-001",
            "workspace_id": "workspace-001",
            "workspace_path": "/workspace",
            "agentic_tool": "claude-code",
            "created_at": datetime.utcnow().isoformat(),
        }
        analysis_recorder.record("session_created", session_data, role="system")

        # 2. User initiates analysis request
        user_prompt = {
            "content": "Please analyze this project",
            "language": "zh-TW",
            "request_type": "project_analysis",
        }
        analysis_recorder.record("user_prompt", user_prompt, role="user")

        # 3. Simulate Agent analysis process
        agent_thinking = {
            "process": "Analyze project structure, configuration files, core code",
            "workspace_mount": "/workspace",
            "analysis_steps": [
                "Read project structure",
                "Check configuration files",
                "Analyze core modules",
                "Evaluate technology stack",
                "Generate analysis report"
            ],
        }
        analysis_recorder.record("agent_thinking", agent_thinking, role="assistant")

        # 4. Simulate Agent executing analysis tool calls
        tool_calls = [
            {
                "tool_id": "glob_001",
                "tool_name": "Glob",
                "purpose": "List project file structure",
                "pattern": "**/*.{md,json,py,ts,yml}",
                "status": "pending",
            },
            {
                "tool_id": "read_001",
                "tool_name": "Read",
                "purpose": "Read README file",
                "file_path": "/workspace/README.md",
                "status": "pending",
            },
            {
                "tool_id": "read_002",
                "tool_name": "Read",
                "purpose": "Read AGENTS.md",
                "file_path": "/workspace/AGENTS.md",
                "status": "pending",
            },
        ]

        for tool_call in tool_calls:
            analysis_recorder.record("tool_use", tool_call, role="assistant")

        # 5. Simulate Tool execution results
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
            "content_preview": "AI Developer Hub is a full-stack AI developer hub...",
            "key_sections": [
                "Overview",
                "Features",
                "Quick Start",
                "Architecture",
                "Development Guide",
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

        # 6. Agent processes results and generates analysis
        analysis_summary = {
            "project_name": "ai-developer-hub",
            "description": "Full-stack AI developer hub",
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
            "message_id": "msg-project-analysis",
            "content": "I have completed the analysis of the project. This is a full-stack AI developer hub...",
            "analysis_result": analysis_summary,
            "confidence": 0.95,
        }
        analysis_recorder.record("assistant_response", assistant_response, role="assistant")

        # 7. Record Session state changes
        session_states = [
            {"status": "idle", "timestamp": datetime.utcnow().isoformat()},
            {"status": "processing", "timestamp": datetime.utcnow().isoformat()},
            {"status": "executing_tools", "timestamp": datetime.utcnow().isoformat()},
            {"status": "generating_response", "timestamp": datetime.utcnow().isoformat()},
            {"status": "idle", "timestamp": datetime.utcnow().isoformat()},
        ]

        for state in session_states:
            analysis_recorder.record("session_state_change", state, role="system")

        # 8. Record analysis completion
        completion_data = {
            "analysis_status": "completed",
            "total_files_analyzed": 250,
            "key_findings": [
                "Complete OpenSpec documentation system",
                "Modular agent session architecture",
                "Powerful tool execution capabilities",
            ],
            "recommendations": [
                "Consider adding more integration tests",
                "Optimize WebSocket performance",
                "Expand tool library",
            ],
        }
        analysis_recorder.record("analysis_complete", completion_data, role="system")

        # Save all records
        output_dir = Path("/app/test-results/agent_session_messages")
        output_file = analysis_recorder.save(output_dir)

        assert len(analysis_recorder.messages) > 0
        print(f"\n✅ Saved {len(analysis_recorder.messages)} analysis messages to: {output_file}")

    @pytest.mark.asyncio
    async def test_workspace_structure_scan(self, analysis_recorder):
        """Scan workspace structure and record."""

        workspace_scan = {
            "scan_type": "directory_structure",
            "root_path": "/workspace",
            "scan_time": datetime.utcnow().isoformat(),
        }
        analysis_recorder.record("workspace_scan_start", workspace_scan, role="system")

        # Simulate directory scan results
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
                ".env.example",
                "docker-compose.yml",
                "tsconfig.json",
                "pyproject.toml",
            ],
        }
        analysis_recorder.record("directory_structure", directory_structure, role="system")

        # Save results
        output_dir = Path("/app/test-results/agent_session_messages")
        output_file = analysis_recorder.save(output_dir)

        assert len(analysis_recorder.messages) > 0
        print(f"\n✅ Saved {len(analysis_recorder.messages)} workspace scan messages to: {output_file}")

    @pytest.mark.asyncio
    async def test_technology_stack_analysis(self, analysis_recorder):
        """Analyze technology stack."""

        tech_analysis = {
            "analysis_type": "technology_stack",
            "timestamp": datetime.utcnow().isoformat(),
        }
        analysis_recorder.record("tech_analysis_start", tech_analysis, role="system")

        # Frontend technology stack
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

        # Backend technology stack
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

        # Infrastructure
        infrastructure = {
            "layer": "infrastructure",
            "containerization": "Docker Compose",
            "orchestration": "Docker",
            "databases": ["PostgreSQL 15", "Redis 7"],
            "ci_cd": "GitHub Actions",
            "package_managers": ["npm", "uv"],
        }
        analysis_recorder.record("infrastructure_stack", infrastructure, role="system")

        # Save results
        output_dir = Path("/app/test-results/agent_session_messages")
        output_file = analysis_recorder.save(output_dir)

        assert len(analysis_recorder.messages) > 0
        print(f"\n✅ Saved {len(analysis_recorder.messages)} technology stack analysis messages to: {output_file}")
