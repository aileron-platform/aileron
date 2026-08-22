from pathlib import Path


def test_runtime_image_does_not_persist_global_safe_directory_entries() -> None:
    dockerfile = Path(__file__).parents[4] / "Dockerfile"

    assert "git config --global --add safe.directory" not in dockerfile.read_text(
        encoding="utf-8"
    )


def test_agent_defaults_are_readable_by_the_runtime_user() -> None:
    dockerfile = Path(__file__).parents[4] / "Dockerfile"
    dockerfile_text = dockerfile.read_text(encoding="utf-8")
    readable_agent_defaults = (
        "RUN find /opt/aileron/agent-defaults -type d -exec chmod a+rx {} + \\\n"
        "    && find /opt/aileron/agent-defaults -type f -exec chmod a+r {} +"
    )

    assert dockerfile_text.count(readable_agent_defaults) == 3
