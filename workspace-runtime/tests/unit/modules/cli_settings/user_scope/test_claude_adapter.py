from pathlib import Path

import pytest

from app.modules.cli_settings.user_scope.adapter import (
    CoreProfileResource,
    UserCopyAdapterError,
)
from app.modules.cli_settings.user_scope.claude import ClaudeUserCopyAdapter
from app.modules.cli_settings.user_scope.paths import UserScopePathResolver


def _skill_resource(
    *,
    source_kind: str,
    source_locator: str,
    resource_id: str = "review",
) -> CoreProfileResource:
    return CoreProfileResource(
        resource_type="skill",
        resource_id=resource_id,
        source_kind=source_kind,
        source_locator=source_locator,
        target_resource="skills",
        copy_semantics="create-directory",
        relative_target=resource_id,
        json_pointer=None,
    )


def test_explicit_skill_selector_maps_arbitrary_safe_source_to_user_skill(
    tmp_path: Path,
) -> None:
    adapter = ClaudeUserCopyAdapter(paths=UserScopePathResolver(user_home=tmp_path))

    target = adapter.resolve_target(
        _skill_resource(
            source_kind="plugin-component",
            source_locator="components/skills/review",
        ),
        source_value=None,
    )

    assert target.runtime_path == tmp_path / ".claude" / "skills" / "review"
    assert target.logical_locator == "~/.claude/skills/review"


@pytest.mark.parametrize(
    ("source_kind", "source_locator"),
    [
        ("copy-convention", "components/skills/review"),
        ("plugin-component", "../review"),
        ("plugin-component", "components/skills/other"),
    ],
)
def test_skill_selector_rejects_invalid_source_contract(
    tmp_path: Path,
    source_kind: str,
    source_locator: str,
) -> None:
    adapter = ClaudeUserCopyAdapter(paths=UserScopePathResolver(user_home=tmp_path))

    with pytest.raises(UserCopyAdapterError):
        adapter.resolve_target(
            _skill_resource(
                source_kind=source_kind,
                source_locator=source_locator,
            ),
            source_value=None,
        )
