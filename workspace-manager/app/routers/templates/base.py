"""模板基础 CRUD 路由"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.openapi import build_responses
from app.modules.auth import get_current_user_id
from app.models import (
    Template,
    TemplateCategory,
    TemplateCategoryListResponse,
    TemplateCanonicalUpdate,
    TemplateCreate,
    TemplateFeatureListResponse,
    TemplateListResponse,
    TemplateUpdate,
    TemplateFeatureInfo,
    FeatureStatItem,
    FeatureStatsResponse,
)
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)
router = APIRouter()

DEFAULT_TEMPLATE_CATEGORY_METADATA = {
    "general": {
        "name": "General",
        "description": "Templates that do not belong to a specific category yet",
        "icon": "folder",
        "sortOrder": 1,
    },
    "automation": {
        "name": "Automation",
        "description": "Templates for workflows, automation tasks, and scheduling",
        "icon": "workflow",
        "sortOrder": 2,
    },
    "documentation": {
        "name": "Documentation",
        "description": "Templates for docs, knowledge bases, and content writing",
        "icon": "file-text",
        "sortOrder": 3,
    },
    "web": {
        "name": "Web Development",
        "description": "Templates for websites and web application development",
        "icon": "globe",
        "sortOrder": 4,
    },
    "devops": {
        "name": "DevOps",
        "description": "Templates for deployment, CI/CD, and infrastructure",
        "icon": "wrench",
        "sortOrder": 5,
    },
}

# canonical feature key 正規化
_CAMEL_MAP = {
    "commands": "commands",
    "agentsMd": "agentsMd",
    "agents": "agents",
    "outputStyle": "outputStyle",
}


def _translate_template_base_value_error(translate, error: str) -> str:
    if error.startswith("模板代號 '") and error.endswith("' 已存在，請使用其他代號"):
        template_id = error[len("模板代號 '"):].split("' 已存在，請使用其他代號", 1)[0]
        return translate("templates.base.id_already_exists", template_id=template_id)
    if "模板代號必須使用 kebab-case 格式" in error:
        return translate("templates.base.invalid_template_id")
    return error


def _to_camel_feature(key: str) -> str:
    return _CAMEL_MAP.get(key, key)


def _normalize_category(category: TemplateCategory) -> TemplateCategory:
    default_meta = DEFAULT_TEMPLATE_CATEGORY_METADATA.get(category.id)
    if not default_meta:
        return category

    return TemplateCategory(
        id=category.id,
        name=default_meta["name"],
        description=default_meta["description"],
        icon=default_meta["icon"],
        sortOrder=default_meta["sortOrder"],
        isActive=category.isActive,
    )


def get_template_service(db: Session = Depends(get_db)) -> TemplateService:
    """取得模板服務實例"""
    return TemplateService(db)


@router.get(
    "/",
    response_model=TemplateListResponse,
    summary="列出模板",
    responses=build_responses(401, 422, 500),
)
async def list_templates(
    request: Request,
    category: Optional[str] = Query(default=None, description="分類篩選"),
    cli_type: Optional[str] = Query(default=None, description="CLI 類型篩選"),
    keywords: Optional[str] = Query(default=None, description="關鍵字篩選（逗號分隔）"),
    search: Optional[str] = Query(default=None, description="搜尋關鍵字"),
    features: Optional[str] = Query(default=None, description="Feature 篩選（逗號分隔）"),
    page: int = Query(default=1, ge=1, description="頁碼"),
    limit: int = Query(default=20, ge=1, le=100, description="每頁數量"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service),
) -> TemplateListResponse:
    """取得模板列表（支援篩選和分頁）"""
    return service.list(
        category=category,
        cli_type=cli_type,
        keywords=keywords,
        search=search,
        features=features,
        page=page,
        limit=limit,
    )


@router.post(
    "/",
    response_model=Template,
    status_code=status.HTTP_201_CREATED,
    summary="建立模板",
    responses=build_responses(401, 422, 500),
)
async def create_template(
    request: Request,
    payload: TemplateCreate,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> Template:
    """建立新模板"""
    try:
        return service.create(payload)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=_translate_template_base_value_error(request.state.translate, str(e)),
        )


@router.get(
    "/features",
    response_model=TemplateFeatureListResponse,
    summary="依 CLI 類型取得可用功能清單",
    responses=build_responses(401, 422, 500),
)
async def list_features_by_cli(
    request: Request,
    cli_type: Optional[str] = Query(
        default=None, description="CLI 類型（claude-code/codex/gemini，可為 all 或省略）"
    ),
    db: Session = Depends(get_db),
) -> TemplateFeatureListResponse:
    """從資料庫讀取並回傳對應 CLI 類型可使用的功能鍵列表（依 sort_order 排序）。
    回傳的鍵為前端使用的 camelCase。
    """
    if cli_type in (None, "all"):
        sql = text(
            """
            SELECT feature_key
            FROM template_features
            WHERE is_active = TRUE
            ORDER BY sort_order ASC
            """
        )
        rows = db.execute(sql).all()
    else:
        sql = text(
            """
            SELECT tf.feature_key
            FROM template_features tf
            JOIN template_feature_cli_types tfc ON tfc.feature_id = tf.id
            WHERE tf.is_active = TRUE AND tfc.cli_type = :cli
            ORDER BY tf.sort_order ASC
            """
        )
        rows = db.execute(sql, {"cli": cli_type}).all()

    keys = [_to_camel_feature(row[0]) for row in rows]
    return TemplateFeatureListResponse(items=keys)


@router.get(
    "/categories",
    response_model=TemplateCategoryListResponse,
    summary="列出模板分類",
    responses=build_responses(401, 500),
)
async def list_categories(
    request: Request,
    db: Session = Depends(get_db),
) -> TemplateCategoryListResponse:
    """取得所有模板分類（依 sort_order 排序）"""
    from app.db.models import TemplateCategory as TemplateCategoryDB

    categories = (
        db.query(TemplateCategoryDB)
        .filter(TemplateCategoryDB.is_active == True)
        .order_by(TemplateCategoryDB.sort_order.asc())
        .all()
    )

    # 使用 from_attributes 自動轉換
    items = [_normalize_category(TemplateCategory.model_validate(cat)) for cat in categories]

    return TemplateCategoryListResponse(items=items)


@router.get(
    "/{template_id}",
    response_model=Template,
    summary="取得模板",
    responses=build_responses(401, 404, 500),
)
async def get_template(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> Template:
    """取得指定模板"""
    template = service.get(template_id)
    if not template:
        translate = request.state.translate
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.not_found")
        )
    return template


@router.put(
    "/{template_id}",
    response_model=Template,
    summary="更新模板",
    responses=build_responses(401, 404, 422, 500),
)
async def update_template(
    request: Request,
    template_id: str,
    payload: TemplateUpdate,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service),
) -> Template:
    """更新模板基本資訊"""
    template = service.update(template_id, payload)
    if not template:
        translate = request.state.translate
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.not_found")
        )
    return template


@router.put(
    "/{template_id}/canonical",
    response_model=Template,
    summary="更新 canonical 模板",
    responses=build_responses(401, 404, 422, 500),
)
async def update_canonical_template(
    request: Request,
    template_id: str,
    payload: TemplateCanonicalUpdate,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service),
) -> Template:
    """以 canonical template tree 更新模板。"""
    template = service.update_canonical(template_id, payload)
    if not template:
        translate = request.state.translate
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.not_found"),
        )
    return template


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="刪除模板",
    responses=build_responses(401, 404, 500),
)
async def delete_template(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> None:
    """刪除指定模板"""
    success = service.delete(template_id)
    if not success:
        translate = request.state.translate
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.not_found")
        )


# ============ Feature 索引相關端點 ============

@router.get(
    "/{template_id}/features",
    response_model=TemplateFeatureInfo,
    summary="查詢模板已索引 Feature",
    responses=build_responses(401, 404, 500),
)
async def get_template_features(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service),
    db: Session = Depends(get_db)
) -> TemplateFeatureInfo:
    """查詢模板已索引的 Feature 列表

    用於前端獲取模板的 Feature 資訊
    """
    # 檢查模板是否存在
    template = service.get(template_id)
    if not template:
        translate = request.state.translate
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.not_found")
        )

    # 查詢已索引的 Feature
    features = service.feature_detection_service.get_template_features(template_id)

    # 查詢索引時間
    from app.db.models import TemplateFeatureMapping
    mapping = db.query(TemplateFeatureMapping).filter(
        TemplateFeatureMapping.template_id == template_id
    ).order_by(TemplateFeatureMapping.indexed_at.desc()).first()

    indexed_at = mapping.indexed_at.isoformat() if mapping and mapping.indexed_at else None

    return TemplateFeatureInfo(
        templateId=template_id,
        features=features,
        indexedAt=indexed_at
    )


@router.get(
    "/features/stats",
    response_model=FeatureStatsResponse,
    summary="取得 Feature 統計資訊",
    responses=build_responses(401, 422, 500),
)
async def get_feature_stats(
    request: Request,
    cli_type: Optional[str] = Query(default=None, description="CLI 類型篩選"),
    db: Session = Depends(get_db)
) -> FeatureStatsResponse:
    """取得 Feature 統計資訊

    顯示每個 Feature 有多少模板支援
    """
    from app.db.models import TemplateFeature, TemplateFeatureMapping, Template as TemplateDB
    from sqlalchemy import func

    # 建立基本查詢
    query = db.query(
        TemplateFeature.feature_key,
        TemplateFeature.feature_name,
        TemplateFeature.description,
        func.count(func.distinct(TemplateFeatureMapping.template_id)).label('count')
    ).outerjoin(
        TemplateFeatureMapping,
        TemplateFeature.id == TemplateFeatureMapping.feature_id
    ).filter(
        TemplateFeature.is_active == True
    )

    # 如果有 CLI 類型篩選，加入條件
    if cli_type:
        query = query.join(
            TemplateDB,
            TemplateFeatureMapping.template_id == TemplateDB.id
        ).filter(
            TemplateDB.cli_type == cli_type
        )

    # 按 Feature 分組並排序
    results = query.group_by(
        TemplateFeature.id,
        TemplateFeature.feature_key,
        TemplateFeature.feature_name,
        TemplateFeature.description,
        TemplateFeature.sort_order
    ).order_by(
        TemplateFeature.sort_order
    ).all()

    # 轉換為回應格式
    stats = {}
    for result in results:
        # 將 snake_case 轉換為 camelCase
        feature_key = _to_camel_feature(result.feature_key)
        stats[feature_key] = FeatureStatItem(
            name=result.feature_name,
            count=result.count,
            description=result.description
        )

    return FeatureStatsResponse(stats=stats)


__all__ = ["router"]
