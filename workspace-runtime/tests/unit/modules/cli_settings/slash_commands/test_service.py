"""CLI Slash Commands Service unit tests"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.modules.cli_settings.slash_commands.config import (
    DocumentFormat,
    SlashCommandScope,
    SlashCommandTool,
    SlashCommandToolConfig,
)
from app.modules.cli_settings.slash_commands.service import (
    CliSlashCommandDuplicateError,
    CliSlashCommandNotFoundError,
    CliSlashCommandService,
)


# === Fixture helpers ====================================================


def _make_config(
    tmp_path: Path,
    tool: SlashCommandTool = SlashCommandTool.GEMINI,
    fmt: DocumentFormat = DocumentFormat.TOML,
    ext: str = ".toml",
    dir_name: str = "commands",
    dot_dir: str = ".gemini",
    supports_namespace: bool = True,
) -> SlashCommandToolConfig:
    user_root = tmp_path / "user" / dir_name
    return SlashCommandToolConfig(
        tool=tool,
        dir_name=dir_name,
        file_extension=ext,
        format=fmt,
        project_dot_dir=dot_dir,
        user_root=user_root,
        supports_namespace=supports_namespace,
    )


def _gemini_config(tmp_path: Path) -> SlashCommandToolConfig:
    return _make_config(tmp_path)


def _codex_config(tmp_path: Path) -> SlashCommandToolConfig:
    return _make_config(
        tmp_path,
        tool=SlashCommandTool.CODEX,
        fmt=DocumentFormat.MARKDOWN,
        ext=".md",
        dir_name="prompts",
        dot_dir=".codex",
        supports_namespace=False,
    )


def _opencode_config(tmp_path: Path) -> SlashCommandToolConfig:
    return _make_config(
        tmp_path,
        tool=SlashCommandTool.OPENCODE,
        fmt=DocumentFormat.MARKDOWN,
        ext=".md",
        dir_name="commands",
        dot_dir=".opencode",
        supports_namespace=True,
    )


WORKSPACE_ID = "test-ws"


# === Tests ==============================================================


class TestGeminiToml:
    """Gemini TOML format CRUD tests"""

    def _service(self, tmp_path: Path) -> CliSlashCommandService:
        config = _gemini_config(tmp_path)
        return CliSlashCommandService(config)

    @patch("app.modules.cli_settings.slash_commands.service.get_workspace_path")
    def test_list_empty(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)
        result = svc.list_scopes(WORKSPACE_ID)
        assert len(result.scopes) == 2
        assert all(len(g.documents) == 0 for g in result.scopes)

    @patch("app.modules.cli_settings.slash_commands.service.get_workspace_path")
    def test_create_and_get_toml(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        toml_content = 'description = "Test command"\nprompt = "Hello world"\n'
        from app.modules.cli_settings.slash_commands.models import CliSlashCommandCreateRequest

        payload = CliSlashCommandCreateRequest(fileName="test.toml", content=toml_content)
        result = svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)

        assert result.document.file_name == "test.toml"
        assert result.document.description == "Test command"
        assert result.document.format == DocumentFormat.TOML
        assert "Hello world" in result.document.content

        # Get document
        detail = svc.get_document(WORKSPACE_ID, SlashCommandScope.USER, "test.toml")
        assert detail.document.content == toml_content

    @patch("app.modules.cli_settings.slash_commands.service.get_workspace_path")
    def test_create_duplicate_raises(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import CliSlashCommandCreateRequest

        payload = CliSlashCommandCreateRequest(fileName="dup.toml", content="prompt = 'x'")
        svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)

        with pytest.raises(CliSlashCommandDuplicateError):
            svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)

    @patch("app.modules.cli_settings.slash_commands.service.get_workspace_path")
    def test_update_toml(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import (
            CliSlashCommandCreateRequest,
            CliSlashCommandUpdateRequest,
        )

        create_payload = CliSlashCommandCreateRequest(
            fileName="upd.toml", content='prompt = "old"'
        )
        svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, create_payload)

        update_payload = CliSlashCommandUpdateRequest(content='prompt = "new"\ndescription = "Updated"')
        result = svc.update_document(
            WORKSPACE_ID, SlashCommandScope.USER, "upd.toml", update_payload
        )
        assert result.document.description == "Updated"
        assert 'prompt = "new"' in result.document.content

    @patch("app.modules.cli_settings.slash_commands.service.get_workspace_path")
    def test_delete_toml(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import CliSlashCommandCreateRequest

        payload = CliSlashCommandCreateRequest(fileName="del.toml", content='prompt = "bye"')
        svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)

        result = svc.delete_document(WORKSPACE_ID, SlashCommandScope.USER, "del.toml")
        assert result.deleted is True

        with pytest.raises(CliSlashCommandNotFoundError):
            svc.get_document(WORKSPACE_ID, SlashCommandScope.USER, "del.toml")

    @patch("app.modules.cli_settings.slash_commands.service.get_workspace_path")
    def test_namespace_support(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import CliSlashCommandCreateRequest

        payload = CliSlashCommandCreateRequest(
            fileName="ns_cmd.toml",
            content='prompt = "namespaced"',
            namespace="my-ns",
        )
        result = svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)
        assert result.document.namespace == "my-ns"

        # Verify listing includes it
        scopes = svc.list_scopes(WORKSPACE_ID, SlashCommandScope.USER)
        assert len(scopes.scopes) == 1
        docs = scopes.scopes[0].documents
        assert any(d.namespace == "my-ns" for d in docs)

    @patch("app.modules.cli_settings.slash_commands.service.resolve_workspace_root")
    def test_lists_enabled_gemini_extension_commands(self, mock_workspace_root, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        home = tmp_path / "home"
        extensions_dir = home / ".gemini" / "extensions"
        extension_dir = extensions_dir / "gemini-cli-security"
        commands_dir = extension_dir / "commands" / "security"
        commands_dir.mkdir(parents=True)

        (extension_dir / "gemini-extension.json").write_text(
            json.dumps({"name": "gemini-cli-security", "version": "0.5.0"}),
            encoding="utf-8",
        )
        for name in ["analyze", "analyze-full", "analyze-github-pr"]:
            (commands_dir / f"{name}.toml").write_text(
                f'description = "{name}"\nprompt = "scan"\n',
                encoding="utf-8",
            )
        (extensions_dir / "extension-enablement.json").write_text(
            json.dumps({"gemini-cli-security": {"overrides": [f"{workspace}/*"]}}),
            encoding="utf-8",
        )

        monkeypatch.setattr(Path, "home", lambda: home)
        mock_workspace_root.return_value = workspace
        svc = self._service(tmp_path)

        result = svc.get_scope(WORKSPACE_ID, SlashCommandScope.EXTENSION)

        assert [doc.file_name for doc in result.documents] == [
            "analyze-full.toml",
            "analyze-github-pr.toml",
            "analyze.toml",
        ]
        assert {doc.namespace for doc in result.documents} == {"security"}
        assert {doc.extension_name for doc in result.documents} == {"gemini-cli-security"}

    @patch("app.modules.cli_settings.slash_commands.service.resolve_workspace_root")
    def test_list_scopes_includes_extension_scope_when_enabled_commands_exist(
        self,
        mock_workspace_root,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        class FakeResolver:
            def __init__(self) -> None:
                self.extensions_dir = tmp_path / "extensions"
                self.extensions_dir.mkdir()

            def enabled_slash_commands(self, workspace_root: Path):
                assert workspace_root == workspace
                package = SimpleNamespace(name="gemini-cli-security", version="0.5.0")
                return [
                    (
                        package,
                        SimpleNamespace(
                            fileName="analyze.toml",
                            namespace="security",
                            description="analyze",
                            content='description = "analyze"\nprompt = "scan"\n',
                        ),
                    )
                ]

        monkeypatch.setattr("app.modules.cli_settings.slash_commands.service.GeminiExtensionResourceResolver", FakeResolver)
        mock_workspace_root.return_value = workspace
        svc = self._service(tmp_path)

        result = svc.list_scopes(WORKSPACE_ID)

        assert [group.scope for group in result.scopes] == [
            SlashCommandScope.PROJECT,
            SlashCommandScope.USER,
            SlashCommandScope.EXTENSION,
        ]
        document = result.scopes[2].documents[0]
        assert document.file_name == "analyze.toml"
        assert document.namespace == "security"
        assert document.extension_name == "gemini-cli-security"

    @patch("app.modules.cli_settings.slash_commands.service.resolve_workspace_root")
    def test_get_extension_document_reads_enabled_command_content(
        self,
        mock_workspace_root,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        class FakeResolver:
            def enabled_slash_commands(self, workspace_root: Path):
                assert workspace_root == workspace
                package = SimpleNamespace(name="gemini-cli-security", version="0.5.0")
                return [
                    (
                        package,
                        SimpleNamespace(
                            fileName="analyze.toml",
                            namespace="security",
                            description="analyze",
                            content='description = "analyze"\nprompt = "scan"\n',
                        ),
                    )
                ]

        monkeypatch.setattr("app.modules.cli_settings.slash_commands.service.GeminiExtensionResourceResolver", FakeResolver)
        mock_workspace_root.return_value = workspace
        svc = self._service(tmp_path)

        result = svc.get_document(WORKSPACE_ID, SlashCommandScope.EXTENSION, "analyze.toml")

        assert result.scope == SlashCommandScope.EXTENSION
        assert result.document.file_name == "analyze.toml"
        assert result.document.content == 'description = "analyze"\nprompt = "scan"\n'
        assert result.document.extension_name == "gemini-cli-security"
        assert result.document.extension_version == "0.5.0"


class TestCodexMarkdown:
    """Codex Markdown format CRUD tests"""

    def _service(self, tmp_path: Path) -> CliSlashCommandService:
        config = _codex_config(tmp_path)
        return CliSlashCommandService(config)

    @patch("app.modules.cli_settings.slash_commands.service.get_workspace_path")
    def test_create_and_get_markdown(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        md_content = "---\ndescription: A codex prompt\n---\n# My Prompt\nDo something useful.\n"
        from app.modules.cli_settings.slash_commands.models import CliSlashCommandCreateRequest

        payload = CliSlashCommandCreateRequest(fileName="my-prompt", content=md_content)
        result = svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)

        assert result.document.file_name == "my-prompt.md"
        assert result.document.description == "A codex prompt"
        assert result.document.format == DocumentFormat.MARKDOWN
        # namespace should be None for codex (no namespace support)
        assert result.document.namespace is None

    @patch("app.modules.cli_settings.slash_commands.service.get_workspace_path")
    def test_list_markdown(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import CliSlashCommandCreateRequest

        svc.create_document(
            WORKSPACE_ID,
            SlashCommandScope.USER,
            CliSlashCommandCreateRequest(fileName="a.md", content="# A"),
        )
        svc.create_document(
            WORKSPACE_ID,
            SlashCommandScope.USER,
            CliSlashCommandCreateRequest(fileName="b.md", content="# B"),
        )

        result = svc.list_scopes(WORKSPACE_ID, SlashCommandScope.USER)
        assert len(result.scopes) == 1
        assert len(result.scopes[0].documents) == 2

    @patch("app.modules.cli_settings.slash_commands.service.get_workspace_path")
    def test_auto_md_extension(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import CliSlashCommandCreateRequest

        payload = CliSlashCommandCreateRequest(fileName="no-ext", content="# No ext")
        result = svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)
        assert result.document.file_name == "no-ext.md"


class TestOpencodeMarkdown:
    """OpenCode Markdown format CRUD tests"""

    def _service(self, tmp_path: Path) -> CliSlashCommandService:
        config = _opencode_config(tmp_path)
        return CliSlashCommandService(config)

    @patch("app.modules.cli_settings.slash_commands.service.get_workspace_path")
    def test_namespace_in_opencode(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import CliSlashCommandCreateRequest

        payload = CliSlashCommandCreateRequest(
            fileName="oc-cmd.md",
            content="# OpenCode command",
            namespace="tools",
        )
        result = svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)
        assert result.document.namespace == "tools"
        assert result.document.format == DocumentFormat.MARKDOWN

    @patch("app.modules.cli_settings.slash_commands.service.get_workspace_path")
    def test_project_scope_path(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import CliSlashCommandCreateRequest

        payload = CliSlashCommandCreateRequest(
            fileName="proj-cmd.md", content="# Project command"
        )
        result = svc.create_document(WORKSPACE_ID, SlashCommandScope.PROJECT, payload)
        assert result.document.file_name == "proj-cmd.md"
        assert result.scope == SlashCommandScope.PROJECT

        # Verify file was created in the project directory
        expected_dir = tmp_path / "workspace" / ".opencode" / "commands"
        assert (expected_dir / "proj-cmd.md").exists()


class TestCrossToolParameterized:
    """Cross-tool parameterization tests"""

    @pytest.mark.parametrize(
        "config_factory,file_content,expected_ext",
        [
            (_gemini_config, 'prompt = "hello"', ".toml"),
            (_codex_config, "# Hello", ".md"),
            (_opencode_config, "# Hello", ".md"),
        ],
        ids=["gemini", "codex", "opencode"],
    )
    @patch("app.modules.cli_settings.slash_commands.service.get_workspace_path")
    def test_create_normalizes_extension(
        self, mock_ws, tmp_path, config_factory, file_content, expected_ext
    ) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        config = config_factory(tmp_path)
        svc = CliSlashCommandService(config)

        from app.modules.cli_settings.slash_commands.models import CliSlashCommandCreateRequest

        payload = CliSlashCommandCreateRequest(fileName="test-cmd", content=file_content)
        result = svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)
        assert result.document.file_name.endswith(expected_ext)

    @pytest.mark.parametrize(
        "config_factory",
        [_gemini_config, _codex_config, _opencode_config],
        ids=["gemini", "codex", "opencode"],
    )
    @patch("app.modules.cli_settings.slash_commands.service.get_workspace_path")
    def test_delete_nonexistent_raises(self, mock_ws, tmp_path, config_factory) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        config = config_factory(tmp_path)
        svc = CliSlashCommandService(config)

        with pytest.raises(CliSlashCommandNotFoundError):
            svc.delete_document(WORKSPACE_ID, SlashCommandScope.USER, "nonexistent")
