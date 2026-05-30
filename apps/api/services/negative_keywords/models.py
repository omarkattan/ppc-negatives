"""Input/output models local to the negative keyword engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class MatchType(str, Enum):
    EXACT = "exact"
    PHRASE = "phrase"
    BROAD = "broad"


class Scope(str, Enum):
    AD_GROUP = "ad_group"
    CAMPAIGN = "campaign"
    ACCOUNT = "account"
    SHARED_LIST = "shared_list"


class IntentLabel(str, Enum):
    IRRELEVANT = "irrelevant"
    SUPPORT = "support"
    JOBS = "jobs"
    COMPETITOR = "competitor"
    INFORMATIONAL = "informational"
    STUDENT_RESEARCH = "student_research"
    LOW_PURCHASE_INTENT = "low_purchase_intent"
    HIGH_PURCHASE_INTENT = "high_purchase_intent"
    UNCERTAIN = "uncertain"


@dataclass
class SearchTerm:
    """One row of a search-terms report, normalised across platforms."""
    term_id: str
    text: str
    campaign_id: str
    ad_group_id: str
    matched_keyword: Optional[str] = None
    impressions: int = 0
    clicks: int = 0
    cost: float = 0.0          # account currency
    conversions: float = 0.0
    conversion_value: float = 0.0
    language: str = "en"        # "en" | "ar"

    @property
    def cpa(self) -> Optional[float]:
        return self.cost / self.conversions if self.conversions > 0 else None

    @property
    def roas(self) -> Optional[float]:
        return self.conversion_value / self.cost if self.cost > 0 else None


@dataclass
class EngineConfig:
    """Targets and guardrails. Defaults are deliberately conservative so the
    engine errs toward not suggesting a negative rather than risking value."""
    currency: str = "AED"
    target_cpa: Optional[float] = None
    target_roas: Optional[float] = None
    # Layer 1 thresholds
    min_clicks_for_no_conversion: int = 25      # need enough evidence of failure
    cost_floor_no_value: float = 50.0           # cost above this with no value is wasteful
    cpa_multiple_for_negative: float = 2.0      # CPA worse than 2x target
    # Brand / competitor protection
    brand_whitelist: list[str] = field(default_factory=list)
    competitor_terms: list[str] = field(default_factory=list)
    positive_keywords: list[str] = field(default_factory=list)  # for conflict detection
    do_not_suggest: list[str] = field(default_factory=list)     # archived false positives
