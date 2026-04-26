"""Template feature detection and indexing service"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4
import yaml

from sqlalchemy.orm import Session

from app.db.models import Template as TemplateDB
from app.db.models import TemplateFeature, TemplateFeatureMapping
from app.services.template_base_service import TemplateBaseService

logger = logging.getLogger(__name__)


class FeatureIndexResult:
    """Feature IndexResult"""
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
    """Template feature detection and indexing service

    Responsibilities:
    1. Analyze template directory structure, detect feature existence
    2. Verify feature validity (such as JSON file format)
    3. Sync feature index with database
    4. Provide feature query interface
    """

    # Feature detection rule definitions
    FEATURE_DETECTION_RULES = {
        'mcp': {
            'path': 'mcp',
            'type': 'directory',
            'validator': '_has_valid_yaml_files'
        },
        'commands': {
            'path': 'commands',
            'type': 'directory',
            'validator': '_has_valid_md_files'
        },
        'hooks': {
            'path': 'hooks',
            'type': 'directory',
            'validator': '_has_valid_hook_files'
        },
        'agentsMd': {
            'path': 'agents.md',
            'type': 'file',
            'validator': '_validate_agents_md'
        },
        'agents': {
            'path': 'agents',
            'type': 'directory',
            'validator': '_has_valid_md_files'
        },
        'outputStyle': {
            'path': 'output-style.yaml',
            'type': 'file',
            'validator': '_validate_output_style_yaml'
        },
        'scripts': {
            'path': 'resources/scripts',
            'type': 'directory',
            'validator': '_has_valid_files_in_directory'
        },
        'skills': {
            'path': 'skills',
            'type': 'directory',
            'validator': '_has_valid_files_in_directory'
        }
    }

    # Files to ignore
    IGNORE_FILES = {'.gitkeep', '.git', '__pycache__', '.DS_Store', 'Thumbs.db'}

    def __init__(self, db: Session, template_base_service: TemplateBaseService):
        """InitializeService

        Args:
            db: Database session
            template_base_service: Template base service, used for getting template path and other information
        """
        self.db = db
        self.template_base_service = template_base_service

    def detect_features(self, template_id: str) -> Dict[str, bool]:
        """Detect existence status of all features in template

        Args:
            template_id: Template ID

        Returns:
            Dict[str, bool]: Feature key -> whether exists mapping
        """
        template_dir = self.template_base_service._resolve_template_dir(template_id)

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
        """Analyze and index features to database

        Args:
            template_id: Template ID

        Returns:
            FeatureIndexResult: IndexResult
        """
        try:
            # Check if template exists
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

            # Detect features
            detected_features = self.detect_features(template_id)
            detected_feature_keys = [key for key, exists in detected_features.items() if exists]

            logger.info(f"Detected features for template {template_id}: {detected_feature_keys}")

            # Delete old mappings
            self.db.query(TemplateFeatureMapping).filter(
                TemplateFeatureMapping.template_id == template_id
            ).delete()

            # Create new mappings
            indexed_count = 0
            failed_count = 0

            for feature_key in detected_feature_keys:
                try:
                    # Query Feature ID
                    feature = self.db.query(TemplateFeature).filter(
                        TemplateFeature.feature_key == feature_key,
                        TemplateFeature.is_active == True
                    ).first()

                    if not feature:
                        logger.warning(f"Feature '{feature_key}' not found in database")
                        failed_count += 1
                        continue

                    # Create new mappings
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

            # Commit changes
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
        """Query template indexed features

        Args:
            template_id: Template ID

        Returns:
            List[str]: Feature key list
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

    # ==================== Validation methods ====================

    def _validate_mcp_json(self, path: Path) -> bool:
        """Verify MCP JSON validity

        Checks:
        1. JSON format is correct
        2. has mcpServers field
        3. mcpServers has at least one server
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
        """Verify hooks JSON validity

        Checks:
        1. JSON format is correct
        2. has hooks field
        """
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return isinstance(data, dict) and 'hooks' in data
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            logger.debug(f"Hooks JSON validation failed for {path}: {e}")
            return False

    def _has_valid_yaml_files(self, directory: Path) -> bool:
        """Directory contains at least one valid YAML file."""
        try:
            return any(path.is_file() and path.suffix in {".yaml", ".yml"} for path in directory.iterdir())
        except Exception as e:
            logger.debug(f"YAML directory validation failed for {directory}: {e}")
            return False

    def _has_valid_hook_files(self, directory: Path) -> bool:
        """Hooks directory has at least one valid hook YAML, ignoring the scripts subdirectory."""
        try:
            return any(
                path.is_file() and path.suffix in {".yaml", ".yml"} for path in directory.iterdir()
            )
        except Exception as e:
            logger.debug(f"Hook directory validation failed for {directory}: {e}")
            return False

    def _validate_output_style_yaml(self, path: Path) -> bool:
        """Verify canonical output-style.yaml."""
        try:
            data = json.loads(json.dumps(yaml.safe_load(path.read_text(encoding="utf-8")) or {}))
            return isinstance(data, dict)
        except Exception as e:
            logger.debug(f"Output style YAML validation failed for {path}: {e}")
            return False

    def _validate_agents_md(self, path: Path) -> bool:
        """Verify AGENTS.md validity

        Check file size > 10 bytes (non-empty file)
        """
        try:
            return path.stat().st_size > 10
        except OSError as e:
            logger.debug(f"AGENTS.md validation failed for {path}: {e}")
            return False

    def _has_valid_md_files(self, directory: Path) -> bool:
        """Check if directory has valid .md files

        Args:
            directory: Directory path

        Returns:
            bool: whether there is at least one .md file
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
        """Check if directory has valid files (excluding .gitkeep etc.)

        Args:
            directory: Directory path

        Returns:
            bool: Whether directory is non-empty (excluding ignored files)
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
