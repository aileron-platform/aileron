from __future__ import annotations

import json
from pathlib import Path

from aileron_marketplace_core import (
    PluginReleaseIdentity,
    extract_user_copy_source_profile,
)

from app.modules.cli_settings.user_scope.paths import UserScopePathResolver
from app.modules.cli_settings.user_scope.planner import (
    UserCopyInventory,
    UserCopyMaterializationPlan,
    UserCopyPlanner,
)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_full_codex_package(
    package_root: Path,
    *,
    use_payload_placeholder: bool = True,
) -> None:
    command = "${CODEX_PLUGIN_ROOT}/bin/server" if use_payload_placeholder else "server"
    write_text(
        package_root / ".codex-plugin" / "plugin.json",
        json.dumps(
            {
                "name": "demo",
                "mcpServers": {
                    "local": {
                        "command": command,
                        "args": ["--stdio"],
                    }
                },
                "hooks": {
                    "SessionStart": [
                        {
                            "command": "echo ready",
                        }
                    ]
                },
            }
        ),
    )
    write_text(package_root / "AGENTS.md", "# Marketplace instructions\n")
    write_text(
        package_root / "skills" / "review" / "SKILL.md",
        "# Review skill\n",
    )
    write_text(
        package_root / "agents" / "reviewer.toml",
        'name = "reviewer"\n',
    )
    write_text(
        package_root / "prompts" / "nested" / "review.md",
        "# Review prompt\n",
    )
    write_text(
        package_root / "rules" / "safe.rules",
        "allow prefix git\n",
    )
    write_text(package_root / "bin" / "server", "#!/bin/sh\nexit 0\n")
    (package_root / "bin" / "server").chmod(0o755)


def plan_codex_package(
    package_root: Path,
    runtime_home: Path,
    *,
    package_id: str = "demo",
    inventory: UserCopyInventory | None = None,
) -> UserCopyMaterializationPlan:
    runtime_home.mkdir(parents=True, exist_ok=True)
    profile = extract_user_copy_source_profile(
        "codex-native",
        package_root,
        release=PluginReleaseIdentity(
            catalog_plugin_id=f"test/{package_id}",
            revision="a" * 64,
        ),
    )
    planner = UserCopyPlanner(
        package_id=package_id,
        release_revision="a" * 64,
        paths=UserScopePathResolver(user_home=runtime_home),
    )
    return planner.plan_source_profile(
        profile,
        target_client="codex",
        package_root=package_root,
        inventory=inventory or UserCopyInventory(complete=True),
    )
