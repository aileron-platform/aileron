"""Shared pytest fixtures and import-path setup for ppt-design-flow tests."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SKILL_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = SKILL_ROOT / "assets"
SCRIPTS_DIR = SKILL_ROOT / "scripts"

# Allow tests to import ``canvas_protocol`` / ``stage_state`` directly.
sys.path.insert(0, str(ASSETS_DIR))


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Return an isolated workspace directory rooted at ``tmp_path``."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws


@pytest.fixture
def session_id() -> str:
    return "2026-05-19-test-session"


@pytest.fixture
def skill_root() -> Path:
    return SKILL_ROOT


@pytest.fixture
def stage_cli() -> Path:
    return SCRIPTS_DIR / "stage.py"


@pytest.fixture
def build_cli() -> Path:
    return ASSETS_DIR / "canvas" / "build.py"


@pytest.fixture
def build_pptx_cli() -> Path:
    return SCRIPTS_DIR / "build_pptx_deck.py"


@pytest.fixture
def build_html_cli() -> Path:
    return SCRIPTS_DIR / "build_html_deck.py"


@pytest.fixture
def adopt_imagegen_cli() -> Path:
    return SCRIPTS_DIR / "adopt_imagegen_output.py"


@pytest.fixture
def find_imagegen_cli() -> Path:
    return SCRIPTS_DIR / "find_imagegen_output.py"
