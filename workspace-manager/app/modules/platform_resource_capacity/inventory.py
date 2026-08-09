"""Capacity-owned inventory filters and projections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import case, func

from app.db import models as db_models

from .models import CapacityRisk, PlatformCapacityProjection
from .policy import CapacityGovernancePolicy


@dataclass(frozen=True)
class WorkspaceCapacityExpressions:
    utilization: Any
    risk: Any
    used_bytes: Any


@dataclass(frozen=True)
class KnowledgeBaseCapacityExpressions:
    effective_quota: Any
    utilization: Any
    risk: Any


@dataclass(frozen=True)
class KnowledgeBaseCapacityProjection:
    effective_quota_bytes: int
    quota_source: str
    utilization_percent: float
    risk: CapacityRisk


class PlatformResourceCapacityInventory:
    """Keep capacity SQL semantics and projections behind one public seam."""

    @staticmethod
    def workspace_expressions(
        workspace_data: Any, runtime_home: Any
    ) -> WorkspaceCapacityExpressions:
        workspace_ratio = workspace_data.used_bytes / func.nullif(
            workspace_data.allocated_bytes, 0
        )
        runtime_ratio = runtime_home.used_bytes / func.nullif(
            runtime_home.allocated_bytes, 0
        )
        workspace_utilization = func.coalesce(workspace_ratio, 0)
        runtime_utilization = func.coalesce(runtime_ratio, 0)
        utilization = case(
            (workspace_utilization >= runtime_utilization, workspace_utilization),
            else_=runtime_utilization,
        )
        risks = (
            CapacityGovernancePolicy.observation_risk_expression(
                exists=workspace_data.id.is_not(None),
                used_bytes=workspace_data.used_bytes,
                allocated_bytes=workspace_data.allocated_bytes,
                measured_at=workspace_data.measured_at,
            ),
            CapacityGovernancePolicy.observation_risk_expression(
                exists=runtime_home.id.is_not(None),
                used_bytes=runtime_home.used_bytes,
                allocated_bytes=runtime_home.allocated_bytes,
                measured_at=runtime_home.measured_at,
            ),
        )
        return WorkspaceCapacityExpressions(
            utilization=utilization,
            risk=CapacityGovernancePolicy.highest_risk_expression(risks),
            used_bytes=func.coalesce(workspace_data.used_bytes, 0)
            + func.coalesce(runtime_home.used_bytes, 0),
        )

    @staticmethod
    def knowledge_base_expressions(
        default_quota_bytes: int,
    ) -> KnowledgeBaseCapacityExpressions:
        effective_quota = case(
            (
                db_models.KnowledgeBase.quota_bytes.is_not(None),
                db_models.KnowledgeBase.quota_bytes,
            ),
            else_=default_quota_bytes,
        )
        utilization = db_models.KnowledgeBase.current_size_bytes / func.nullif(
            effective_quota, 0
        )
        return KnowledgeBaseCapacityExpressions(
            effective_quota=effective_quota,
            utilization=utilization,
            risk=CapacityGovernancePolicy.quota_risk_expression(
                used_bytes=db_models.KnowledgeBase.current_size_bytes,
                quota_bytes=effective_quota,
            ),
        )

    @staticmethod
    def workspace_projection(
        observation: db_models.ResourceCapacityObservation | None,
        *,
        expansion_supported: bool,
    ) -> PlatformCapacityProjection | None:
        if observation is None:
            return None
        assessment = CapacityGovernancePolicy.assess(
            used_bytes=observation.used_bytes,
            allocated_bytes=observation.allocated_bytes,
            measured_at=observation.measured_at,
        )
        return PlatformCapacityProjection(
            usedBytes=observation.used_bytes,
            allocatedBytes=observation.allocated_bytes,
            hostAvailableBytes=observation.host_available_bytes,
            utilizationPercent=(
                assessment.utilization * 100
                if assessment.utilization is not None
                else None
            ),
            risk=assessment.risk,
            measuredAt=observation.measured_at,
            expansionSupported=expansion_supported,
        )

    @staticmethod
    def highest(risks: list[CapacityRisk]) -> CapacityRisk:
        return CapacityGovernancePolicy.highest(risks)

    @staticmethod
    def knowledge_base_projection(
        knowledge_base: db_models.KnowledgeBase,
        *,
        default_quota_bytes: int,
    ) -> KnowledgeBaseCapacityProjection:
        effective_quota = (
            knowledge_base.quota_bytes
            if knowledge_base.quota_bytes is not None
            else default_quota_bytes
        )
        assessment = CapacityGovernancePolicy.assess_quota(
            used_bytes=knowledge_base.current_size_bytes or 0,
            quota_bytes=effective_quota,
        )
        return KnowledgeBaseCapacityProjection(
            effective_quota_bytes=effective_quota,
            quota_source=(
                "custom"
                if knowledge_base.quota_bytes is not None
                else "platform_default"
            ),
            utilization_percent=(assessment.utilization or 0) * 100,
            risk=assessment.risk,
        )
