"""Script template engine, responsible for rendering runtime related scripts"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound


class ScriptTemplateEngine:
    """Simplified wrapper for script template rendering."""

    def __init__(self, template_root: Path) -> None:
        self._template_root = template_root
        self._env = Environment(
            loader=FileSystemLoader(str(template_root)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    @property
    def template_root(self) -> Path:
        """Return template root directory."""

        return self._template_root

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render specified template and return string content."""

        try:
            template = self._env.get_template(template_name)
        except TemplateNotFound as exc:  # pragma: no cover - Explicit error needed
            available = ", ".join(sorted(self._env.list_templates()))
            raise ValueError(
                f"Template {template_name} not found, available templates: {available or 'none'}"
            ) from exc
        return template.render(**context)

    def render_to_file(
        self,
        template_name: str,
        destination: Path,
        context: dict[str, Any],
        *,
        executable: bool = False,
    ) -> Path:
        """Render template and write to file."""

        destination.parent.mkdir(parents=True, exist_ok=True)
        content = self.render(template_name, context)
        destination.write_text(content, encoding="utf-8")
        if executable:
            destination.chmod(0o755)
        return destination


__all__ = ["ScriptTemplateEngine"]
