"""Negative keyword engine.

Orchestrates Layers 1-4 and emits Recommendation objects on the shared contract.

Safety model (the part that makes this beat naive tools):
  * Brand-whitelisted terms never produce suggestions.
  * A candidate negative whose key n-gram also appears in the conversion-assisting
    set is NOT emitted as an action; it is downgraded to a conflict-flagged review
    item with reduced confidence and autopilot_safe = False.
  * autopilot_safe is granted only for high-confidence, zero-conversion,
    no-conflict, low-risk suggestions. Everything else is approval-only.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the shared contract importable whether run as a package or standalone.
_SHARED = Path(__file__).resolve().parents[4] / "packages" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

from ppc_shared.recommendation import (  # noqa: E402
    ApprovalStatus, EstimatedImpact, FeatureType, Recommendation,
    RecommendationRun, RiskLevel, SourceRef,
)

from .arabic import tokens  # noqa: E402
from .clustering import cluster_terms  # noqa: E402
from .embeddings import Embedder  # noqa: E402
from .intent import IntentClassifier, LexiconIntentClassifier  # noqa: E402
from .models import EngineConfig, MatchType, Scope, SearchTerm  # noqa: E402
from .ngrams import assisting_ngrams, mine_ngrams, wasted_ngrams  # noqa: E402
from .rules import evaluate_rules  # noqa: E402

MODEL_VERSION = "negatives-engine-0.1.0"


def _confidence_from_weights(weights: list[float]) -> float:
    """Diminishing-returns aggregation: multiple weak signals raise confidence
    but never to certainty. 1 - prod(1 - w)."""
    acc = 1.0
    for w in weights:
        acc *= (1.0 - max(0.0, min(1.0, w)))
    return round(1.0 - acc, 4)


def run_engine(
    account_id: str,
    terms: list[SearchTerm],
    cfg: EngineConfig | None = None,
    embedder: Embedder | None = None,
    classifier: IntentClassifier | None = None,
) -> RecommendationRun:
    cfg = cfg or EngineConfig()
    classifier = classifier or LexiconIntentClassifier()

    stats = mine_ngrams(terms)
    assisting = assisting_ngrams(stats)        # protective veto set
    clusters = cluster_terms(terms, embedder=embedder)
    cluster_by_term = {tid: c for c in clusters for tid in c.term_ids}

    recs: list[Recommendation] = []

    for term in terms:
        hits = evaluate_rules(term, cfg)
        if not hits:
            continue
        intent = classifier.classify(term)

        # Choose the strongest hit for match type / scope.
        primary = max(hits, key=lambda h: h.weight)
        term_toks = set(tokens(term.text))

        # Protective veto, correctly scoped to the match type.
        # A phrase/exact negative of the whole multi-word term only blocks that
        # phrase, so a shared converting token like "shoes" does not make it
        # unsafe. The assist veto only bites when the negative is BROAD, or is a
        # single token that itself assists conversions.
        single_token = len(term_toks) == 1
        assist_relevant = primary.match_type == MatchType.BROAD or single_token
        assists = assist_relevant and any(
            set(ng.split()).issubset(term_toks) for ng in assisting
        )
        keyword_conflict = any(h.conflict for h in hits)   # positive-keyword overlap

        weights = [h.weight for h in hits]
        # High-intent terms should rarely be negated; penalise confidence hard.
        if intent.label.value == "high_purchase_intent":
            weights = [w * 0.3 for w in weights]
        confidence = _confidence_from_weights(weights)

        risk_flags = sorted({f for h in hits for f in h.risk_flags})
        if assists:
            risk_flags.append("token_assists_conversions")

        wasted = term.cost if term.conversions == 0 else 0.0
        # Risk tiers:
        #   HIGH   - negating directly loses recorded value, or a broad/token
        #            negative would block converting traffic
        #   MEDIUM - phrase/exact overlap with an active positive keyword, or low
        #            confidence; safe to act only after a human looks
        #   LOW    - clean off-target waste
        if term.conversions > 0 or assists:
            risk_level = RiskLevel.HIGH
        elif keyword_conflict or confidence < 0.6:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        conflict = keyword_conflict or assists  # surfaced in explanation/payload

        autopilot_safe = (
            confidence >= 0.75 and term.conversions == 0
            and risk_level == RiskLevel.LOW
        )

        cluster = cluster_by_term.get(term.term_id)
        explanation = (
            f"Search term '{term.text}' flagged by {', '.join(h.rule for h in hits)}. "
            f"Intent classified as {intent.label.value} ({intent.confidence:.0%}). "
            + ("CONFLICT: shares a token with converting traffic, review before applying. "
               if conflict else "")
            + (f"Sits in cluster '{cluster.label}'." if cluster else "")
        )

        recs.append(Recommendation(
            account_id=account_id,
            feature_type=FeatureType.NEGATIVE_KEYWORD,
            confidence=confidence,
            estimated_impact=EstimatedImpact(
                metric="wasted_spend_prevented", value=round(wasted, 2), unit=cfg.currency,
            ),
            explanation=explanation,
            constraints=[f"scope={primary.scope.value}", f"match_type={primary.match_type.value}"],
            risk_flags=risk_flags,
            risk_level=risk_level,
            approval_status=ApprovalStatus.PENDING_APPROVAL,
            autopilot_safe=autopilot_safe,
            model_version=MODEL_VERSION,
            source_refs=[SourceRef(kind="search_term", ref_id=term.term_id, note=term.text)],
            payload={
                "suggested_negative": term.text,
                "match_type": primary.match_type.value,
                "scope": primary.scope.value,
                "intent": intent.label.value,
                "intent_signals": intent.signals,
                "evidence": {
                    "clicks": term.clicks, "cost": round(term.cost, 2),
                    "conversions": term.conversions,
                    "conversion_value": round(term.conversion_value, 2),
                    "cpa": round(term.cpa, 2) if term.cpa else None,
                },
                "rules_fired": [h.rule for h in hits],
                "conflict": conflict,
                "cluster": cluster.label if cluster else None,
            },
        ))

    # N-gram-level suggestions: recurring wasteful tokens become shared-list
    # candidates, but only if NOT in the assisting veto set.
    for ng in wasted_ngrams(stats):
        if ng.ngram in assisting:
            continue
        confidence = _confidence_from_weights([0.5, min(0.4, ng.term_count / 20.0)])
        recs.append(Recommendation(
            account_id=account_id,
            feature_type=FeatureType.NEGATIVE_KEYWORD,
            confidence=confidence,
            estimated_impact=EstimatedImpact(
                metric="wasted_spend_prevented", value=round(ng.cost, 2), unit=cfg.currency,
            ),
            explanation=(
                f"N-gram '{ng.ngram}' appears across {ng.term_count} search terms, "
                f"costing {cfg.currency} {ng.cost:.0f} with no conversions. "
                f"Candidate for a shared negative list."
            ),
            constraints=["scope=shared_list", "match_type=phrase"],
            risk_flags=[],
            risk_level=RiskLevel.LOW if confidence >= 0.6 else RiskLevel.MEDIUM,
            approval_status=ApprovalStatus.PENDING_APPROVAL,
            autopilot_safe=False,  # portfolio-wide actions always need a human
            model_version=MODEL_VERSION,
            source_refs=[SourceRef(kind="ngram", ref_id=ng.ngram)],
            payload={
                "suggested_negative": ng.ngram, "match_type": "phrase",
                "scope": "shared_list", "term_count": ng.term_count,
                "cost": round(ng.cost, 2), "n": ng.n,
            },
        ))

    recs.sort(key=lambda r: (r.estimated_impact.value or 0.0), reverse=True)
    return RecommendationRun(
        account_id=account_id, feature_type=FeatureType.NEGATIVE_KEYWORD,
        model_version=MODEL_VERSION,
        params={"currency": cfg.currency, "term_count": len(terms), "clusters": len(clusters)},
        recommendations=recs,
    )
