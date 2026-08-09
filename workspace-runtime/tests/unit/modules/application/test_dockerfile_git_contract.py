from pathlib import Path


def test_runtime_image_does_not_persist_global_safe_directory_entries() -> None:
    dockerfile = Path(__file__).parents[4] / "Dockerfile"

    assert "git config --global --add safe.directory" not in dockerfile.read_text(
        encoding="utf-8"
    )
