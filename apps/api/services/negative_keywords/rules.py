"""Layer 1: deterministic rules.

Each rule is a pure function over a SearchTerm + EngineConfig that returns zero
or more RuleHits. A hit is evidence, not a verdict: the engine aggregates hits
across layers before deciding. Rules never fire on whitelisted brand terms or
terms that conflict with active positive keywords, because a false negative here
destroys real demand and is far more expensive than a missed bit of waste.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .arabic import normalise, tokens
from .models import EngineConfig, MatchType, Scope, SearchTerm

# Low-intent / off-target lexicons. English plus Gulf-Arabic equivalents.
LOW_INTENT_LEXICON: dict[str, dict[str, list[str]]] = {
    "jobs": {
        "en": ["job", "jobs", "career", "careers", "salary", "vacancy", "hiring", "recruit", "cv", "resume", "internship"],
        "ar": ["وظيفه", "وظائف", "توظيف", "شاغر", "راتب", "سيره ذاتيه", "تدريب", "متدرب"],
    },
    "support": {
        "en": ["login", "log in", "sign in", "support", "helpline", "complaint", "contact number", "customer service", "track order", "refund", "cancel"],
        "ar": ["تسجيل الدخول", "دعم", "شكوى", "خدمة العملاء", "رقم", "تتبع", "استرجاع", "الغاء"],
    },
    "free": {
        "en": ["free", "freebie", "gratis", "no cost", "cheap", "cheapest", "discount code", "coupon", "crack", "torrent"],
        "ar": ["مجاني", "مجانا", "ببلاش", "ارخص", "رخيص", "كوبون", "خصم"],
    },
    "student_research": {
        "en": ["meaning", "definition", "what is", "how to", "wikipedia", "pdf", "tutorial", "example", "diy", "homework", "assignment", "student"],
        "ar": ["معنى", "تعريف", "ما هو", "ما هي", "كيف", "شرح", "بحث", "مثال", "طالب", "واجب"],
    },
}


@dataclass
class RuleHit:
    rule: str
    reason: str
    match_type: MatchType
    scope: Scope
    weight: float                # 0..1 contribution toward confidence
    risk_flags: list[str] = field(default_factory=list)
    conflict: bool = False
    category_hint: str | None = None


def _is_brand_protected(term: SearchTerm, cfg: EngineConfig) -> bool:
    norm = normalise(term.text)
    return any(normalise(b) in norm for b in cfg.brand_whitelist if b)


def _conflicts_with_positive(term: SearchTerm, cfg: EngineConfig) -> bool:
    """If the term contains a token that is itself an active positive keyword,
    a negative could block legitimate matched traffic. Flag, do not silently
    suggest."""
    term_tokens = set(tokens(term.text))
    for kw in cfg.positive_keywords:
        kw_tokens = set(tokens(kw))
        if kw_tokens and kw_tokens.issubset(term_tokens):
            return True
    return False


def _lexicon_category(term: SearchTerm) -> str | None:
    norm = normalise(term.text)
    for category, langs in LOW_INTENT_LEXICON.items():
        for phrases in langs.values():
            for phrase in phrases:
                if normalise(phrase) in norm:
                    return category
    return None


def evaluate_rules(term: SearchTerm, cfg: EngineConfig) -> list[RuleHit]:
    # Hard exclusions first. These short-circuit everything downstream.
    if _is_brand_protected(term, cfg):
        return []
    if normalise(term.text) in {normalise(d) for d in cfg.do_not_suggest}:
        return []

    conflict = _conflicts_with_positive(term, cfg)
    conflict_flags = ["conflicts_with_active_keyword"] if conflict else []
    hits: list[RuleHit] = []

    # Rule: spend with no conversions past an evidence threshold.
    if term.conversions == 0 and term.clicks >= cfg.min_clicks_for_no_conversion:
        hits.append(RuleHit(
            rule="no_conversion_after_threshold",
            reason=f"{term.clicks} clicks and {cfg.currency} {term.cost:.0f} spend, zero conversions",
            match_type=MatchType.PHRASE,
            scope=Scope.AD_GROUP,
            weight=0.55,
            risk_flags=conflict_flags,
            conflict=conflict,
        ))

    # Rule: meaningful cost with no value at all.
    if term.cost >= cfg.cost_floor_no_value and term.conversion_value == 0 and term.conversions == 0:
        hits.append(RuleHit(
            rule="cost_no_value",
            reason=f"{cfg.currency} {term.cost:.0f} spend produced no recorded value",
            match_type=MatchType.PHRASE,
            scope=Scope.CAMPAIGN,
            weight=0.5,
            risk_flags=conflict_flags,
            conflict=conflict,
        ))

    # Rule: CPA far worse than target.
    if cfg.target_cpa and term.cpa is not None and term.cpa > cfg.target_cpa * cfg.cpa_multiple_for_negative:
        hits.append(RuleHit(
            rule="cpa_above_target",
            reason=f"CPA {cfg.currency} {term.cpa:.0f} vs target {cfg.currency} {cfg.target_cpa:.0f}",
            match_type=MatchType.EXACT,
            scope=Scope.CAMPAIGN,
            weight=0.45,
            risk_flags=conflict_flags + (["has_some_conversions"] if term.conversions > 0 else []),
            conflict=conflict,
        ))

    # Rule: lexicon-matched off-target intent (jobs/support/free/research).
    category = _lexicon_category(term)
    if category:
        # Off-target lexicon hits are stronger when they also waste money.
        weight = 0.6 if term.conversions == 0 else 0.35
        hits.append(RuleHit(
            rule=f"low_intent_{category}",
            reason=f"matches {category} pattern in search text",
            match_type=MatchType.PHRASE,
            scope=Scope.ACCOUNT if term.conversions == 0 else Scope.CAMPAIGN,
            weight=weight,
            risk_flags=conflict_flags,
            conflict=conflict,
            category_hint=category,
        ))

    # Rule: competitor terms (configurable, account decides policy).
    norm = normalise(term.text)
    if any(normalise(c) in norm for c in cfg.competitor_terms if c):
        hits.append(RuleHit(
            rule="competitor_term",
            reason="contains a configured competitor term",
            match_type=MatchType.PHRASE,
            scope=Scope.CAMPAIGN,
            weight=0.4,
            risk_flags=conflict_flags + ["competitor_policy_dependent"],
            conflict=conflict,
            category_hint="competitor",
        ))

    return hits
