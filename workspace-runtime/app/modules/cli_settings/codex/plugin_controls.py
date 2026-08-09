"""Provider-native policy and trust controls for installed Codex plugins."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Literal

from fastapi import HTTPException, status

from app.core.revision import assert_revision, compute_revision
from app.modules.cli_settings.user_scope.models import CodexLayer, CodexResource
from app.modules.cli_settings.user_scope.paths import (
    CodexPathResolver,
)
from app.modules.cli_settings.toml_codec import dump_toml, parse_toml
from app.modules.cli_settings.user_scope.codecs import read_text, write_text_atomic
from app.modules.marketplace_operations.gate import get_marketplace_provider_gate

from .app_server_hooks import (
    CodexAuthoritativeHook,
    CodexHooksListClient,
    clear_codex_hooks_cache,
)
from .models import CodexPluginHookTrustState, CodexPluginMcpPolicy
from .plugin_resources import (
    CodexPluginHookDocument,
    CodexPluginMcpServer,
    CodexPluginResourceResolver,
)

_write_locks_guard = Lock()
_write_locks: dict[Path, Lock] = {}


def _write_lock(path: Path) -> Lock:
    with _write_locks_guard:
        return _write_locks.setdefault(path, Lock())


@dataclass(frozen=True)
class CodexPluginHookControl:
    """One command hook's official persisted trust identity."""

    plugin_id: str
    key: str
    current_hash: str
    enabled: bool
    trust_state: Literal["trusted", "untrusted", "modified"]

    @property
    def trusted(self) -> bool:
        return self.trust_state == "trusted"


@dataclass(frozen=True)
class CodexPluginHookControlSummary:
    """Aggregate trust and effective state for one plugin hook document."""

    trust_state: CodexPluginHookTrustState
    trusted: bool
    effective: bool
    revision: str
    controls: tuple[CodexPluginHookControl, ...]


class CodexPluginControlStore:
    """Read and mutate only provider-supported plugin policy state."""

    def __init__(
        self,
        resolver: CodexPathResolver,
        plugin_resolver: CodexPluginResourceResolver | None = None,
        hooks_client: CodexHooksListClient | None = None,
    ) -> None:
        self._resolver = resolver
        self._plugin_resolver = plugin_resolver or CodexPluginResourceResolver(resolver)
        self._hooks_client = hooks_client or CodexHooksListClient()
        self._hooks_cache_key: tuple[int, str] | None = None
        self._hooks_cache: tuple[CodexAuthoritativeHook, ...] = ()
        self._user_config_cache: dict[str, Any] | None = None

    def user_revision(self) -> str:
        """Return the revision guarding provider-native user plugin controls."""

        return compute_revision(read_text(self._user_config_path()))

    def mcp_policy(
        self,
        plugin_id: str,
        server_id: str,
    ) -> CodexPluginMcpPolicy:
        """Read one policy overlay, applying Codex's provider defaults."""

        config = self._read_user_config()
        plugins = _table(config.get("plugins"))
        plugin = _table(plugins.get(plugin_id))
        servers = _table(plugin.get("mcp_servers"))
        raw_policy = servers.get(server_id)
        if raw_policy is None:
            return CodexPluginMcpPolicy()
        if not isinstance(raw_policy, dict):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"errorCode": "marketplace.settings.plugin_mcp_policy_invalid"},
            )
        try:
            return CodexPluginMcpPolicy.model_validate(raw_policy)
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail={"errorCode": "marketplace.settings.plugin_mcp_policy_invalid"},
            ) from exc

    def mcp_effective(
        self,
        server: CodexPluginMcpServer,
        policy: CodexPluginMcpPolicy | None = None,
    ) -> bool:
        """Return whether a definition survives plugin and server policy gates."""

        resolved_policy = policy or self.mcp_policy(
            server.plugin.plugin_id,
            server.name,
        )
        return server.plugin.enabled and resolved_policy.enabled

    def update_mcp_policy(
        self,
        *,
        plugin_id: str,
        server_id: str,
        policy: CodexPluginMcpPolicy,
        revision: str,
    ) -> tuple[CodexPluginMcpPolicy, bool, str, int]:
        """Atomically replace one official plugin MCP policy and verify readback."""

        gate = get_marketplace_provider_gate()

        def mutate() -> tuple[CodexPluginMcpPolicy, bool, str]:
            server = self._require_mcp_server(plugin_id, server_id)
            path = self._user_config_path()
            with _write_lock(path):
                current_content = read_text(path)
                assert_revision(compute_revision(current_content), revision)
                config = self._parse_config(current_content)
                plugins = _table(config.get("plugins"))
                plugin = _table(plugins.get(plugin_id))
                servers = _table(plugin.get("mcp_servers"))
                native_policy = policy.model_dump(
                    by_alias=False,
                    exclude_none=True,
                    exclude_defaults=False,
                )
                if not native_policy.get("tools"):
                    native_policy.pop("tools", None)
                servers[server_id] = native_policy
                plugin["mcp_servers"] = servers
                plugins[plugin_id] = plugin
                config["plugins"] = plugins
                write_text_atomic(path, dump_toml(config))
                next_content = read_text(path)

            self._user_config_cache = None
            verified = self.mcp_policy(plugin_id, server_id)
            if verified != policy:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail={
                        "errorCode": ("marketplace.settings.plugin_mcp_policy_invalid")
                    },
                )
            self._plugin_resolver.clear_cache()
            return (
                verified,
                self.mcp_effective(server, verified),
                compute_revision(next_content),
            )

        result, generation = gate.run_settings_mutation("codex", mutate)
        verified, effective, next_revision = result
        return (
            verified,
            effective,
            next_revision,
            generation,
        )

    def hook_document_summary(
        self,
        document: CodexPluginHookDocument,
    ) -> CodexPluginHookControlSummary:
        """Read official trust state for one installed plugin hook document."""

        content = read_text(self._user_config_path())
        hooks = self._authoritative_hooks()
        controls = tuple(self._hook_controls(document, hooks))
        trust_state = _aggregate_trust_state(controls)
        trusted = bool(controls) and all(item.trusted for item in controls)
        return CodexPluginHookControlSummary(
            trust_state=trust_state,
            trusted=trusted,
            effective=(
                document.plugin.enabled
                and bool(controls)
                and all(item.enabled and item.trusted for item in controls)
            ),
            revision=compute_revision(content),
            controls=controls,
        )

    def plugin_hook_summary(
        self,
        plugin_id: str,
    ) -> CodexPluginHookControlSummary:
        """Aggregate hook trust across all documents contributed by one plugin."""

        documents = self._plugin_hook_documents(plugin_id)
        content = read_text(self._user_config_path())
        hooks = self._authoritative_hooks()
        source_paths = {
            document.source_path.resolve(strict=False) for document in documents
        }
        controls = tuple(
            self._hook_control(hook)
            for hook in hooks
            if hook.plugin_id == plugin_id and hook.source_path in source_paths
        )
        trust_state = _aggregate_trust_state(controls)
        package_enabled = all(document.plugin.enabled for document in documents)
        trusted = bool(controls) and all(item.trusted for item in controls)
        return CodexPluginHookControlSummary(
            trust_state=trust_state,
            trusted=trusted,
            effective=(
                package_enabled
                and bool(controls)
                and all(item.enabled and item.trusted for item in controls)
            ),
            revision=compute_revision(content),
            controls=controls,
        )

    def update_plugin_hook_trust(
        self,
        *,
        plugin_id: str,
        trusted: bool,
        revision: str,
    ) -> tuple[CodexPluginHookControlSummary, str, int]:
        """Approve or revoke every command hook contributed by one plugin."""

        gate = get_marketplace_provider_gate()

        def mutate() -> tuple[CodexPluginHookControlSummary, str]:
            documents = self._plugin_hook_documents(plugin_id)
            path = self._user_config_path()
            with _write_lock(path):
                current_content = read_text(path)
                assert_revision(compute_revision(current_content), revision)
                config = self._parse_config(current_content)
                hooks = _table(config.get("hooks"))
                states = _table(hooks.get("state"))
                authoritative = self._authoritative_hooks()
                source_paths = {
                    document.source_path.resolve(strict=False) for document in documents
                }
                controls = [
                    self._hook_control(hook)
                    for hook in authoritative
                    if hook.plugin_id == plugin_id and hook.source_path in source_paths
                ]
                if not controls:
                    raise HTTPException(
                        status.HTTP_400_BAD_REQUEST,
                        detail={
                            "errorCode": (
                                "marketplace.settings.plugin_hook_trust_not_supported"
                            )
                        },
                    )
                for control in controls:
                    state = _table(states.get(control.key))
                    if trusted:
                        state["trusted_hash"] = control.current_hash
                    else:
                        state.pop("trusted_hash", None)
                    if state:
                        states[control.key] = state
                    else:
                        states.pop(control.key, None)
                if states:
                    hooks["state"] = states
                else:
                    hooks.pop("state", None)
                if hooks:
                    config["hooks"] = hooks
                else:
                    config.pop("hooks", None)
                write_text_atomic(path, dump_toml(config))
                next_content = read_text(path)

            self._user_config_cache = None
            self._hooks_cache_key = None
            clear_codex_hooks_cache(self._resolver.workspace_root)
            verified = self.plugin_hook_summary(plugin_id)
            if verified.trusted != trusted:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail={
                        "errorCode": ("marketplace.settings.plugin_hook_trust_invalid")
                    },
                )
            self._plugin_resolver.clear_cache()
            return verified, compute_revision(next_content)

        result, generation = gate.run_settings_mutation("codex", mutate)
        verified, next_revision = result
        return verified, next_revision, generation

    def _require_mcp_server(
        self,
        plugin_id: str,
        server_id: str,
    ) -> CodexPluginMcpServer:
        matches = [
            server
            for server in self._plugin_resolver.mcp_servers()
            if server.plugin.plugin_id == plugin_id and server.name == server_id
        ]
        if len(matches) != 1:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"errorCode": "marketplace.settings.plugin_resource_not_found"},
            )
        return matches[0]

    def _plugin_hook_documents(
        self,
        plugin_id: str,
    ) -> list[CodexPluginHookDocument]:
        packages = {package.plugin_id for package in self._plugin_resolver.packages()}
        if plugin_id not in packages:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail={"errorCode": "marketplace.settings.plugin_resource_not_found"},
            )
        return [
            document
            for document in self._plugin_resolver.hook_documents()
            if document.plugin.plugin_id == plugin_id
        ]

    def _hook_controls(
        self,
        document: CodexPluginHookDocument,
        hooks: tuple[CodexAuthoritativeHook, ...],
    ) -> list[CodexPluginHookControl]:
        source_path = document.source_path.resolve(strict=False)
        return [
            self._hook_control(hook)
            for hook in hooks
            if hook.plugin_id == document.plugin.plugin_id
            and hook.source_path == source_path
        ]

    @staticmethod
    def _hook_control(hook: CodexAuthoritativeHook) -> CodexPluginHookControl:
        return CodexPluginHookControl(
            plugin_id=hook.plugin_id,
            key=hook.key,
            current_hash=hook.current_hash,
            enabled=hook.enabled,
            trust_state=hook.trust_status,  # type: ignore[arg-type]
        )

    def _user_config_path(self) -> Path:
        return self._resolver.resolve(CodexLayer.USER, CodexResource.CONFIG)

    def _authoritative_hooks(self) -> tuple[CodexAuthoritativeHook, ...]:
        key = (
            get_marketplace_provider_gate().generation("codex"),
            self.user_revision(),
        )
        if key != self._hooks_cache_key:
            self._hooks_cache = self._hooks_client.list_hooks(
                self._resolver.workspace_root
            )
            self._hooks_cache_key = key
        return self._hooks_cache

    def _read_user_config(self) -> dict[str, Any]:
        if self._user_config_cache is None:
            self._user_config_cache = self._parse_config(
                read_text(self._user_config_path())
            )
        return self._user_config_cache

    @staticmethod
    def _parse_config(content: str) -> dict[str, Any]:
        if not content:
            return {}
        try:
            parsed = parse_toml(content)
        except Exception as exc:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_TOML"},
            ) from exc
        return parsed if isinstance(parsed, dict) else {}


def _aggregate_trust_state(
    controls: tuple[CodexPluginHookControl, ...],
) -> CodexPluginHookTrustState:
    if not controls:
        return "untrusted"
    states = {item.trust_state for item in controls}
    if len(states) == 1:
        return next(iter(states))  # type: ignore[return-value]
    return "mixed"


def _table(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
