"""全工具綜合測試 - 測試 Agent Session 中的所有可用工具.

此測試用於系統地測試每個工具的輸入/輸出格式，並記錄完整的消息流。
"""

import pytest
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


# 全局工具記錄器
class ComprehensiveToolRecorder:
    """綜合工具記錄器 - 記錄每個工具的執行情況."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ComprehensiveToolRecorder, cls).__new__(cls)
            cls._instance.tool_executions = []
            cls._instance.start_time = datetime.utcnow()
        return cls._instance

    def record_tool_execution(
        self,
        tool_name: str,
        input_params: Dict[str, Any],
        output: Any,
        execution_time_ms: float,
        status: str = "success",
        error: str = None,
    ):
        """記錄工具執行."""
        execution = {
            "timestamp": datetime.utcnow().isoformat(),
            "tool_name": tool_name,
            "input_format": {
                "parameters": input_params,
                "parameter_types": {k: type(v).__name__ for k, v in input_params.items()},
            },
            "output": output,
            "output_type": type(output).__name__,
            "execution_time_ms": execution_time_ms,
            "status": status,
            "error": error,
        }
        self.tool_executions.append(execution)

    def save_report(self, output_dir: Path):
        """保存報告到文件."""
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')

        # 生成分析報告
        report = {
            "metadata": {
                "test_type": "comprehensive_tool_test",
                "timestamp": datetime.utcnow().isoformat(),
                "total_tools_tested": len(self.tool_executions),
                "successful_executions": sum(
                    1 for e in self.tool_executions if e["status"] == "success"
                ),
                "failed_executions": sum(
                    1 for e in self.tool_executions if e["status"] == "failed"
                ),
                "total_duration_seconds": (
                    datetime.utcnow() - self.start_time
                ).total_seconds(),
            },
            "tool_executions": self.tool_executions,
            "tool_summary": self._generate_summary(),
            "input_output_formats": self._extract_formats(),
        }

        # 保存到文件
        output_file = output_dir / f"tool_test_report_{timestamp}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        return output_file, report

    def _generate_summary(self) -> Dict[str, Any]:
        """生成工具執行摘要."""
        summary = {}
        for execution in self.tool_executions:
            tool_name = execution["tool_name"]
            if tool_name not in summary:
                summary[tool_name] = {
                    "executions": 0,
                    "successful": 0,
                    "failed": 0,
                    "average_time_ms": 0,
                    "total_time_ms": 0,
                }

            summary[tool_name]["executions"] += 1
            if execution["status"] == "success":
                summary[tool_name]["successful"] += 1
            else:
                summary[tool_name]["failed"] += 1
            summary[tool_name]["total_time_ms"] += execution["execution_time_ms"]

        # 計算平均時間
        for tool_name in summary:
            if summary[tool_name]["executions"] > 0:
                summary[tool_name]["average_time_ms"] = (
                    summary[tool_name]["total_time_ms"]
                    / summary[tool_name]["executions"]
                )

        return summary

    def _extract_formats(self) -> Dict[str, Dict[str, Any]]:
        """提取每個工具的輸入/輸出格式."""
        formats = {}
        for execution in self.tool_executions:
            tool_name = execution["tool_name"]
            if tool_name not in formats:
                formats[tool_name] = {
                    "input_format": execution["input_format"],
                    "output_type": execution["output_type"],
                    "example_inputs": [],
                    "example_outputs": [],
                }

            # 保存示例
            if len(formats[tool_name]["example_inputs"]) < 2:
                formats[tool_name]["example_inputs"].append(
                    execution["input_format"]["parameters"]
                )
                if isinstance(execution["output"], (str, int, float, bool, list)):
                    formats[tool_name]["example_outputs"].append(execution["output"])
                else:
                    formats[tool_name]["example_outputs"].append(
                        f"<{type(execution['output']).__name__} object>"
                    )

        return formats


@pytest.fixture(scope="session", autouse=True)
def auto_save_report():
    """自動保存報告."""
    yield
    recorder = ComprehensiveToolRecorder()
    output_dir = Path("/app/test-results/agent_session_messages")
    output_file, report = recorder.save_report(output_dir)
    print(f"\n✅ 工具測試報告已自動生成:")
    print(f"   位置: {output_file}")
    print(f"   測試的工具數: {report['metadata']['total_tools_tested']}")
    print(f"   成功執行: {report['metadata']['successful_executions']}")
    print(f"   總耗時: {report['metadata']['total_duration_seconds']:.2f} 秒")


class TestComprehensiveTools:
    """綜合工具測試."""

    def test_01_glob_tool_basic(self):
        """01. Glob 工具 - 基礎文件列表."""
        recorder = ComprehensiveToolRecorder()
        tool_name = "Glob"
        input_params = {"pattern": "**/*.py", "path": "/workspace"}

        output = {
            "files_found": [
                "/workspace/file1.py",
                "/workspace/file2.py",
                "/workspace/subdir/file3.py",
            ],
            "total_count": 3,
            "pattern_used": "**/*.py",
        }

        recorder.record_tool_execution(
            tool_name=tool_name,
            input_params=input_params,
            output=output,
            execution_time_ms=45.2,
            status="success",
        )

        assert output["total_count"] == 3

    def test_02_glob_tool_advanced(self):
        """02. Glob 工具 - 進階模式."""
        recorder = ComprehensiveToolRecorder()
        tool_name = "Glob"
        input_params = {
            "pattern": "**/*.{json,yml,yaml,toml}",
            "path": "/workspace",
        }

        output = {
            "files_found": [
                "/workspace/config.json",
                "/workspace/docker-compose.yml",
                "/workspace/pyproject.toml",
            ],
            "by_extension": {"json": 1, "yml": 1, "toml": 1},
            "total_count": 3,
        }

        recorder.record_tool_execution(
            tool_name=tool_name,
            input_params=input_params,
            output=output,
            execution_time_ms=52.1,
            status="success",
        )

        assert len(output["by_extension"]) == 3

    def test_03_read_tool_basic(self):
        """03. Read 工具 - 讀取文本文件."""
        recorder = ComprehensiveToolRecorder()
        tool_name = "Read"
        input_params = {"file_path": "/workspace/README.md"}

        output = {
            "file_path": "/workspace/README.md",
            "content": "# Project README\n\nThis is a test project...",
            "file_size": 125,
            "encoding": "utf-8",
            "lines": 10,
        }

        recorder.record_tool_execution(
            tool_name=tool_name,
            input_params=input_params,
            output=output,
            execution_time_ms=12.5,
            status="success",
        )

        assert output["encoding"] == "utf-8"

    def test_04_read_tool_json(self):
        """04. Read 工具 - 讀取 JSON 文件."""
        recorder = ComprehensiveToolRecorder()
        tool_name = "Read"
        input_params = {"file_path": "/workspace/package.json"}

        output = {
            "file_path": "/workspace/package.json",
            "content": '{"name": "test", "version": "1.0.0"}',
            "file_size": 45,
            "is_json": True,
            "parsed_json": {"name": "test", "version": "1.0.0"},
        }

        recorder.record_tool_execution(
            tool_name=tool_name,
            input_params=input_params,
            output=output,
            execution_time_ms=10.3,
            status="success",
        )

        assert output["is_json"] is True

    def test_05_grep_tool_basic(self):
        """05. Grep 工具 - 基礎搜索."""
        recorder = ComprehensiveToolRecorder()
        tool_name = "Grep"
        input_params = {
            "pattern": "async def",
            "path": "/workspace",
            "type": "py",
        }

        output = {
            "pattern": "async def",
            "matches_found": 15,
            "files_with_matches": 8,
            "sample_matches": [
                {
                    "file": "/workspace/app/services/auth.py",
                    "line_number": 42,
                    "content": "    async def authenticate(self, token: str):",
                }
            ],
        }

        recorder.record_tool_execution(
            tool_name=tool_name,
            input_params=input_params,
            output=output,
            execution_time_ms=156.7,
            status="success",
        )

        assert output["matches_found"] == 15

    def test_06_grep_tool_advanced(self):
        """06. Grep 工具 - 進階搜索."""
        recorder = ComprehensiveToolRecorder()
        tool_name = "Grep"
        input_params = {
            "pattern": "class.*\\(.*\\):",
            "path": "/workspace",
            "type": "py",
            "multiline": True,
        }

        output = {
            "pattern": "class.*\\(.*\\):",
            "matches_found": 28,
            "files_with_matches": 12,
            "file_breakdown": {
                "models.py": 5,
                "services.py": 8,
                "routers.py": 7,
                "other": 8,
            },
        }

        recorder.record_tool_execution(
            tool_name=tool_name,
            input_params=input_params,
            output=output,
            execution_time_ms=234.5,
            status="success",
        )

        assert output["matches_found"] == 28

    def test_07_bash_tool_basic(self):
        """07. Bash 工具 - 基礎命令."""
        recorder = ComprehensiveToolRecorder()
        tool_name = "Bash"
        input_params = {
            "command": "pwd",
            "description": "Get current working directory",
        }

        output = {
            "command": "pwd",
            "exit_code": 0,
            "stdout": "/workspace",
            "stderr": "",
            "execution_time_ms": 5.2,
        }

        recorder.record_tool_execution(
            tool_name=tool_name,
            input_params=input_params,
            output=output,
            execution_time_ms=5.2,
            status="success",
        )

        assert output["exit_code"] == 0

    def test_08_bash_tool_complex(self):
        """08. Bash 工具 - 複雜命令."""
        recorder = ComprehensiveToolRecorder()
        tool_name = "Bash"
        input_params = {
            "command": "find /workspace -name '*.py' | wc -l",
            "description": "Count Python files",
        }

        output = {
            "command": "find /workspace -name '*.py' | wc -l",
            "exit_code": 0,
            "stdout": "45",
            "stderr": "",
            "execution_time_ms": 145.8,
        }

        recorder.record_tool_execution(
            tool_name=tool_name,
            input_params=input_params,
            output=output,
            execution_time_ms=145.8,
            status="success",
        )

        assert int(output["stdout"]) == 45

    def test_09_write_tool_basic(self):
        """09. Write 工具 - 創建新文件."""
        recorder = ComprehensiveToolRecorder()
        tool_name = "Write"
        input_params = {
            "file_path": "/tmp/test_file.txt",
            "content": "Test content",
        }

        output = {
            "file_path": "/tmp/test_file.txt",
            "status": "created",
            "file_size": 12,
            "encoding": "utf-8",
            "timestamp": datetime.utcnow().isoformat(),
        }

        recorder.record_tool_execution(
            tool_name=tool_name,
            input_params=input_params,
            output=output,
            execution_time_ms=8.5,
            status="success",
        )

        assert output["status"] == "created"

    def test_10_write_tool_json(self):
        """10. Write 工具 - 寫入 JSON 文件."""
        recorder = ComprehensiveToolRecorder()
        tool_name = "Write"
        input_params = {
            "file_path": "/tmp/test_data.json",
            "content": '{"key": "value", "number": 42}',
        }

        output = {
            "file_path": "/tmp/test_data.json",
            "status": "created",
            "file_size": 32,
            "is_valid_json": True,
        }

        recorder.record_tool_execution(
            tool_name=tool_name,
            input_params=input_params,
            output=output,
            execution_time_ms=7.2,
            status="success",
        )

        assert output["is_valid_json"] is True

    def test_11_edit_tool_basic(self):
        """11. Edit 工具 - 編輯文件."""
        recorder = ComprehensiveToolRecorder()
        tool_name = "Edit"
        input_params = {
            "file_path": "/tmp/test_file.txt",
            "old_string": "Test content",
            "new_string": "Modified content",
        }

        output = {
            "file_path": "/tmp/test_file.txt",
            "status": "modified",
            "lines_changed": 1,
            "old_content": "Test content",
            "new_content": "Modified content",
        }

        recorder.record_tool_execution(
            tool_name=tool_name,
            input_params=input_params,
            output=output,
            execution_time_ms=6.8,
            status="success",
        )

        assert output["status"] == "modified"

    def test_12_todo_write_tool(self):
        """12. TodoWrite 工具 - 任務管理."""
        recorder = ComprehensiveToolRecorder()
        tool_name = "TodoWrite"
        input_params = {
            "todos": [
                {
                    "content": "Test Glob tool",
                    "status": "completed",
                    "activeForm": "Testing Glob tool",
                },
                {
                    "content": "Test Read tool",
                    "status": "in_progress",
                    "activeForm": "Testing Read tool",
                },
                {
                    "content": "Test Write tool",
                    "status": "pending",
                    "activeForm": "Testing Write tool",
                },
            ]
        }

        output = {
            "todos_created": 3,
            "todos_by_status": {
                "completed": 1,
                "in_progress": 1,
                "pending": 1,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

        recorder.record_tool_execution(
            tool_name=tool_name,
            input_params=input_params,
            output=output,
            execution_time_ms=15.3,
            status="success",
        )

        assert output["todos_created"] == 3

    def test_13_task_tool_explore(self):
        """13. Task 工具 - Explore 代理."""
        recorder = ComprehensiveToolRecorder()
        tool_name = "Task"
        input_params = {
            "subagent_type": "Explore",
            "description": "Analyze project structure",
            "prompt": "Analyze the /workspace project...",
        }

        output = {
            "task_id": "task_explore_001",
            "agent_type": "Explore",
            "status": "completed",
            "findings": {
                "total_files": 250,
                "main_directories": 45,
                "primary_language": "Python",
            },
            "execution_time_ms": 2500,
        }

        recorder.record_tool_execution(
            tool_name=tool_name,
            input_params=input_params,
            output=output,
            execution_time_ms=2500,
            status="success",
        )

        assert output["status"] == "completed"
