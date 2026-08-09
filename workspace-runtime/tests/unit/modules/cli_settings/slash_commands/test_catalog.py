"""CLI Slash Commands Service unit tests"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from app.core.revision import compute_revision
from app.modules.cli_settings.slash_commands.config import (
    DocumentFormat,
    SlashCommandScope,
    SlashCommandTool,
    SlashCommandToolConfig,
)
from app.modules.cli_settings.slash_commands.catalog import (
    CliSlashCommandDuplicateError,
    CliSlashCommandNotFoundError,
    CliSlashCommandService,
)


# === Fixture helpers ====================================================


def _make_config(
    tmp_path: Path,
    tool: SlashCommandTool = SlashCommandTool.OPENCODE,
    fmt: DocumentFormat = DocumentFormat.TOML,
    ext: str = ".toml",
    dir_name: str = "commands",
    dot_dir: str = ".opencode",
) -> SlashCommandToolConfig:
    user_root = tmp_path / "user" / dir_name
    return SlashCommandToolConfig(
        tool=tool,
        dir_name=dir_name,
        file_extension=ext,
        format=fmt,
        project_dot_dir=dot_dir,
        user_root=user_root,
    )


def _toml_config(tmp_path: Path) -> SlashCommandToolConfig:
    return _make_config(tmp_path)


def _codex_config(tmp_path: Path) -> SlashCommandToolConfig:
    return _make_config(
        tmp_path,
        tool=SlashCommandTool.CODEX,
        fmt=DocumentFormat.MARKDOWN,
        ext=".md",
        dir_name="prompts",
        dot_dir=".codex",
    )


def _opencode_config(tmp_path: Path) -> SlashCommandToolConfig:
    return _make_config(
        tmp_path,
        tool=SlashCommandTool.OPENCODE,
        fmt=DocumentFormat.MARKDOWN,
        ext=".md",
        dir_name="commands",
        dot_dir=".opencode",
    )


WORKSPACE_ID = "test-ws"


def _empty_scope_revision() -> str:
    return compute_revision("{}")


def _content_revision(content: str) -> str:
    return compute_revision(content)


# === Tests ==============================================================


class TestTomlSlashCommands:
    """TOML format CRUD tests"""

    def _service(self, tmp_path: Path) -> CliSlashCommandService:
        config = _toml_config(tmp_path)
        return CliSlashCommandService(config)

    @patch("app.modules.cli_settings.slash_commands.catalog.get_workspace_path")
    def test_list_empty(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)
        result = svc.list_scopes(WORKSPACE_ID)
        assert result.items == []
        assert [
            (scope.scope, scope.read_only) for scope in result.available_scopes
        ] == [
            (SlashCommandScope.PROJECT, False),
            (SlashCommandScope.USER, False),
        ]

    @patch("app.modules.cli_settings.slash_commands.catalog.get_workspace_path")
    def test_create_and_get_toml(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        toml_content = 'description = "Test command"\nprompt = "Hello world"\n'
        from app.modules.cli_settings.slash_commands.models import (
            CliSlashCommandCreateRequest,
        )

        payload = CliSlashCommandCreateRequest(
            path="test.toml",
            content=toml_content,
            revision=_empty_scope_revision(),
        )
        result = svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)

        assert result.document.path == "test.toml"
        assert result.revision == _content_revision(toml_content)
        assert result.document.description == "Test command"
        assert result.document.format == DocumentFormat.TOML
        assert "Hello world" in result.document.content

        # Get document
        detail = svc.get_document(WORKSPACE_ID, SlashCommandScope.USER, "test.toml")
        assert detail.document.content == toml_content
        assert detail.revision == result.revision

    @patch("app.modules.cli_settings.slash_commands.catalog.get_workspace_path")
    def test_create_duplicate_raises(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import (
            CliSlashCommandCreateRequest,
        )

        payload = CliSlashCommandCreateRequest(
            path="dup.toml",
            content="prompt = 'x'",
            revision=_empty_scope_revision(),
        )
        svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)

        payload.revision = svc.get_scope(WORKSPACE_ID, SlashCommandScope.USER).revision
        with pytest.raises(CliSlashCommandDuplicateError):
            svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)

    @patch("app.modules.cli_settings.slash_commands.catalog.get_workspace_path")
    def test_update_toml(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import (
            CliSlashCommandCreateRequest,
            CliSlashCommandUpdateRequest,
        )

        create_payload = CliSlashCommandCreateRequest(
            path="upd.toml",
            content='prompt = "old"',
            revision=_empty_scope_revision(),
        )
        created = svc.create_document(
            WORKSPACE_ID, SlashCommandScope.USER, create_payload
        )

        update_payload = CliSlashCommandUpdateRequest(
            path="upd.toml",
            content='prompt = "new"\ndescription = "Updated"',
            revision=created.revision,
        )
        result = svc.update_document(
            WORKSPACE_ID, SlashCommandScope.USER, update_payload
        )
        assert result.document.description == "Updated"
        assert 'prompt = "new"' in result.document.content
        assert result.revision == _content_revision(
            'prompt = "new"\ndescription = "Updated"'
        )

    @patch("app.modules.cli_settings.slash_commands.catalog.get_workspace_path")
    def test_update_rejects_stale_revision(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import (
            CliSlashCommandCreateRequest,
            CliSlashCommandUpdateRequest,
        )

        created = svc.create_document(
            WORKSPACE_ID,
            SlashCommandScope.USER,
            CliSlashCommandCreateRequest(
                path="stale.toml",
                content='prompt = "old"',
                revision=_empty_scope_revision(),
            ),
        )
        svc.update_document(
            WORKSPACE_ID,
            SlashCommandScope.USER,
            CliSlashCommandUpdateRequest(
                path="stale.toml",
                content='prompt = "new"',
                revision=created.revision,
            ),
        )

        with pytest.raises(HTTPException) as exc_info:
            svc.update_document(
                WORKSPACE_ID,
                SlashCommandScope.USER,
                CliSlashCommandUpdateRequest(
                    path="stale.toml",
                    content='prompt = "stale"',
                    revision=created.revision,
                ),
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["errorCode"] == "REVISION_CONFLICT"

    @patch("app.modules.cli_settings.slash_commands.catalog.get_workspace_path")
    def test_delete_toml(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import (
            CliSlashCommandCreateRequest,
        )

        payload = CliSlashCommandCreateRequest(
            path="del.toml",
            content='prompt = "bye"',
            revision=_empty_scope_revision(),
        )
        created = svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)

        result = svc.delete_document(
            WORKSPACE_ID,
            SlashCommandScope.USER,
            "del.toml",
            revision=created.revision,
        )
        assert result.deleted is True
        assert result.revision == _empty_scope_revision()

        with pytest.raises(CliSlashCommandNotFoundError):
            svc.get_document(WORKSPACE_ID, SlashCommandScope.USER, "del.toml")

    @patch("app.modules.cli_settings.slash_commands.catalog.get_workspace_path")
    def test_path_directory_support(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import (
            CliSlashCommandCreateRequest,
        )

        payload = CliSlashCommandCreateRequest(
            path="my-ns/ns_cmd.toml",
            content='prompt = "namespaced"',
            revision=_empty_scope_revision(),
        )
        result = svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)
        assert result.document.path == "my-ns/ns_cmd.toml"

        # Verify listing includes it
        scopes = svc.list_scopes(WORKSPACE_ID, SlashCommandScope.USER)
        assert [
            (scope.scope, scope.read_only) for scope in scopes.available_scopes
        ] == [
            (SlashCommandScope.USER, False),
        ]
        docs = scopes.items
        assert any(d.path == "my-ns/ns_cmd.toml" for d in docs)

    @patch("app.modules.cli_settings.slash_commands.catalog.get_workspace_path")
    def test_path_identity_allows_same_name_across_directories(
        self, mock_ws, tmp_path: Path
    ) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import (
            CliSlashCommandCreateRequest,
        )

        svc.create_document(
            WORKSPACE_ID,
            SlashCommandScope.USER,
            CliSlashCommandCreateRequest(
                path="drive/search.toml",
                content='description = "Drive search"\nprompt = "drive"\n',
                revision=_empty_scope_revision(),
            ),
        )
        revision = svc.get_scope(WORKSPACE_ID, SlashCommandScope.USER).revision
        svc.create_document(
            WORKSPACE_ID,
            SlashCommandScope.USER,
            CliSlashCommandCreateRequest(
                path="gmail/search.toml",
                content='description = "Gmail search"\nprompt = "gmail"\n',
                revision=revision,
            ),
        )

        drive_result = svc.get_document(
            WORKSPACE_ID, SlashCommandScope.USER, "drive/search.toml"
        )
        gmail_result = svc.get_document(
            WORKSPACE_ID, SlashCommandScope.USER, "gmail/search.toml"
        )

        assert drive_result.document.path == "drive/search.toml"
        assert 'prompt = "drive"' in drive_result.document.content
        assert gmail_result.document.path == "gmail/search.toml"
        assert 'prompt = "gmail"' in gmail_result.document.content


class TestCodexMarkdown:
    """Codex Markdown format CRUD tests"""

    def _service(self, tmp_path: Path) -> CliSlashCommandService:
        config = _codex_config(tmp_path)
        return CliSlashCommandService(config)

    @patch("app.modules.cli_settings.slash_commands.catalog.get_workspace_path")
    def test_create_and_get_markdown(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        md_content = (
            "---\ndescription: A codex prompt\n---\n# My Prompt\nDo something useful.\n"
        )
        from app.modules.cli_settings.slash_commands.models import (
            CliSlashCommandCreateRequest,
        )

        payload = CliSlashCommandCreateRequest(
            path="my-prompt",
            content=md_content,
            revision=_empty_scope_revision(),
        )
        result = svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)

        assert result.document.path == "my-prompt.md"
        assert result.document.description == "A codex prompt"
        assert result.document.format == DocumentFormat.MARKDOWN

    @patch("app.modules.cli_settings.slash_commands.catalog.get_workspace_path")
    def test_list_markdown(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import (
            CliSlashCommandCreateRequest,
        )

        svc.create_document(
            WORKSPACE_ID,
            SlashCommandScope.USER,
            CliSlashCommandCreateRequest(
                path="a.md",
                content="# A",
                revision=_empty_scope_revision(),
            ),
        )
        revision = svc.get_scope(WORKSPACE_ID, SlashCommandScope.USER).revision
        svc.create_document(
            WORKSPACE_ID,
            SlashCommandScope.USER,
            CliSlashCommandCreateRequest(
                path="b.md",
                content="# B",
                revision=revision,
            ),
        )

        result = svc.list_scopes(WORKSPACE_ID, SlashCommandScope.USER)
        assert [
            (scope.scope, scope.read_only) for scope in result.available_scopes
        ] == [
            (SlashCommandScope.USER, False),
        ]
        assert len(result.items) == 2

    @patch("app.modules.cli_settings.slash_commands.catalog.get_workspace_path")
    def test_auto_md_extension(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import (
            CliSlashCommandCreateRequest,
        )

        payload = CliSlashCommandCreateRequest(
            path="no-ext",
            content="# No ext",
            revision=_empty_scope_revision(),
        )
        result = svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)
        assert result.document.path == "no-ext.md"


class TestOpencodeMarkdown:
    """OpenCode Markdown format CRUD tests"""

    def _service(self, tmp_path: Path) -> CliSlashCommandService:
        config = _opencode_config(tmp_path)
        return CliSlashCommandService(config)

    @patch("app.modules.cli_settings.slash_commands.catalog.get_workspace_path")
    def test_path_directory_in_opencode(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import (
            CliSlashCommandCreateRequest,
        )

        payload = CliSlashCommandCreateRequest(
            path="tools/oc-cmd.md",
            content="# OpenCode command",
            revision=_empty_scope_revision(),
        )
        result = svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)
        assert result.document.path == "tools/oc-cmd.md"
        assert result.document.format == DocumentFormat.MARKDOWN

    @patch("app.modules.cli_settings.slash_commands.catalog.get_workspace_path")
    def test_project_scope_path(self, mock_ws, tmp_path: Path) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        svc = self._service(tmp_path)

        from app.modules.cli_settings.slash_commands.models import (
            CliSlashCommandCreateRequest,
        )

        payload = CliSlashCommandCreateRequest(
            path="proj-cmd.md",
            content="# Project command",
            revision=_empty_scope_revision(),
        )
        result = svc.create_document(WORKSPACE_ID, SlashCommandScope.PROJECT, payload)
        assert result.document.path == "proj-cmd.md"
        assert result.scope == SlashCommandScope.PROJECT

        # Verify file was created in the project directory
        expected_dir = tmp_path / "workspace" / ".opencode" / "commands"
        assert (expected_dir / "proj-cmd.md").exists()


class TestCrossToolParameterized:
    """Cross-tool parameterization tests"""

    @pytest.mark.parametrize(
        "config_factory,file_content,expected_ext",
        [
            (_toml_config, 'prompt = "hello"', ".toml"),
            (_codex_config, "# Hello", ".md"),
            (_opencode_config, "# Hello", ".md"),
        ],
        ids=["toml", "codex", "opencode"],
    )
    @patch("app.modules.cli_settings.slash_commands.catalog.get_workspace_path")
    def test_create_normalizes_extension(
        self, mock_ws, tmp_path, config_factory, file_content, expected_ext
    ) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        config = config_factory(tmp_path)
        svc = CliSlashCommandService(config)

        from app.modules.cli_settings.slash_commands.models import (
            CliSlashCommandCreateRequest,
        )

        payload = CliSlashCommandCreateRequest(
            path="test-cmd",
            content=file_content,
            revision=_empty_scope_revision(),
        )
        result = svc.create_document(WORKSPACE_ID, SlashCommandScope.USER, payload)
        assert result.document.path.endswith(expected_ext)

    @pytest.mark.parametrize(
        "config_factory",
        [_toml_config, _codex_config, _opencode_config],
        ids=["toml", "codex", "opencode"],
    )
    @patch("app.modules.cli_settings.slash_commands.catalog.get_workspace_path")
    def test_delete_nonexistent_raises(self, mock_ws, tmp_path, config_factory) -> None:
        mock_ws.return_value = str(tmp_path / "workspace")
        config = config_factory(tmp_path)
        svc = CliSlashCommandService(config)

        with pytest.raises(CliSlashCommandNotFoundError):
            svc.delete_document(
                WORKSPACE_ID,
                SlashCommandScope.USER,
                "nonexistent",
                revision=_empty_scope_revision(),
            )
