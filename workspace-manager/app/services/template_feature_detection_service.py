"""模板 Feature 偵測與索引服務"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models import Template as TemplateDB
from app.db.models import TemplateFeature, TemplateFeatureMapping
from app.services.template_base_service import TemplateBaseService

logger = logging.getLogger(__name__)


class FeatureIndexResult:
    """Feature 索引結果"""
    def __init__(
        self,
        success: bool,
        template_id: str,
        detected_features: List[str],
        indexed_count: int,
        failed_count: int,
        message: Optional[str] = None
    ):
        self.success = success
        self.template_id = template_id
        self.detected_features = detected_features
        self.indexed_count = indexed_count
        self.failed_count = failed_count
        self.message = message


class TemplateFeatureDetectionService:
    """模板 Feature 偵測與索引服務

    負責：
    1. 分析模板目錄結構，偵測 Feature 存在
    2. 驗證 Feature 有效性（如 JSON 檔案格式）
    3. 與資料庫同步 Feature 索引
    4. 提供 Feature 查詢接口
    """

    # Feature 偵測規則定義
    FEATURE_DETECTION_RULES = {
        'mcp': {
            'path': '.claude-plugin/mcp.json',
            'type': 'file',
            'validator': '_validate_mcp_json'
        },
        'slashCommands': {
            'path': 'commands',
            'type': 'directory',
            'validator': '_has_valid_md_files'
        },
        'hooks': {
            'path': '.claude-plugin/hooks.json',
            'type': 'file',
            'validator': '_validate_hooks_json'
        },
        'claudeMd': {
            'path': 'CLAUDE.md',
            'type': 'file',
            'validator': '_validate_claude_md'
        },
        'subAgents': {
            'path': 'agents',
            'type': 'directory',
            'validator': '_has_valid_md_files'
        },
        'outputStyles': {
            'path': 'output-styles',
            'type': 'directory',
            'validator': '_has_valid_md_files'
        },
        'scripts': {
            'path': 'scripts',
            'type': 'directory',
            'validator': '_has_valid_files_in_directory'
        },
        'skills': {
            'path': 'skills',
            'type': 'directory',
            'validator': '_has_valid_files_in_directory'
        }
    }

    # 需要忽略的檔案
    IGNORE_FILES = {'.gitkeep', '.git', '__pycache__', '.DS_Store', 'Thumbs.db'}

    def __init__(self, db: Session, template_base_service: TemplateBaseService):
        """初始化服務

        Args:
            db: 資料庫 session
            template_base_service: 模板基礎服務，用於取得模板路徑等資訊
        """
        self.db = db
        self.template_base_service = template_base_service

    def detect_features(self, template_id: str) -> Dict[str, bool]:
        """偵測模板的所有 Feature 存在狀態

        Args:
            template_id: 模板 ID

        Returns:
            Dict[str, bool]: Feature key -> 是否存在的映射
        """
        template_dir = self.template_base_service._get_template_dir(template_id)

        if not template_dir.exists():
            logger.warning(f"Template directory not found: {template_dir}")
            return {}

        detected = {}

        for feature_key, rule in self.FEATURE_DETECTION_RULES.items():
            path = template_dir / rule['path']
            validator_method = getattr(self, rule['validator'])

            try:
                if rule['type'] == 'file':
                    detected[feature_key] = path.is_file() and validator_method(path)
                elif rule['type'] == 'directory':
                    detected[feature_key] = path.is_dir() and validator_method(path)
                else:
                    detected[feature_key] = False

                if detected[feature_key]:
                    logger.debug(f"Feature '{feature_key}' detected for template {template_id}")
            except Exception as e:
                logger.error(f"Error detecting feature '{feature_key}' for template {template_id}: {e}", exc_info=True)
                detected[feature_key] = False

        return detected

    def index_features(self, template_id: str) -> FeatureIndexResult:
        """分析並索引 Feature 到資料庫

        Args:
            template_id: 模板 ID

        Returns:
            FeatureIndexResult: 索引結果
        """
        try:
            # 檢查模板是否存在
            template = self.template_base_service._get_template(template_id)
            if not template:
                return FeatureIndexResult(
                    success=False,
                    template_id=template_id,
                    detected_features=[],
                    indexed_count=0,
                    failed_count=0,
                    message=f"Template '{template_id}' not found"
                )

            # 偵測 Feature
            detected_features = self.detect_features(template_id)
            detected_feature_keys = [key for key, exists in detected_features.items() if exists]

            logger.info(f"Detected features for template {template_id}: {detected_feature_keys}")

            # 刪除舊的 mapping
            self.db.query(TemplateFeatureMapping).filter(
                TemplateFeatureMapping.template_id == template_id
            ).delete()

            # 建立新的 mapping
            indexed_count = 0
            failed_count = 0

            for feature_key in detected_feature_keys:
                try:
                    # 查詢 Feature ID
                    feature = self.db.query(TemplateFeature).filter(
                        TemplateFeature.feature_key == feature_key,
                        TemplateFeature.is_active == True
                    ).first()

                    if not feature:
                        logger.warning(f"Feature '{feature_key}' not found in database")
                        failed_count += 1
                        continue

                    # 建立新的 mapping
                    mapping = TemplateFeatureMapping(
                        id=str(uuid4()),
                        template_id=template_id,
                        feature_id=feature.id,
                        is_enabled=True,
                        indexed_at=datetime.utcnow()
                    )
                    self.db.add(mapping)
                    indexed_count += 1

                except Exception as e:
                    logger.error(f"Failed to index feature '{feature_key}': {e}", exc_info=True)
                    failed_count += 1

            # 提交變更
            self.db.commit()

            message = f"Successfully indexed {indexed_count} features for template {template_id}"
            if failed_count > 0:
                message += f" ({failed_count} failed)"

            logger.info(message)

            return FeatureIndexResult(
                success=True,
                template_id=template_id,
                detected_features=detected_feature_keys,
                indexed_count=indexed_count,
                failed_count=failed_count,
                message=message
            )

        except Exception as e:
            self.db.rollback()
            error_msg = f"Feature indexing failed for template {template_id}: {e}"
            logger.error(error_msg, exc_info=True)
            return FeatureIndexResult(
                success=False,
                template_id=template_id,
                detected_features=[],
                indexed_count=0,
                failed_count=0,
                message=error_msg
            )

    def get_template_features(self, template_id: str) -> List[str]:
        """查詢模板已索引的 Feature

        Args:
            template_id: 模板 ID

        Returns:
            List[str]: Feature key 列表
        """
        try:
            mappings = self.db.query(TemplateFeatureMapping).join(
                TemplateFeature,
                TemplateFeatureMapping.feature_id == TemplateFeature.id
            ).filter(
                TemplateFeatureMapping.template_id == template_id,
                TemplateFeatureMapping.is_enabled == True,
                TemplateFeature.is_active == True
            ).all()

            features = []
            for mapping in mappings:
                feature = self.db.query(TemplateFeature).filter(
                    TemplateFeature.id == mapping.feature_id
                ).first()
                if feature:
                    features.append(feature.feature_key)

            return features
        except Exception as e:
            logger.error(f"Failed to get template features for {template_id}: {e}", exc_info=True)
            return []

    # ==================== 驗證方法 ====================

    def _validate_mcp_json(self, path: Path) -> bool:
        """驗證 MCP JSON 有效性

        檢查：
        1. JSON 格式正確
        2. 有 mcpServers 欄位
        3. mcpServers 至少有一個 server
        """
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return (
                isinstance(data, dict) and
                'mcpServers' in data and
                isinstance(data['mcpServers'], dict) and
                len(data['mcpServers']) > 0
            )
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            logger.debug(f"MCP JSON validation failed for {path}: {e}")
            return False

    def _validate_hooks_json(self, path: Path) -> bool:
        """驗證 Hooks JSON 有效性

        檢查：
        1. JSON 格式正確
        2. 有 hooks 欄位
        """
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return isinstance(data, dict) and 'hooks' in data
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            logger.debug(f"Hooks JSON validation failed for {path}: {e}")
            return False

    def _validate_claude_md(self, path: Path) -> bool:
        """驗證 CLAUDE.md 有效性

        檢查檔案大小 > 10 bytes（非空檔案）
        """
        try:
            return path.stat().st_size > 10
        except OSError as e:
            logger.debug(f"CLAUDE.md validation failed for {path}: {e}")
            return False

    def _has_valid_md_files(self, directory: Path) -> bool:
        """檢查目錄中是否有有效的 .md 檔案

        Args:
            directory: 目錄路徑

        Returns:
            bool: 是否有至少一個 .md 檔案
        """
        if not directory.exists() or not directory.is_dir():
            return False

        try:
            for item in directory.iterdir():
                if item.is_file() and item.suffix == '.md' and item.name not in self.IGNORE_FILES:
                    return True
            return False
        except OSError as e:
            logger.debug(f"Directory validation failed for {directory}: {e}")
            return False

    def _has_valid_files_in_directory(self, directory: Path) -> bool:
        """檢查目錄中是否有有效檔案（排除 .gitkeep 等）

        Args:
            directory: 目錄路徑

        Returns:
            bool: 目錄是否非空（排除忽略檔案）
        """
        if not directory.exists() or not directory.is_dir():
            return False

        try:
            for item in directory.iterdir():
                if item.name not in self.IGNORE_FILES:
                    return True
            return False
        except OSError as e:
            logger.debug(f"Directory validation failed for {directory}: {e}")
            return False
