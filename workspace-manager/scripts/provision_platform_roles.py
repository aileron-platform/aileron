"""Validate the local platform-role vocabulary before bootstrap."""

from app.modules.identity.platform_role import PLATFORM_ROLES


def main() -> int:
    """Return success when the provider-neutral role vocabulary is available."""
    if {role.value for role in PLATFORM_ROLES} != {"admin", "member"}:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
