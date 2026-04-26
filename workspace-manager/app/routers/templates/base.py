"""Template basic CRUD routes"""

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

# Canonical feature key normalization
_CAMEL_MAP = {
    "commands": "commands",
    "agentsMd": "agentsMd",
    "agents": "agents",
    "outputStyle": "outputStyle",
}


def _translate_template_base_value_error(translate, error: str) -> str:
    if error.startswith("Template ID '") and error.endswith("' already exists, please use another ID"):
        template_id = error[len("Template ID '"):].split("' already exists, please use another ID", 1)[0]
        return translate("templates.base.id_already_exists", template_id=template_id)
    if "Template ID must use kebab-case format" in error:
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
    """Get template service instance"""
    return TemplateService(db)


@router.get(
    "/",
    response_model=TemplateListResponse,
    summary="List templates",
    responses=build_responses(401, 422, 500),
)
async def list_templates(
    request: Request,
    category: Optional[str] = Query(default=None, description="Category filter"),
    cli_type: Optional[str] = Query(default=None, description="CLI type filter"),
    keywords: Optional[str] = Query(default=None, description="Keyword filter (comma-separated)"),
    search: Optional[str] = Query(default=None, description="Search keyword"),
    features: Optional[str] = Query(default=None, description="Feature filter (comma-separated)"),
    page: int = Query(default=1, ge=1, description="Page number"),
    limit: int = Query(default=20, ge=1, le=100, description="Items per page"),
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service),
) -> TemplateListResponse:
    """Get template list (supports filtering and pagination)"""
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
    summary="Create template",
    responses=build_responses(401, 422, 500),
)
async def create_template(
    request: Request,
    payload: TemplateCreate,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> Template:
    """Create new template"""
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
    summary="Get available features by CLI type",
    responses=build_responses(401, 422, 500),
)
async def list_features_by_cli(
    request: Request,
    cli_type: Optional[str] = Query(
        default=None, description="CLI type (claude-code/codex/gemini, can be all or omitted)"
    ),
    db: Session = Depends(get_db),
) -> TemplateFeatureListResponse:
    """
    Read from database and return feature key list usable by corresponding CLI type (sorted by sort_order).
    Returned keys are in camelCase for frontend use.
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
    summary="List template categories",
    responses=build_responses(401, 500),
)
async def list_categories(
    request: Request,
    db: Session = Depends(get_db),
) -> TemplateCategoryListResponse:
    """Get all template categories (sorted by sort_order)"""
    from app.db.models import TemplateCategory as TemplateCategoryDB

    categories = (
        db.query(TemplateCategoryDB)
        .filter(TemplateCategoryDB.is_active == True)
        .order_by(TemplateCategoryDB.sort_order.asc())
        .all()
    )

    # Use from_attributes for auto-conversion
    items = [_normalize_category(TemplateCategory.model_validate(cat)) for cat in categories]

    return TemplateCategoryListResponse(items=items)


@router.get(
    "/{template_id}",
    response_model=Template,
    summary="Get template",
    responses=build_responses(401, 404, 500),
)
async def get_template(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> Template:
    """Get specified template"""
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
    summary="Update template",
    responses=build_responses(401, 404, 422, 500),
)
async def update_template(
    request: Request,
    template_id: str,
    payload: TemplateUpdate,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service),
) -> Template:
    """Update template basic information"""
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
    summary="Update canonical template",
    responses=build_responses(401, 404, 422, 500),
)
async def update_canonical_template(
    request: Request,
    template_id: str,
    payload: TemplateCanonicalUpdate,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service),
) -> Template:
    """Update template with canonical template tree."""
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
    summary="Delete template",
    responses=build_responses(401, 404, 500),
)
async def delete_template(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service)
) -> None:
    """Delete specified template"""
    success = service.delete(template_id)
    if not success:
        translate = request.state.translate
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.not_found")
        )


# ============ Feature Index Endpoints ============

@router.get(
    "/{template_id}/features",
    response_model=TemplateFeatureInfo,
    summary="Query template indexed features",
    responses=build_responses(401, 404, 500),
)
async def get_template_features(
    request: Request,
    template_id: str,
    current_user_id: str = Depends(get_current_user_id),
    service: TemplateService = Depends(get_template_service),
    db: Session = Depends(get_db)
) -> TemplateFeatureInfo:
    """Query template's indexed feature list

    Used for frontend to get template feature information
    """
    # Check if template exists
    template = service.get(template_id)
    if not template:
        translate = request.state.translate
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=translate("templates.not_found")
        )

    # Query indexed features
    features = service.feature_detection_service.get_template_features(template_id)

    # Query index time
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
    summary="Get feature statistics",
    responses=build_responses(401, 422, 500),
)
async def get_feature_stats(
    request: Request,
    cli_type: Optional[str] = Query(default=None, description="CLI type filter"),
    db: Session = Depends(get_db)
) -> FeatureStatsResponse:
    """Get feature statistics

    Display how many templates support each feature
    """
    from app.db.models import TemplateFeature, TemplateFeatureMapping, Template as TemplateDB
    from sqlalchemy import func

    # Create base query
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

    # Add CLI type filter condition if provided
    if cli_type:
        query = query.join(
            TemplateDB,
            TemplateFeatureMapping.template_id == TemplateDB.id
        ).filter(
            TemplateDB.cli_type == cli_type
        )

    # Group by feature and sort
    results = query.group_by(
        TemplateFeature.id,
        TemplateFeature.feature_key,
        TemplateFeature.feature_name,
        TemplateFeature.description,
        TemplateFeature.sort_order
    ).order_by(
        TemplateFeature.sort_order
    ).all()

    # Convert to response format
    stats = {}
    for result in results:
        # Convert snake_case to camelCase
        feature_key = _to_camel_feature(result.feature_key)
        stats[feature_key] = FeatureStatItem(
            name=result.feature_name,
            count=result.count,
            description=result.description
        )

    return FeatureStatsResponse(stats=stats)


__all__ = ["router"]
