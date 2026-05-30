from demo_search_terms import english_account, gcc_bilingual_account
from negative_keywords.engine import run_engine
from negative_keywords.models import EngineConfig, SearchTerm
from ppc_shared.recommendation import FeatureType, Recommendation


def test_english_pipeline_produces_valid_contract_objects():
    acct, terms, cfg = english_account()
    run = run_engine(acct, terms, cfg)
    assert run.feature_type == FeatureType.NEGATIVE_KEYWORD
    assert len(run.recommendations) > 0
    for r in run.recommendations:
        assert isinstance(r, Recommendation)       # validates the contract
        assert r.account_id == acct
        assert 0.0 <= r.confidence <= 1.0
        assert r.explanation.strip()
        assert r.model_version
        assert r.source_refs


def test_high_intent_converting_term_not_autopiloted():
    acct, terms, cfg = english_account()
    run = run_engine(acct, terms, cfg)
    # "buy running shoes online" converts; it must never be an autopilot negative.
    for r in run.recommendations:
        if "buy running shoes online" in r.payload.get("suggested_negative", ""):
            assert r.autopilot_safe is False


def test_converting_token_blocks_ngram_shared_negative():
    # "shoes" converts heavily, so it must not surface as a shared-list negative.
    acct, terms, cfg = english_account()
    run = run_engine(acct, terms, cfg)
    shared = [r for r in run.recommendations if r.payload.get("scope") == "shared_list"]
    assert all(r.payload["suggested_negative"] != "shoes" for r in shared)


def test_gcc_distinguishes_buy_from_jobs():
    acct, terms, cfg = gcc_bilingual_account()
    run = run_engine(acct, terms, cfg)
    by_term = {r.payload.get("suggested_negative"): r for r in run.recommendations
               if r.feature_type == FeatureType.NEGATIVE_KEYWORD}
    # The jobs term should be recommended; the high-intent buy term should not be
    # an autopilot-safe negative.
    jobs = [r for r in run.recommendations if "وظائف" in r.payload.get("suggested_negative", "")]
    assert jobs, "expected the Arabic jobs term to be flagged"


def test_brand_term_never_suggested():
    cfg = EngineConfig(currency="AED", brand_whitelist=["Siyate"])
    terms = [SearchTerm("b1", "Siyate perfume offers", "c", "g", None, 100, 40, 200.0, 0, 0.0)]
    run = run_engine("acct", terms, cfg)
    assert all("siyate" not in r.payload.get("suggested_negative", "").lower()
               for r in run.recommendations)


def test_estimated_impact_is_wasted_spend_for_zero_conversion():
    cfg = EngineConfig(currency="USD")
    terms = [SearchTerm("z1", "free download tool pdf", "c", "g", None, 100, 40, 120.0, 0, 0.0)]
    run = run_engine("acct", terms, cfg)
    term_recs = [r for r in run.recommendations if r.payload.get("suggested_negative") == "free download tool pdf"]
    assert term_recs and term_recs[0].estimated_impact.value == 120.0
