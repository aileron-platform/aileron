"""模板服務基礎類別 - 提供共用的輔助方法"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db.models import Template as TemplateDB

logger = logging.getLogger(__name__)


class TemplateBaseService:
    """模板服務基礎類別 - 提供共用的路徑管理和驗證方法"""

    MAX_FILE_SIZE_BYTES = 1024 * 1024  # SlashCommand/SubAgent 檔案限制 1MB
    MAX_TEMPLATE_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 模板檔案限制 10MB
    MAX_UPLOAD_FILES = 50  # 單次最多上傳 50 個檔案
    ALLOWED_EXTENSIONS = {
        '.md', '.txt', '.json', '.yaml', '.yml', '.py', '.js', '.ts',
        '.jsx', '.tsx', '.css', '.scss', '.html', '.xml', '.sh',
        '.dockerfile', '.gitignore', '.env.example', '.toml', '.ini',
        '.cfg', '.conf', '.properties', '.sql', '.graphql', '.proto'
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        # 動態獲取 settings，確保在測試環境中使用正確的配置
        settings = get_settings()
        self.storage_path = Path(settings.TEMPLATE_STORAGE_PATH)
        # 確保儲存目錄存在
        self.storage_path.mkdir(parents=True, exist_ok=True)
        # 確保 plugins 目錄存在
        (self.storage_path / "plugins").mkdir(parents=True, exist_ok=True)

    def _get_template_dir(self, template_id: str) -> Path:
        """取得模板目錄路徑（包含 plugins 前綴）"""
        return self.storage_path / "plugins" / template_id

    def _get_plugin_json_path(self, template_id: str) -> Path:
        """取得 plugin.json 檔案路徑"""
        return self._get_template_dir(template_id) / ".claude-plugin" / "plugin.json"

    def _get_template(self, template_id: str) -> Optional[TemplateDB]:
        """取得模板資料"""
        return self.db.query(TemplateDB).filter(TemplateDB.id == template_id).first()

    def _response_template_not_found(self, response_cls, *, include_list_data: bool = False):
        """建立模板不存在的標準回應"""
        payload = {"success": False, "error": "Template not found"}
        if include_list_data:
            payload["data"] = []
        return response_cls(**payload)

    def _validate_template_and_filename(
        self,
        template_id: str,
        response_cls,
        *,
        file_name: Optional[str] = None,
        include_list_data: bool = False
    ):
        """模板與檔名檢查，若失敗直接回傳對應回應"""
        db_template = self._get_template(template_id)
        if not db_template:
            return None, self._response_template_not_found(response_cls, include_list_data=include_list_data)

        if file_name is not None and not self._validate_filename(file_name):
            return None, response_cls(success=False, error="Invalid filename")

        return db_template, None

    def _ensure_directory(self, template_id: str, subdir: str) -> Tuple[Path, bool]:
        """確保模板子目錄存在，回傳目錄路徑與是否新建"""
        directory = self._get_template_dir(template_id) / subdir
        created = False
        if not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            created = True
        return directory, created

    def _list_markdown_files(self, directory: Path, file_model_cls):
        """列出指定目錄下的 Markdown 檔案資訊"""
        files = []
        for file_path in directory.glob("*.md"):
            stat = file_path.stat()
            files.append(
                file_model_cls(
                    file_name=file_path.name,
                    size=stat.st_size,
                    last_modified=datetime.fromtimestamp(stat.st_mtime),
                )
            )
        return files

    def _read_file_content(self, file_path: Path, content_model_cls):
        """讀取檔案並建立內容模型"""
        content = file_path.read_text(encoding="utf-8")
        stat = file_path.stat()
        return content_model_cls(
            file_name=file_path.name,
            content=content,
            size=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime),
        )

    def _write_file_with_stats(self, file_path: Path, content: str, content_model_cls):
        """寫入檔案並回傳內容模型或錯誤訊息"""
        if len(content.encode("utf-8")) > self.MAX_FILE_SIZE_BYTES:
            return None, "File content too large (max 1MB)"

        file_path.write_text(content, encoding="utf-8")
        stat = file_path.stat()
        return (
            content_model_cls(
                file_name=file_path.name,
                content=content,
                size=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
            ),
            None,
        )

    def _normalize_file_name(self, file_name: str) -> str:
        """標準化檔案名稱，自動補上 .md 副檔名（如果沒有）"""
        if file_name.endswith(".md"):
            return file_name
        return f"{file_name}.md"

    def _validate_filename(self, filename: str) -> bool:
        """驗證檔案名稱是否合法"""
        # 檢查是否為空或只有點號
        if not filename or filename == '.' or filename == '..':
            return False

        # 檢查是否包含非法字符
        illegal_chars = r'[<>:"/\\|?*\x00-\x1f]'
        if re.search(illegal_chars, filename):
            return False

        # 檢查副檔名是否在允許列表中（轉換為小寫比較）
        file_ext = Path(filename).suffix.lower()
        if file_ext and file_ext not in self.ALLOWED_EXTENSIONS:
            return False

        return True

    def _validate_file_path(self, path: str) -> bool:
        """驗證檔案路徑"""
        if not path or path.startswith('/') or path.startswith('..'):
            return False

        # 檢查非法字符
        illegal_chars = r'[<>:"|?*\x00-\x1f]'
        if re.search(illegal_chars, path):
            return False

        return True

    def _is_safe_path(self, path: Path, base_path: Path) -> bool:
        """檢查路徑是否在基礎路徑內(防止路徑遍歷攻擊)"""
        try:
            path.resolve().relative_to(base_path.resolve())
            return True
        except ValueError:
            return False

    def _validate_template_id(self, template_id: str) -> bool:
        """驗證模板 ID 格式（kebab-case）"""
        pattern = r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$'
        return bool(re.match(pattern, template_id))

    def _update_plugin_json(self, template_id: str) -> None:
        """更新 plugin.json 中的 commands 和 agents 路徑"""
        template_dir = self._get_template_dir(template_id)
        plugin_file = self._get_plugin_json_path(template_id)

        if not plugin_file.exists():
            logger.warning(f"plugin.json 不存在: {plugin_file}")
            return

        try:
            # 讀取現有的 plugin.json
            plugin_data = json.loads(plugin_file.read_text(encoding="utf-8"))

            # 掃描 commands 目錄
            commands_dir = template_dir / "commands"
            command_paths = []
            if commands_dir.exists():
                for item in commands_dir.rglob("*"):
                    if item.is_file() and item.suffix == ".md":
                        # 計算相對路徑
                        rel_path = item.relative_to(template_dir)
                        command_paths.append(f"./{rel_path.as_posix()}")

            # 掃描 agents 目錄
            agents_dir = template_dir / "agents"
            agent_paths = []
            if agents_dir.exists():
                for item in agents_dir.rglob("*"):
                    if item.is_file() and item.suffix == ".md":
                        # 計算相對路徑
                        rel_path = item.relative_to(template_dir)
                        agent_paths.append(f"./{rel_path.as_posix()}")

            # 更新 plugin.json
            plugin_data["commands"] = sorted(command_paths)
            plugin_data["agents"] = sorted(agent_paths)

            # 寫回檔案
            plugin_file.write_text(
                json.dumps(plugin_data, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )

            logger.info(f"已更新 plugin.json: {len(command_paths)} commands, {len(agent_paths)} agents")

        except Exception as e:
            logger.error(f"更新 plugin.json 失敗: {e}")

    def _extract_yaml_description(self, content: str) -> str:
        """從 Markdown 檔案的 YAML front matter 中提取 description"""
        description = ""  # 預設為空

        # 檢查是否有 YAML front matter
        if content.startswith('---\n'):
            # 找到 YAML front matter 結束位置
            front_matter_end = content.find('\n---', 4)
            if front_matter_end != -1:
                yaml_content = content[4:front_matter_end]
                # 尋找 description 欄位
                for line in yaml_content.split('\n'):
                    line = line.strip()
                    if line.startswith('description:'):
                        # 提取 description 值
                        desc_value = line[12:].strip()
                        # 移除引號（如果有的話）
                        if (desc_value.startswith('"') and desc_value.endswith('"')) or \
                           (desc_value.startswith("'") and desc_value.endswith("'")):
                            desc_value = desc_value[1:-1].strip()
                        if desc_value:
                            description = desc_value
                        break

        return description


__all__ = ["TemplateBaseService"]

