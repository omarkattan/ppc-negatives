"""Canonical recommendation contract.

Every recommendation produced by any engine (text ads, budget, negatives) MUST
be representable as a Recommendation. This is the single source of truth for the
data model, which is priority #1 in the brief. Engines are free to put
feature-specific detail inside `payload`, but the envelope fields below are
mandatory and validated.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FeatureType(str, Enum):
    TEXT_ADS = "text_ads"
    BUDGET_ALLOCATION = "budget_allocation"
    NEGATIVE_KEYWORD = "negative_keyword"


class ApprovalStatus(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUSHED = "pushed"
    ROLLED_BACK = "rolled_back"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SourceRef(BaseModel):
    """Pointer back to the raw data a recommendation was derived from, so every
    suggestion is auditable rather than a black box."""
    kind: str  # e.g. "search_term", "daily_performance", "ad_asset"
    ref_id: str
    note: Optional[str] = None


class EstimatedImpact(BaseModel):
    """Impact is always a signed estimate with an explicit unit and, where the
    engine can produce one, a confidence interval. None means 'not estimable',
    which is different from zero."""
    metric: str  # e.g. "wasted_spend_prevented", "incremental_conversions"
    value: Optional[float] = None
    unit: str = "AED"
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None


class Recommendation(BaseModel):
    recommendation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str
    feature_type: FeatureType
    confidence: float = Field(ge=0.0, le=1.0)
    estimated_impact: EstimatedImpact
    explanation: str
    constraints: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = RiskLevel.LOW
    approval_status: ApprovalStatus = ApprovalStatus.DRAFT
    autopilot_safe: bool = False
    generated_at: datetime = Field(default_factory=_utcnow)
    model_version: str
    source_refs: list[SourceRef] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("explanation")
    @classmethod
    def _non_empty_explanation(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("explanation must be a non-empty human-readable string")
        return v


class RecommendationRun(BaseModel):
    """A batch of recommendations from one engine invocation, for auditability
    and evaluation."""
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str
    feature_type: FeatureType
    model_version: str
    generated_at: datetime = Field(default_factory=_utcnow)
    params: dict[str, Any] = Field(default_factory=dict)
    recommendations: list[Recommendation] = Field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "feature_type": self.feature_type.value,
            "count": len(self.recommendations),
            "autopilot_safe": sum(1 for r in self.recommendations if r.autopilot_safe),
            "high_risk": sum(1 for r in self.recommendations if r.risk_level == RiskLevel.HIGH),
        }
