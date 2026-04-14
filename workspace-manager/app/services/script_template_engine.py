"""腳本模板引擎，負責渲染 runtime 相關腳本"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, TemplateNotFound


class ScriptTemplateEngine:
    """簡化腳本模板渲染的封裝。"""

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
        """回傳模板根目錄。"""

        return self._template_root

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """渲染指定模板並回傳字串內容。"""

        try:
            template = self._env.get_template(template_name)
        except TemplateNotFound as exc:  # pragma: no cover - 需顯性錯誤
            available = ", ".join(sorted(self._env.list_templates()))
            raise ValueError(
                f"找不到模板 {template_name}，可用模板：{available or '無'}"
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
        """渲染模板並寫入檔案。"""

        destination.parent.mkdir(parents=True, exist_ok=True)
        content = self.render(template_name, context)
        destination.write_text(content, encoding="utf-8")
        if executable:
            destination.chmod(0o755)
        return destination


__all__ = ["ScriptTemplateEngine"]
