"""模板服務 - 整合所有模板相關功能的主服務

這個服務整合了以下子服務：
- TemplateBaseService: 基礎方法和路徑管理
- TemplateMcpService: MCP 配置管理
- TemplateHooksService: Hooks 配置管理
- TemplateCommandsService: Commands 檔案管理
- TemplateAgentsService: Agents 檔案管理
- TemplateOutputStyleService: Output Style 檔案管理
- TemplateFileService: 通用檔案操作（scripts/skills）
- TemplateAgentsMdService: AGENTS.md 檔案管理
- TemplateMarketplaceService: Marketplace 配置管理
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import yaml

from app.config.settings import get_settings
from app.db.models import Template as TemplateDB
from app.models import (
    Template,
    TemplateAuthor,
    TemplateCanonicalUpdate,
    TemplateCreate,
    TemplateListResponse,
    TemplateUpdate,
)
from app.models.template_canonical import CanonicalTemplate
from app.models.template import (
    TemplateFileNode,
    TemplateHook,
    TemplateMcpServer,
    TemplateOutputStyle,
    TemplateCommand,
    TemplateAgent,
)
from app.services.template_base_service import TemplateBaseService
from app.services.template_canonical_service import TemplateCanonicalService
from app.services.template_mcp_service import TemplateMcpService
from app.services.template_hooks_service import TemplateHooksService
from app.services.template_commands_service import TemplateCommandsService
from app.services.template_agents_service import TemplateAgentsService
from app.services.template_output_style_service import TemplateOutputStyleService
from app.services.template_file_service import TemplateFileService
from app.services.template_agents_md_service import TemplateAgentsMdService
from app.services.template_marketplace_service import TemplateMarketplaceService
from app.services.template_feature_detection_service import TemplateFeatureDetectionService

logger = logging.getLogger(__name__)

ALLOWED_TEMPLATE_CLI_TYPES = {"claude-code", "codex", "gemini", "opencode"}
ALLOWED_TEMPLATE_STATUSES = {"draft", "released"}
LEGACY_TEMPLATE_STATUS_MAP = {
    "active": "released",
    "published": "released",
    "inactive": "draft",
}


class TemplateService(TemplateBaseService):
    """管理工作區範本與配置（資料庫 + 檔案系統）

    整合所有模板相關功能，包括：
    - 模板 CRUD 操作
    - MCP 配置管理
    - Hooks 配置管理
    - Commands 檔案管理
    - Agents 檔案管理
    - Output Styles 檔案管理
    - 檔案系統操作
    - 模板匯入/匯出
    """

    def __init__(self, db: Session) -> None:
        super().__init__(db)
        # 初始化子服務
        self.mcp_service = TemplateMcpService(db)
        self.hooks_service = TemplateHooksService(db)
        self.commands_service = TemplateCommandsService(db)
        self.agents_service = TemplateAgentsService(db)
        self.output_style_service = TemplateOutputStyleService(db)
        self.file_service = TemplateFileService(db)
        self.agents_md_service = TemplateAgentsMdService(db)
        self.marketplace_service = TemplateMarketplaceService(db)
        self.feature_detection_service = TemplateFeatureDetectionService(db, self)
        self.canonical_service = TemplateCanonicalService(db)

    # ============ 模板 CRUD 操作 ============

    def list(
        self,
        category: Optional[str] = None,
        cli_type: Optional[str] = None,
        keywords: Optional[str] = None,
        search: Optional[str] = None,
        features: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> TemplateListResponse:
        """列出所有模板（支援篩選和分頁）"""
        from app.db.models import TemplateFeature, TemplateFeatureMapping
        from sqlalchemy import func

        query = self.db.query(TemplateDB)

        # 篩選條件
        if category:
            query = query.filter(TemplateDB.category == category)
        if cli_type:
            query = query.filter(TemplateDB.cli_type == cli_type)
        if keywords:
            # 關鍵字篩選（逗號分隔）
            keyword_list = [t.strip() for t in keywords.split(",") if t.strip()]
            for keyword in keyword_list:
                query = query.filter(TemplateDB.keywords.contains([keyword]))
        if search:
            # 搜尋名稱或描述
            search_pattern = f"%{search}%"
            query = query.filter(
                (TemplateDB.name.ilike(search_pattern))
                | (TemplateDB.description.ilike(search_pattern))
            )

        # Feature 篩選（支援多個 Feature 的 AND 邏輯）
        if features:
            feature_list = [f.strip() for f in features.split(",") if f.strip()]

            # canonical feature keys
            _SNAKE_MAP = {
                "commands": "commands",
                "agentsMd": "agentsMd",
                "agents": "agents",
                "outputStyle": "outputStyle",
            }

            for feature_key in feature_list:
                # 轉換為 snake_case
                db_feature_key = _SNAKE_MAP.get(feature_key, feature_key)

                # 子查詢：找出擁有此 Feature 的模板 ID
                subquery = self.db.query(TemplateFeatureMapping.template_id).join(
                    TemplateFeature,
                    TemplateFeatureMapping.feature_id == TemplateFeature.id
                ).filter(
                    TemplateFeature.feature_key == db_feature_key,
                    TemplateFeature.is_active == True,
                    TemplateFeatureMapping.is_enabled == True
                ).subquery()

                # 主查詢只保留在子查詢結果中的模板
                query = query.filter(TemplateDB.id.in_(subquery))

        # 總數
        total = query.count()

        # 分頁
        offset = (page - 1) * limit
        db_templates = query.order_by(TemplateDB.created_at.desc()).offset(offset).limit(limit).all()

        # 轉換為 Pydantic 模型
        items = [self._db_to_pydantic(t) for t in db_templates]

        total_pages = (total + limit - 1) // limit if limit > 0 else 1

        return TemplateListResponse(
            items=items, total=total, page=page, limit=limit, total_pages=total_pages
        )

    def get(self, template_id: str) -> Optional[Template]:
        """取得單一模板"""
        db_template = self.db.query(TemplateDB).filter(TemplateDB.id == template_id).first()
        if not db_template:
            return None
        return self._db_to_pydantic(db_template)

    def create(self, payload: TemplateCreate) -> Template:
        """建立新模板"""
        # 使用 template_id 欄位作為模板代號
        template_id = payload.template_id

        # 檢查模板 ID 是否已存在
        existing = self.db.query(TemplateDB).filter(TemplateDB.id == template_id).first()
        if existing:
            raise ValueError(f"模板代號 '{template_id}' 已存在，請使用其他代號")

        # 驗證模板代號格式（kebab-case，必須以字母開頭，只能英文）
        if not re.match(r'^[a-z][a-z0-9]*(-[a-z0-9]+)*$', template_id):
            raise ValueError("模板代號必須使用 kebab-case 格式（以小寫英文字母開頭，僅包含小寫英文、數字和連字號）")

        # 建立資料庫記錄
        db_template = TemplateDB(
            id=template_id,
            name=payload.name,
            description=payload.description,
            author_name=payload.author.name,
            author_email=payload.author.email,
            author_url=payload.author.url,
            category=None,
            version=payload.version or "1.0.0",
            cli_type=payload.cli_type,
            status=payload.status,
            keywords=payload.keywords or [],
            init_commands=payload.init_commands,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(db_template)
        self.db.commit()
        self.db.refresh(db_template)

        # 建立檔案系統結構
        try:
            self._create_template_structure(template_id, payload)
        except Exception as e:
            # 如果檔案系統建立失敗，回滾資料庫
            logger.error(f"建立模板檔案結構失敗: {e}")
            self.db.delete(db_template)
            self.db.commit()
            raise

        # 自動索引 Feature（失敗不阻斷）
        try:
            self.feature_detection_service.index_features(template_id)
            logger.info(f"Successfully indexed features for template {template_id}")
        except Exception as e:
            logger.error(f"Feature indexing failed for template {template_id}: {e}", exc_info=True)
            # 不拋出例外，允許模板建立成功

        return self._db_to_pydantic(db_template)

    def update(self, template_id: str, payload: TemplateUpdate) -> Optional[Template]:
        """更新模板基本資訊"""
        db_template = self.db.query(TemplateDB).filter(TemplateDB.id == template_id).first()
        if not db_template:
            return None

        # 更新欄位
        update_data = payload.model_dump(exclude_none=True, by_alias=False)
        author_data = update_data.pop("author", None)

        # 欄位名稱映射：API (camelCase) -> DB (snake_case)
        field_mapping = {
            "categoryId": "category",
        }

        for field, value in update_data.items():
            # 使用映射後的欄位名稱
            db_field = field_mapping.get(field, field)
            setattr(db_template, db_field, value)

        if author_data:
            db_template.author_name = author_data.get("name", db_template.author_name)
            db_template.author_email = author_data.get("email")
            db_template.author_url = author_data.get("url")

        db_template.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_template)

        # 自動重新索引 Feature（失敗不阻斷）
        try:
            self.feature_detection_service.index_features(template_id)
            logger.info(f"Successfully re-indexed features for template {template_id}")
        except Exception as e:
            logger.error(f"Feature re-indexing failed for template {template_id}: {e}", exc_info=True)
            # 不拋出例外，允許模板更新成功

        return self._db_to_pydantic(db_template)

    def update_canonical(self, template_id: str, payload: TemplateCanonicalUpdate) -> Optional[Template]:
        """更新 canonical template tree 與 metadata。"""
        db_template = self.db.query(TemplateDB).filter(TemplateDB.id == template_id).first()
        if not db_template:
            return None

        db_template.name = payload.name
        db_template.description = payload.description
        db_template.version = payload.version
        db_template.author_name = payload.author.name
        db_template.author_email = payload.author.email
        db_template.author_url = payload.author.url
        db_template.keywords = payload.keywords or []
        db_template.category = payload.categoryId
        db_template.init_commands = payload.initCommands
        if payload.cliType:
            db_template.cli_type = payload.cliType
        db_template.status = "released" if payload.isActive else "draft"
        db_template.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(db_template)

        self._write_canonical_template_tree(template_id, payload, db_template)

        try:
            self.feature_detection_service.index_features(template_id)
        except Exception as e:
            logger.error("Feature indexing failed for template %s: %s", template_id, e, exc_info=True)

        return self._db_to_pydantic(db_template)

    def delete(self, template_id: str) -> bool:
        """刪除模板（資料庫 + 檔案系統）"""
        db_template = self.db.query(TemplateDB).filter(TemplateDB.id == template_id).first()
        if not db_template:
            return False

        # 刪除資料庫記錄
        self.db.delete(db_template)
        self.db.commit()

        # 刪除檔案系統目錄
        try:
            self._delete_template_structure(template_id)
        except Exception as e:
            logger.error(f"刪除模板檔案結構失敗: {e}")
            # 即使檔案刪除失敗，資料庫已刪除，返回成功

        return True

    def index_features(self, template_id: str):
        """手動觸發模板的 Feature 索引

        用於：
        - 管理員修復不一致
        - 批次更新索引
        - 從其他系統匯入模板後重建索引

        Args:
            template_id: 模板 ID

        Returns:
            FeatureIndexResult: 索引結果
        """
        return self.feature_detection_service.index_features(template_id)

    # ============ 模板結構管理 ============

    def _create_template_structure(self, template_id: str, payload: TemplateCreate) -> None:
        """建立模板檔案系統結構"""
        template_dir = self._resolve_template_dir(template_id)
        template_dir.mkdir(parents=True, exist_ok=True)
        for directory in ("skills", "commands", "agents", "hooks", "mcp", "resources"):
            (template_dir / directory).mkdir(exist_ok=True)
        (template_dir / "resources" / "scripts").mkdir(parents=True, exist_ok=True)

        template_yaml = {
            "id": template_id,
            "name": payload.name,
            "version": payload.version or "1.0.0",
            "description": payload.description,
            "schemaVersion": "v0",
            "supportedTargets": ["claude-code", "codex", "gemini", "opencode"],
            "features": {
                "agentsMd": {"path": "agents.md"},
                "outputStyle": {"path": "output-style.yaml"},
                "skills": {"path": "skills"},
                "commands": {"path": "commands"},
                "agents": {"path": "agents"},
                "hooks": {"path": "hooks"},
                "mcpServers": {"path": "mcp"},
                "resources": {"path": "resources"},
            },
            "metadata": {
                "author": {
                    "name": payload.author.name,
                    "email": payload.author.email,
                    "url": payload.author.url,
                },
                "keywords": payload.keywords or [],
                "status": payload.status,
                "initCommands": payload.init_commands,
            },
        }
        (template_dir / "template.yaml").write_text(
            yaml.safe_dump(template_yaml, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _delete_template_structure(self, template_id: str) -> None:
        """刪除模板檔案系統結構"""
        template_dir = self._get_template_dir(template_id)
        if template_dir.exists():
            shutil.rmtree(template_dir)

    def _db_to_pydantic(self, db_template: TemplateDB) -> Template:
        """將資料庫模型轉換為 Pydantic 模型（包含完整配置）"""
        canonical_root = self._resolve_template_dir(db_template.id)
        if (canonical_root / "template.yaml").exists():
            try:
                canonical = self.canonical_service.load_from_template_id(db_template.id)
                return self._canonical_to_pydantic(db_template, canonical)
            except Exception as e:
                logger.error("Load canonical template failed for %s: %s", db_template.id, e, exc_info=True)

        # 載入各項配置
        mcp_config = self.mcp_service.load_mcp_servers(db_template.id)
        hooks_config = self.hooks_service.load_hooks(db_template.id)
        commands = self.commands_service.load_commands(db_template.id)
        agents = self.agents_service.load_agents(db_template.id)
        output_style = self.output_style_service.load_output_style(db_template.id)
        files = self.file_service.load_files(db_template.id)
        skills = self.file_service.load_skills(db_template.id)

        # 載入 AGENTS.md 內容
        agents_md = self.agents_md_service.get_agents_md(db_template.id)

        return Template(
            id=db_template.id,
            name=db_template.name,
            description=db_template.description,
            author=TemplateAuthor(
                name=db_template.author_name,
                email=db_template.author_email,
                url=db_template.author_url,
            ),
            categoryId=db_template.category,
            version=db_template.version,
            cliType=db_template.cli_type,
            status=db_template.status,
            keywords=db_template.keywords or [],
            initCommands=db_template.init_commands,
            agentsMd=agents_md,
            mcpServers=mcp_config,
            hooks=hooks_config,
            commands=commands,
            agents=agents,
            outputStyle=output_style,
            scripts=files,
            skills=skills,
            created_at=db_template.created_at,
            updated_at=db_template.updated_at,
        )

    def _canonical_to_pydantic(self, db_template: TemplateDB, canonical: CanonicalTemplate) -> Template:
        output_style: List[TemplateOutputStyle] = []
        if canonical.output_style:
            output_style.append(
                TemplateOutputStyle(
                    id="output-style",
                    fileName=Path(canonical.output_style.path).name,
                    description=canonical.output_style.data.get("description"),
                    content=canonical.output_style.fallback_instruction
                    or yaml.safe_dump(canonical.output_style.data, allow_unicode=True, sort_keys=False),
                )
            )

        return Template(
            id=db_template.id,
            name=db_template.name,
            description=db_template.description,
            author=TemplateAuthor(
                name=db_template.author_name,
                email=db_template.author_email,
                url=db_template.author_url,
            ),
            categoryId=db_template.category,
            version=db_template.version,
            cliType=db_template.cli_type,
            status=db_template.status,
            keywords=db_template.keywords or [],
            initCommands=db_template.init_commands,
            documentation=canonical.index.metadata.get("documentation"),
            agentsMd=canonical.agents_md_content,
            mcpServers=[
                TemplateMcpServer(
                    id=server.id,
                    name=server.id,
                    type=server.transport,  # type: ignore[arg-type]
                    command=server.command,
                    args=server.args or None,
                    url=server.url,
                    description=server.raw.get("description"),
                    env=server.env or None,
                    headers=server.headers or None,
                )
                for server in canonical.mcp_servers
            ],
            hooks=[
                TemplateHook(
                    id=hook.id,
                    name=hook.id,
                    event=hook.event,
                    matcher=(hook.matcher or {}).get("tool") if isinstance(hook.matcher, dict) else None,
                    action=str((hook.action or {}).get("type") or "command"),  # type: ignore[arg-type]
                    command=(hook.action or {}).get("command"),
                    script=(hook.action or {}).get("path"),
                    timeout=hook.timeout,
                )
                for hook in canonical.hooks
            ],
            commands=[
                TemplateCommand(
                    id=doc.name,
                    fileName=Path(doc.path).name,
                    description=doc.frontmatter.get("description"),
                    content=doc.content,
                )
                for doc in canonical.commands
            ],
            agents=[
                TemplateAgent(
                    id=doc.name,
                    fileName=Path(doc.path).name,
                    description=doc.frontmatter.get("description"),
                    content=doc.content,
                )
                for doc in canonical.agents
            ],
            outputStyle=output_style,
            scripts=self._canonical_resources_to_file_nodes(canonical),
            skills=[
                TemplateFileNode(
                    id=skill.id,
                    name=Path(skill.skill_md_path).name,
                    path=skill.skill_md_path,
                    type="file",
                    content=skill.content,
                )
                for skill in canonical.skills
            ],
            created_at=db_template.created_at,
            updated_at=db_template.updated_at,
        )

    def _canonical_resources_to_file_nodes(self, canonical: CanonicalTemplate) -> List[TemplateFileNode]:
        root = Path(canonical.root_path)
        nodes: List[TemplateFileNode] = []
        for resource in canonical.resources:
            nodes.extend(self._flatten_resource_nodes(resource, root))
        return nodes

    def _flatten_resource_nodes(self, node: Any, root: Path) -> List[TemplateFileNode]:
        items: List[TemplateFileNode] = []
        if getattr(node, "type", None) == "file":
            file_path = root / node.path
            content = file_path.read_text(encoding="utf-8") if file_path.exists() else None
            items.append(
                TemplateFileNode(
                    id=node.path,
                    name=Path(node.path).name,
                    path=node.path,
                    type="file",
                    content=content,
                )
            )
        for child in getattr(node, "children", []) or []:
            items.extend(self._flatten_resource_nodes(child, root))
        return items

    def _write_canonical_template_tree(
        self,
        template_id: str,
        payload: TemplateCanonicalUpdate,
        db_template: TemplateDB,
    ) -> None:
        root = self._resolve_template_dir(template_id)
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)

        if payload.agentsMd:
            (root / "agents.md").write_text(payload.agentsMd, encoding="utf-8")

        if payload.outputStyle:
            primary_style = payload.outputStyle[0]
            output_payload: Dict[str, Any] = {
                "id": Path(primary_style.fileName).stem,
                "fallbackInstruction": primary_style.content,
            }
            if primary_style.description:
                output_payload["description"] = primary_style.description
            (root / "output-style.yaml").write_text(
                yaml.safe_dump(output_payload, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

        self._write_markdown_documents(root / "commands", payload.commands)
        self._write_markdown_documents(root / "agents", payload.agents)
        self._write_hooks(root / "hooks", payload.hooks)
        self._write_mcp_servers(root / "mcp", payload.mcpServers)
        self._write_file_nodes(root / "skills", payload.skills)
        self._write_file_nodes(root / "resources" / "scripts", payload.scripts)
        self._write_template_yaml(root, payload, db_template)

    def _write_markdown_documents(self, directory: Path, items: List[Any]) -> None:
        if not items:
            return
        directory.mkdir(parents=True, exist_ok=True)
        for item in items:
            file_name = Path(item.fileName).name
            frontmatter: Dict[str, Any] = {"name": Path(file_name).stem}
            if getattr(item, "description", None):
                frontmatter["description"] = item.description
            (directory / file_name).write_text(
                self._render_frontmatter_markdown(frontmatter, item.content),
                encoding="utf-8",
            )

    def _write_hooks(self, directory: Path, hooks: List[TemplateHook]) -> None:
        if not hooks:
            return
        directory.mkdir(parents=True, exist_ok=True)
        for hook in hooks:
            hook_payload: Dict[str, Any] = {
                "id": hook.id,
                "event": hook.event,
                "matcher": {"tool": hook.matcher or "*"},
                "action": {
                    "type": hook.action,
                    **({"command": hook.command} if hook.command else {}),
                    **({"path": hook.script} if hook.script else {}),
                },
            }
            if hook.timeout is not None:
                hook_payload["timeout"] = hook.timeout
            (directory / f"{hook.id}.yaml").write_text(
                yaml.safe_dump(hook_payload, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

    def _write_mcp_servers(self, directory: Path, servers: List[TemplateMcpServer]) -> None:
        if not servers:
            return
        directory.mkdir(parents=True, exist_ok=True)
        for server in servers:
            server_id = server.name or server.id
            server_payload: Dict[str, Any] = {
                "id": server_id,
                "transport": server.type,
                **({"command": server.command} if server.command else {}),
                **({"args": server.args} if server.args else {}),
                **({"url": server.url} if server.url else {}),
                **({"env": server.env} if server.env else {}),
                **({"headers": server.headers} if server.headers else {}),
            }
            if server.description:
                server_payload["description"] = server.description
            (directory / f"{server_id}.yaml").write_text(
                yaml.safe_dump(server_payload, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

    def _write_file_nodes(self, root: Path, nodes: List[TemplateFileNode]) -> None:
        if not nodes:
            return
        for node in nodes:
            self._write_file_node(root, node)

    def _write_file_node(self, root: Path, node: TemplateFileNode) -> None:
        target_path = root / node.path
        if node.type == "directory":
            target_path.mkdir(parents=True, exist_ok=True)
            for child in node.children or []:
                self._write_file_node(root, child)
            return
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(node.content or "", encoding="utf-8")

    def _write_template_yaml(self, root: Path, payload: TemplateCanonicalUpdate, db_template: TemplateDB) -> None:
        template_yaml = {
            "id": db_template.id,
            "name": payload.name,
            "version": payload.version,
            "description": payload.description,
            "schemaVersion": "v0",
            "supportedTargets": ["claude-code", "codex", "gemini", "opencode"],
            "features": {
                "agentsMd": {"path": "agents.md"},
                "outputStyle": {"path": "output-style.yaml"},
                "skills": {"path": "skills"},
                "commands": {"path": "commands"},
                "agents": {"path": "agents"},
                "hooks": {"path": "hooks"},
                "mcpServers": {"path": "mcp"},
                "resources": {"path": "resources"},
            },
            "compileHints": {
                "claude-code": {"agentsMdFileName": "CLAUDE.md"},
                "codex": {"agentsMdFileName": "AGENTS.md"},
                "gemini": {"agentsMdFileName": "GEMINI.md"},
                "opencode": {"agentsMdFileName": "AGENTS.md"},
            },
            "metadata": {
                "author": {
                    "name": payload.author.name,
                    "email": payload.author.email,
                    "url": payload.author.url,
                },
                "keywords": payload.keywords,
                "status": db_template.status,
                "documentation": payload.documentation,
                "initCommands": payload.initCommands,
                "category": payload.categoryId or "general",
            },
        }
        (root / "template.yaml").write_text(
            yaml.safe_dump(template_yaml, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    @staticmethod
    def _render_frontmatter_markdown(frontmatter: Dict[str, Any], content: str) -> str:
        if not frontmatter:
            return content
        frontmatter_text = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
        body = content.lstrip("\n")
        return f"---\n{frontmatter_text}\n---\n\n{body}\n"

    # ============ 模板匯入/匯出 ============

    def export_template(self, template_id: str) -> Optional[Path]:
        """匯出模板為 ZIP 檔案"""
        db_template = self._get_template(template_id)
        if not db_template:
            return None

        template_dir = self._get_template_dir(template_id)
        if not template_dir.exists():
            return None

        # 建立臨時 ZIP 檔案
        temp_dir = Path(tempfile.mkdtemp())
        zip_path = temp_dir / f"{template_id}.zip"

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in template_dir.rglob("*"):
                    if file_path.is_file():
                        arcname = file_path.relative_to(template_dir)
                        zipf.write(file_path, arcname)

            return zip_path
        except Exception as e:
            logger.error(f"匯出模板失敗: {e}")
            if zip_path.exists():
                zip_path.unlink()
            return None

    async def import_template(self, file: UploadFile, overwrite: bool = False) -> Template:
        """匯入模板 ZIP 檔案"""
        # 建立臨時目錄
        temp_dir = Path(tempfile.mkdtemp())

        try:
            # 儲存上傳的檔案
            zip_path = temp_dir / file.filename
            content = await file.read()
            zip_path.write_bytes(content)

            # 解壓縮
            extract_dir = temp_dir / "extracted"
            try:
                with zipfile.ZipFile(zip_path, "r") as zipf:
                    zipf.extractall(extract_dir)
            except zipfile.BadZipFile as e:
                raise ValueError("無效的模板檔案：ZIP 檔案已損壞或格式不正確") from e

            # 讀取 plugin.json
            plugin_json_path = self._find_import_plugin_json(extract_dir)
            if not plugin_json_path.exists():
                raise ValueError("無效的模板檔案：缺少 .claude-plugin/plugin.json")

            try:
                plugin_data = json.loads(plugin_json_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise ValueError("無效的模板檔案：plugin.json 不是合法的 JSON") from e
            template_id = plugin_data.get("id")

            if not template_id:
                raise ValueError("無效的模板檔案：plugin.json 缺少 id 欄位")
            if not self._validate_template_id(template_id):
                raise ValueError("無效的模板檔案：plugin.json 的 id 格式不合法")

            normalized_cli_type = self._normalize_import_cli_type(plugin_data.get("cli_type"))
            normalized_status = self._normalize_import_status(plugin_data.get("status"))

            # 檢查是否已存在
            existing = self._get_template(template_id)
            if existing and not overwrite:
                raise ValueError(f"模板 '{template_id}' 已存在，請使用覆蓋模式")

            # 建立或更新資料庫記錄
            if existing:
                # 更新現有模板
                db_template = existing
                db_template.name = plugin_data.get("name", db_template.name)
                db_template.description = plugin_data.get("description", db_template.description)
                db_template.version = plugin_data.get("version", db_template.version)
                db_template.cli_type = normalized_cli_type or db_template.cli_type
                db_template.status = normalized_status or db_template.status
                db_template.keywords = plugin_data.get("keywords", db_template.keywords)
                db_template.init_commands = plugin_data.get("init_commands", db_template.init_commands)
                db_template.updated_at = datetime.utcnow()

                author = plugin_data.get("author", {})
                db_template.author_name = author.get("name", db_template.author_name)
                db_template.author_email = author.get("email")
                db_template.author_url = author.get("url")
            else:
                # 建立新模板
                author = plugin_data.get("author", {})
                db_template = TemplateDB(
                    id=template_id,
                    name=plugin_data.get("name", "Unnamed Template"),
                    description=plugin_data.get("description", ""),
                    author_name=author.get("name", "Unknown"),
                    author_email=author.get("email"),
                    author_url=author.get("url"),
                    version=plugin_data.get("version", "1.0.0"),
                    cli_type=normalized_cli_type or "claude-code",
                    status=normalized_status or "draft",
                    keywords=plugin_data.get("keywords", []),
                    init_commands=plugin_data.get("init_commands"),
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                self.db.add(db_template)

            try:
                self.db.commit()
                self.db.refresh(db_template)
            except SQLAlchemyError as e:
                self.db.rollback()
                logger.error("匯入模板寫入資料庫失敗: %s", e, exc_info=True)
                raise ValueError("模板 metadata 無效，請檢查 plugin.json 欄位內容")

            # 複製檔案到模板目錄
            template_dir = self._get_template_dir(template_id)
            if template_dir.exists():
                shutil.rmtree(template_dir)
            shutil.copytree(extract_dir, template_dir)

            return self._db_to_pydantic(db_template)

        finally:
            # 清理臨時目錄
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def _find_import_plugin_json(self, extract_dir: Path) -> Path:
        """找出匯入 ZIP 內的 plugin.json，支援直接位於根目錄或包一層模板目錄。"""
        direct_path = extract_dir / ".claude-plugin" / "plugin.json"
        if direct_path.exists():
            return direct_path

        matches = list(extract_dir.glob("*/.claude-plugin/plugin.json"))
        if len(matches) == 1:
            return matches[0]

        return direct_path

    def _normalize_import_cli_type(self, cli_type: Optional[str]) -> Optional[str]:
        """正規化匯入模板的 cli_type，避免 legacy 值造成資料庫錯誤。"""
        if not cli_type:
            return None

        normalized = cli_type.strip().lower()
        if normalized == "claude":
            normalized = "claude-code"
        elif normalized == "claudecode":
            normalized = "claude-code"

        if normalized in ALLOWED_TEMPLATE_CLI_TYPES:
            return normalized

        raise ValueError(
            "無效的模板檔案：plugin.json 的 cli_type 不合法，"
            "僅支援 claude-code、codex、gemini"
        )

    def _normalize_import_status(self, status: Optional[str]) -> Optional[str]:
        """正規化匯入模板的 status，兼容舊版 active/published。"""
        if not status:
            return None

        normalized = status.strip().lower()
        normalized = LEGACY_TEMPLATE_STATUS_MAP.get(normalized, normalized)

        if normalized in ALLOWED_TEMPLATE_STATUSES:
            return normalized

        raise ValueError(
            "無效的模板檔案：plugin.json 的 status 不合法，"
            "僅支援 draft、released"
        )


    # ============ MCP 配置管理（委派給 mcp_service） ============

    def get_mcp_config(self, template_id: str):
        """取得 MCP 配置"""
        return self.mcp_service.get_mcp_config(template_id)

    def update_mcp_config(self, template_id: str, request):
        """更新 MCP 配置"""
        return self.mcp_service.update_mcp_config(template_id, request)

    # ============ Hooks 配置管理（委派給 hooks_service） ============

    def get_hooks_config(self, template_id: str):
        """取得 Hooks 配置"""
        return self.hooks_service.get_hooks_config(template_id)

    def update_hooks_config(self, template_id: str, request):
        """更新 Hooks 配置"""
        return self.hooks_service.update_hooks_config(template_id, request)

    # ============ Commands 管理（委派給 commands_service） ============

    def get_commands_files(self, template_id: str):
        """取得 Commands 檔案列表"""
        return self.commands_service.get_commands_files(template_id)

    def get_command_file_content(self, template_id: str, file_name: str):
        """取得 Slash Command 檔案內容"""
        return self.commands_service.get_command_file_content(template_id, file_name)

    def create_command_file(self, template_id: str, request):
        """建立 Slash Command 檔案"""
        return self.commands_service.create_command_file(template_id, request)

    def update_command_file(self, template_id: str, file_name: str, request):
        """更新 Slash Command 檔案"""
        return self.commands_service.update_command_file(template_id, file_name, request)

    def delete_command_file(self, template_id: str, file_name: str):
        """刪除 Slash Command 檔案"""
        return self.commands_service.delete_command_file(template_id, file_name)

    # ============ Agents 管理（委派給 agents_service） ============

    def get_agents_files(self, template_id: str):
        """取得 Agents 檔案列表"""
        return self.agents_service.get_agents_files(template_id)

    def get_agent_file_content(self, template_id: str, file_name: str):
        """取得 Agent 檔案內容"""
        return self.agents_service.get_agent_file_content(template_id, file_name)

    def create_agent_file(self, template_id: str, request):
        """建立 Agent 檔案"""
        return self.agents_service.create_agent_file(template_id, request)

    def update_agent_file(self, template_id: str, file_name: str, request):
        """更新 Agent 檔案"""
        return self.agents_service.update_agent_file(template_id, file_name, request)

    def delete_agent_file(self, template_id: str, file_name: str):
        """刪除 Agent 檔案"""
        return self.agents_service.delete_agent_file(template_id, file_name)

    # ============ Output Styles 管理（委派給 output_style_service） ============

    def get_output_style_files(self, template_id: str):
        """取得 Output Styles 檔案列表"""
        return self.output_style_service.get_output_style_files(template_id)

    def get_output_style_file_content(self, template_id: str, file_name: str):
        """取得 Output Style 檔案內容"""
        return self.output_style_service.get_output_style_file_content(template_id, file_name)

    def create_output_style_file(self, template_id: str, request):
        """建立 Output Style 檔案"""
        return self.output_style_service.create_output_style_file(template_id, request)

    def update_output_style_file(self, template_id: str, file_name: str, request):
        """更新 Output Style 檔案"""
        return self.output_style_service.update_output_style_file(template_id, file_name, request)

    def delete_output_style_file(self, template_id: str, file_name: str):
        """刪除 Output Style 檔案"""
        return self.output_style_service.delete_output_style_file(template_id, file_name)

    # ============ 檔案管理（委派給 file_service） ============

    @staticmethod
    def _request_value(request, key: str, default=None):
        """同時支援 Pydantic request 與 dict 風格存取"""
        if isinstance(request, dict):
            return request.get(key, default)
        return getattr(request, key, default)

    def get_template_files(self, template_id: str, path: Optional[str] = None, include_content: bool = False, max_depth: int = -1, base_path: str = "scripts"):
        """取得模板檔案樹"""
        resolved_depth = 99 if max_depth < 0 else max_depth
        return self.file_service.get_tree(
            template_id,
            path=path or "/",
            scope=base_path,
            include_hidden=include_content,
            max_depth=resolved_depth,
        )

    def get_file_content(self, template_id: str, path: str, base_path: str = "scripts"):
        """取得檔案內容"""
        return self.file_service.read_file(template_id, path, scope=base_path)

    def create_file_or_directory(self, template_id: str, request, base_path: str = "scripts"):
        """建立檔案或目錄"""
        return self.file_service.create_entry(
            template_id,
            self._request_value(request, "path"),
            self._request_value(request, "type", "file"),
            scope=base_path,
            content=self._request_value(request, "content", ""),
        )

    def update_file_content(self, template_id: str, request, base_path: str = "scripts"):
        """更新檔案內容"""
        return self.file_service.write_file(
            template_id,
            self._request_value(request, "path"),
            self._request_value(request, "content", ""),
            scope=base_path,
            expected_version_id=self._request_value(request, "expected_version_id"),
        )

    async def upload_files(self, template_id: str, target_path: str, files: List[UploadFile], overwrite: bool = False, base_path: str = "scripts"):
        """上傳檔案"""
        return await self.file_service.upload_files(template_id, target_path, files, overwrite, base_path)

    def rename_file(self, template_id: str, request, base_path: str = "scripts"):
        """重命名檔案或目錄"""
        old_path = Path(self._request_value(request, "old_path"))
        new_path = str(old_path.with_name(self._request_value(request, "new_name")))
        return self.file_service.move_entry(
            template_id,
            str(old_path),
            new_path,
            scope=base_path,
            overwrite=False,
        )

    def move_file(self, template_id: str, request, base_path: str = "scripts"):
        """移動檔案或目錄"""
        return self.file_service.move_entry(
            template_id,
            self._request_value(request, "source_path"),
            self._request_value(request, "target_path"),
            scope=base_path,
            overwrite=self._request_value(request, "overwrite", False),
        )

    def copy_file(self, template_id: str, request, base_path: str = "scripts"):
        """複製檔案或目錄"""
        return self.file_service.copy_entry(
            template_id,
            self._request_value(request, "source_path"),
            self._request_value(request, "target_path"),
            scope=base_path,
            overwrite=self._request_value(request, "overwrite", False),
        )

    def delete_file(self, template_id: str, file_path: str, recursive: bool = False, base_path: str = "scripts"):
        """刪除檔案或目錄"""
        return self.file_service.delete_entry(
            template_id,
            file_path,
            scope=base_path,
            recursive=recursive,
        )

    def batch_delete_files(self, template_id: str, request, base_path: str = "scripts"):
        """批次刪除檔案"""
        return self.file_service.batch_delete(
            template_id,
            self._request_value(request, "paths", []),
            scope=base_path,
            recursive=self._request_value(request, "recursive", False),
        )

    def search_files(self, template_id: str, request):
        """搜尋檔案"""
        return self.file_service.search_files(template_id, request)

    # ============ AGENTS.md 管理（委派給 agents_md_service） ============

    def get_agents_md(self, template_id: str) -> str:
        """取得 AGENTS.md 檔案內容"""
        return self.agents_md_service.get_agents_md(template_id)

    def update_agents_md(self, template_id: str, content: str) -> None:
        """更新 AGENTS.md 檔案"""
        return self.agents_md_service.update_agents_md(template_id, content)

    # ============ Marketplace 配置管理（委派給 marketplace_service） ============

    def get_marketplace_config(self):
        """取得 Marketplace 配置"""
        return self.marketplace_service.get_marketplace_config()

    def update_marketplace_config(self, config):
        """更新 Marketplace 配置"""
        return self.marketplace_service.update_marketplace_config(config)

    # ============ 內部載入方法（用於模板安裝） ============

    def _load_commands(self, template_id: str):
        """載入 Commands 配置"""
        return self.commands_service.load_commands(template_id)

    def _load_agents(self, template_id: str):
        """載入 Agents 配置"""
        return self.agents_service.load_agents(template_id)

    def _load_output_style(self, template_id: str):
        """載入 Output Styles 配置"""
        return self.output_style_service.load_output_style(template_id)

    def _load_mcp_servers(self, template_id: str):
        """載入 MCP Servers 配置"""
        return self.mcp_service.load_mcp_servers(template_id)

    def _load_hooks(self, template_id: str):
        """載入 Hooks 配置"""
        return self.hooks_service.load_hooks(template_id)

    def _load_files(self, template_id: str):
        """載入 Files 配置"""
        return self.file_service.load_files(template_id)


__all__ = ["TemplateService"]
