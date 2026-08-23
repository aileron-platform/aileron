"""Validate Browser and Workspace lifecycle acceptance observations."""

from __future__ import annotations

import re
from typing import Any, NamedTuple

DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
FILE_DIGEST = re.compile(r"^[0-9a-f]{64}$")
SourceCommands = dict[str, list[list[str]]]

BROWSER_OBSERVATION_SECTIONS = frozenset(
    {
        "oidcWorkspace",
        "terminal",
        "http",
        "browser",
        "websocket",
        "workspaceLifecycle",
        "adminDisableLogin",
    }
)
_WORKSPACE_ID_SECTIONS = frozenset(
    {
        "oidcWorkspace",
        "terminal",
        "http",
        "browser",
        "websocket",
        "workspaceLifecycle",
    }
)


class BrowserObservationError(RuntimeError):
    """Raised when Browser acceptance observations fail closed."""


class BrowserObservationContext(NamedTuple):
    """Inputs shared by Browser observation policies."""

    commit: str
    workspace: dict[str, str] | None
    source_commands: SourceCommands | None


def _all_source_commands(
    source_commands: SourceCommands | None,
) -> list[list[str]]:
    if source_commands is None:
        return []
    return [command for commands in source_commands.values() for command in commands]


def _source_has_command(
    source_commands: SourceCommands | None, digest: Any, command: Any
) -> bool:
    return (
        isinstance(digest, str)
        and isinstance(command, list)
        and source_commands is not None
        and command in source_commands.get(digest, [])
    )


def _option_value(command: list[str], option: str) -> str | None:
    try:
        option_index = command.index(option)
    except ValueError:
        return None
    value_index = option_index + 1
    if value_index >= len(command):
        return None
    return command[value_index]


class BrowserObservationPolicy:
    """Own the complete Browser and Workspace lifecycle evidence policy."""

    def validate(
        self,
        section: str,
        observations: dict[str, Any],
        context: BrowserObservationContext,
    ) -> None:
        self._validate_workspace_context(section, context)
        if section == "oidcWorkspace":
            self._validate_oidc_workspace(observations, context)
        elif section == "terminal":
            self._validate_terminal(observations, context)
        elif section == "http":
            self._validate_http(observations, context)
        elif section == "browser":
            self._validate_browser(observations, context)
        elif section == "websocket":
            self._validate_websocket(observations, context)
        elif section == "workspaceLifecycle":
            self._validate_workspace_lifecycle(observations, context)
        elif section == "adminDisableLogin":
            self._validate_admin_disable_login(observations, context)
        else:
            raise BrowserObservationError(
                f"unknown browser observation section: {section}"
            )

    @staticmethod
    def _validate_workspace_context(
        section: str,
        context: BrowserObservationContext,
    ) -> None:
        if section not in _WORKSPACE_ID_SECTIONS:
            return
        workspace = context.workspace
        required_keys = {"id", "userSubject"} if section == "oidcWorkspace" else {"id"}
        if not isinstance(workspace, dict) or any(
            not isinstance(workspace.get(key), str) or not workspace[key]
            for key in required_keys
        ):
            raise BrowserObservationError(f"{section} workspace context is invalid")

    def _validate_oidc_workspace(
        self,
        observations: dict[str, Any],
        context: BrowserObservationContext,
    ) -> None:
        expected = {
            "flow": "authorization-code-pkce",
            "createdWorkspaceId": context.workspace["id"],
            "userSubject": context.workspace["userSubject"],
        }
        browser_probe = observations.get("browserProbe")
        if {key: observations.get(key) for key in expected} != expected or set(
            observations
        ) != {*expected, "browserProbe"}:
            raise BrowserObservationError(
                "OIDC user and new Workspace evidence is invalid"
            )
        self._validate_browser_probe(browser_probe, context)
        self._require_lifecycle_source(
            section="oidcWorkspace",
            context=context,
            error="OIDC Workspace browser lifecycle source is missing",
        )

    def _validate_terminal(
        self,
        observations: dict[str, Any],
        context: BrowserObservationContext,
    ) -> None:
        expected = {"sessionId", "roundTrip"}
        browser_probe = observations.get("browserProbe")
        if (
            set(observations) != {*expected, "browserProbe"}
            or not observations.get("sessionId")
            or observations.get("roundTrip") != "verified"
        ):
            raise BrowserObservationError("Terminal evidence is incomplete")
        self._validate_browser_probe(browser_probe, context)
        self._require_lifecycle_source(
            section="terminal",
            context=context,
            workspace_id=context.workspace["id"],
            error="Terminal browser lifecycle source is missing",
        )

    def _validate_http(
        self,
        observations: dict[str, Any],
        context: BrowserObservationContext,
    ) -> None:
        expected = {"runtime": 200, "browser": 200, "canvas": 200}
        browser_probe = observations.get("browserProbe")
        if {key: observations.get(key) for key in expected} != expected or set(
            observations
        ) != {*expected, "browserProbe"}:
            raise BrowserObservationError(
                "Runtime, Browser, and Canvas HTTP evidence is incomplete"
            )
        self._validate_browser_probe(browser_probe, context)
        self._require_lifecycle_source(
            section="http",
            context=context,
            workspace_id=context.workspace["id"],
            error="HTTP browser lifecycle source is missing",
        )

    def _validate_browser(
        self,
        observations: dict[str, Any],
        context: BrowserObservationContext,
    ) -> None:
        browser_probe = observations.get("browserProbe")
        if (
            set(observations)
            != {
                "route",
                "websocket",
                "webrtc",
                "videoTrack",
                "dataChannel",
                "videoWidth",
                "videoHeight",
                "browserProbe",
            }
            or observations.get("route")
            != f"/workspaces/{context.workspace['id']}/browser"
            or observations.get("websocket") != "open"
            or observations.get("webrtc") != "connected"
            or observations.get("videoTrack") != "live"
            or observations.get("dataChannel") != "open"
            or any(
                not isinstance(observations.get(field), int)
                or isinstance(observations.get(field), bool)
                or observations[field] <= 0
                for field in ("videoWidth", "videoHeight")
            )
        ):
            raise BrowserObservationError(
                "Browser UI WebSocket, WebRTC, video, or data-channel evidence "
                "is incomplete"
            )
        self._validate_browser_probe(browser_probe, context)
        self._require_lifecycle_source(
            section="browser",
            context=context,
            workspace_id=context.workspace["id"],
            error="Browser UI lifecycle source is missing",
        )

    def _validate_websocket(
        self,
        observations: dict[str, Any],
        context: BrowserObservationContext,
    ) -> None:
        expected = {"handshakeStatus", "messagesObserved"}
        browser_probe = observations.get("browserProbe")
        if (
            set(observations) != {*expected, "browserProbe"}
            or observations.get("handshakeStatus") != 101
            or observations.get("messagesObserved", 0) < 1
        ):
            raise BrowserObservationError("WebSocket evidence is incomplete")
        self._validate_browser_probe(browser_probe, context)
        self._require_lifecycle_source(
            section="websocket",
            context=context,
            workspace_id=context.workspace["id"],
            error="WebSocket browser lifecycle source is missing",
        )

    def _validate_workspace_lifecycle(
        self,
        observations: dict[str, Any],
        context: BrowserObservationContext,
    ) -> None:
        expected = {
            "componentsRestarted": ["runtime", "browser", "canvas"],
            "stopObserved": "stopped",
            "startObserved": "ready",
        }
        browser_probe = observations.get("browserProbe")
        if observations != {**expected, "browserProbe": browser_probe}:
            raise BrowserObservationError("Workspace lifecycle evidence is incomplete")
        self._validate_browser_probe(browser_probe, context)
        self._require_lifecycle_source(
            section="workspaceLifecycle",
            context=context,
            workspace_id=context.workspace["id"],
            error="Workspace lifecycle browser source is missing",
        )

    def _validate_admin_disable_login(
        self,
        observations: dict[str, Any],
        context: BrowserObservationContext,
    ) -> None:
        expected = {
            "initialLogin": "accepted",
            "disabledLogin": "rejected",
            "restoration": "reEnabled",
            "restoredLogin": "accepted",
        }
        expected_platform_admin = {
            "platformRole": "admin",
            "requiredOperations": "verified",
            "adminUsersStatus": 200,
            "marketplaceCatalogStatus": 200,
        }
        browser_probe = observations.get("browserProbe")
        if observations != {
            **expected,
            "platformAdmin": expected_platform_admin,
            "browserProbe": browser_probe,
        }:
            raise BrowserObservationError(
                "temporary native user disable and restoration did not fail closed"
            )
        self._validate_browser_probe(browser_probe, context)
        self._require_lifecycle_source(
            section="adminDisableLogin",
            context=context,
            error="disabled login browser lifecycle source is missing",
        )

    def _validate_browser_probe(
        self,
        browser_probe: Any,
        context: BrowserObservationContext,
    ) -> None:
        source_commands = context.source_commands
        if (
            not isinstance(browser_probe, dict)
            or set(browser_probe)
            != {
                "imageId",
                "trackedScriptSha256",
                "imageScriptSha256",
                "exactSourceMatch",
            }
            or not isinstance(browser_probe["imageId"], str)
            or DIGEST.fullmatch(browser_probe["imageId"]) is None
            or FILE_DIGEST.fullmatch(browser_probe.get("trackedScriptSha256", ""))
            is None
            or FILE_DIGEST.fullmatch(browser_probe.get("imageScriptSha256", "")) is None
            or browser_probe["trackedScriptSha256"]
            != browser_probe["imageScriptSha256"]
            or browser_probe["exactSourceMatch"] is not True
            or source_commands is None
        ):
            raise BrowserObservationError("browser probe provenance is invalid")
        commands = _all_source_commands(source_commands)
        build_commands = [
            command
            for command in commands
            if command[:2] == ["docker", "build"] and "--tag" in command
        ]
        if len(build_commands) != 1:
            raise BrowserObservationError(
                "browser probe full-SHA image build is missing"
            )
        build_command = build_commands[0]
        image_tag = _option_value(build_command, "--tag")
        revision_label = _option_value(build_command, "--label")
        image_tag_pattern = (
            "ailerondocker/workspace-ui-playwright:"
            rf"{re.escape(context.commit)}-[0-9a-f]{{12}}"
        )
        if (
            not isinstance(image_tag, str)
            or re.fullmatch(image_tag_pattern, image_tag) is None
            or revision_label != f"org.opencontainers.image.revision={context.commit}"
        ):
            raise BrowserObservationError(
                "browser probe full-SHA image build is missing"
            )
        inspect_command = [
            "docker",
            "image",
            "inspect",
            (
                "--format={{.Id}}\t{{index .Config.Labels "
                '"org.opencontainers.image.revision"}}'
            ),
            image_tag,
        ]
        if inspect_command not in commands:
            raise BrowserObservationError(
                "browser probe image identity source is missing"
            )
        shared_tag_command = [
            "docker",
            "image",
            "tag",
            browser_probe["imageId"],
            f"ailerondocker/workspace-ui-playwright:{context.commit}",
        ]
        unique_tag_cleanup_command = [
            "docker",
            "image",
            "rm",
            "--force",
            image_tag,
        ]
        if (
            shared_tag_command not in commands
            or unique_tag_cleanup_command not in commands
        ):
            raise BrowserObservationError(
                "browser probe reusable image tag or unique tag cleanup is missing"
            )
        tracked_command = [
            "git",
            "show",
            f"{context.commit}:frontend/e2e/acceptance.mjs",
        ]
        image_script_command = [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "node",
            browser_probe["imageId"],
            "-e",
            (
                'process.stdout.write(require("node:fs").readFileSync('
                '"/app/e2e/acceptance.mjs"))'
            ),
        ]
        if not _source_has_command(
            source_commands,
            browser_probe["trackedScriptSha256"],
            tracked_command,
        ) or not _source_has_command(
            source_commands,
            browser_probe["imageScriptSha256"],
            image_script_command,
        ):
            raise BrowserObservationError(
                "browser probe exact source evidence is missing"
            )
        if not any(
            command[:3] == ["docker", "run", "--rm"]
            and browser_probe["imageId"] in command
            and "/app/e2e/acceptance.mjs" in " ".join(command)
            and "--section" in command
            for command in commands
        ):
            raise BrowserObservationError("browser probe digest-pinned run is missing")

    def _require_lifecycle_source(
        self,
        *,
        section: str,
        context: BrowserObservationContext,
        error: str,
        workspace_id: str | None = None,
    ) -> None:
        if not any(
            self._is_lifecycle_command(
                command,
                section,
                workspace_id=workspace_id,
            )
            for command in _all_source_commands(context.source_commands)
        ):
            raise BrowserObservationError(error)

    @staticmethod
    def _is_lifecycle_command(
        command: list[str], section: str, *, workspace_id: str | None = None
    ) -> bool:
        recognized = (
            command[:3] == ["docker", "run", "--rm"]
            and any(
                "/app/e2e/acceptance.mjs" in argument for argument in command
            )
            and _option_value(command, "--section") == section
        )
        if not recognized or workspace_id is None:
            return recognized
        return _option_value(command, "--workspace-id") == workspace_id


BROWSER_OBSERVATION_POLICY = BrowserObservationPolicy()
