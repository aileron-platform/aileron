"""
Template AGENTS.md Service

處理模板的 AGENTS.md 檔案管理
"""

from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.services.template_base_service import TemplateBaseService


class TemplateAgentsMdService(TemplateBaseService):
    """AGENTS.md 檔案管理服務"""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_agents_md(self, template_id: str) -> str:
        """
        取得 AGENTS.md 檔案內容

        Args:
            template_id: 模板 ID

        Returns:
            AGENTS.md 檔案內容

        Raises:
            ValueError: 模板不存在
        """
        db_template = self._get_template(template_id)
        if not db_template:
            raise ValueError(f"Template not found: {template_id}")

        template_dir = self._resolve_template_dir(template_id)
        agents_md_path = template_dir / "agents.md"

        if not agents_md_path.exists():
            # 如果檔案不存在，返回空字串
            return ""

        return agents_md_path.read_text(encoding="utf-8")

    def update_agents_md(self, template_id: str, content: str) -> None:
        """
        更新 AGENTS.md 檔案內容

        Args:
            template_id: 模板 ID
            content: 新的檔案內容

        Raises:
            ValueError: 模板不存在
        """
        db_template = self._get_template(template_id)
        if not db_template:
            raise ValueError(f"Template not found: {template_id}")

        template_dir = self._resolve_template_dir(template_id)
        template_dir.mkdir(parents=True, exist_ok=True)
        agents_md_path = template_dir / "agents.md"

        # 寫入檔案（直接寫入，因為不需要返回 content model）
        agents_md_path.write_text(content, encoding="utf-8")

    def load_agents_md(self, template_dir: Path) -> Optional[str]:
        """
        載入 AGENTS.md 檔案內容（用於模板轉換）

        Args:
            template_dir: 模板目錄路徑

        Returns:
            AGENTS.md 檔案內容，如果不存在則返回 None
        """
        agents_md_path = template_dir / "agents.md"

        if not agents_md_path.exists():
            return None

        try:
            return agents_md_path.read_text(encoding="utf-8")
        except Exception:
            return None


__all__ = ["TemplateAgentsMdService"]
