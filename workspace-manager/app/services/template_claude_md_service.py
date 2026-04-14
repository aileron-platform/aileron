"""
Template Claude.md Service

處理模板的 Claude.md 檔案管理
"""

from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.services.template_base_service import TemplateBaseService


class TemplateClaudeMdService(TemplateBaseService):
    """Claude.md 檔案管理服務"""

    def __init__(self, db: Session) -> None:
        super().__init__(db)

    def get_claude_md(self, template_id: str) -> str:
        """
        取得 Claude.md 檔案內容

        Args:
            template_id: 模板 ID

        Returns:
            Claude.md 檔案內容

        Raises:
            ValueError: 模板不存在
        """
        db_template = self._get_template(template_id)
        if not db_template:
            raise ValueError(f"Template not found: {template_id}")

        template_dir = self._get_template_dir(template_id)
        claude_md_path = template_dir / "Claude.md"

        if not claude_md_path.exists():
            # 如果檔案不存在，返回空字串
            return ""

        return claude_md_path.read_text(encoding="utf-8")

    def update_claude_md(self, template_id: str, content: str) -> None:
        """
        更新 Claude.md 檔案內容

        Args:
            template_id: 模板 ID
            content: 新的檔案內容

        Raises:
            ValueError: 模板不存在
        """
        db_template = self._get_template(template_id)
        if not db_template:
            raise ValueError(f"Template not found: {template_id}")

        template_dir = self._get_template_dir(template_id)
        claude_md_path = template_dir / "Claude.md"

        # 寫入檔案（直接寫入，因為不需要返回 content model）
        claude_md_path.write_text(content, encoding="utf-8")

    def load_claude_md(self, template_dir: Path) -> Optional[str]:
        """
        載入 Claude.md 檔案內容（用於模板轉換）

        Args:
            template_dir: 模板目錄路徑

        Returns:
            Claude.md 檔案內容，如果不存在則返回 None
        """
        claude_md_path = template_dir / "Claude.md"

        if not claude_md_path.exists():
            return None

        try:
            return claude_md_path.read_text(encoding="utf-8")
        except Exception:
            return None


__all__ = ["TemplateClaudeMdService"]

