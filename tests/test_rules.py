from negative_keywords.models import EngineConfig, SearchTerm
from negative_keywords.rules import evaluate_rules


def _term(**kw):
    base = dict(term_id="t", text="x", campaign_id="c", ad_group_id="g")
    base.update(kw)
    return SearchTerm(**base)


def test_no_conversion_after_threshold_fires():
    t = _term(text="free shoes", clicks=30, cost=80.0, conversions=0)
    hits = evaluate_rules(t, EngineConfig())
    assert any(h.rule == "no_conversion_after_threshold" for h in hits)


def test_below_click_threshold_does_not_fire_no_conversion():
    t = _term(text="some neutral query", clicks=5, cost=80.0, conversions=0)
    hits = evaluate_rules(t, EngineConfig())
    assert not any(h.rule == "no_conversion_after_threshold" for h in hits)


def test_brand_whitelist_blocks_all_suggestions():
    cfg = EngineConfig(brand_whitelist=["Acme"])
    t = _term(text="acme free login jobs", clicks=40, cost=200.0, conversions=0)
    assert evaluate_rules(t, cfg) == []


def test_do_not_suggest_blocks():
    cfg = EngineConfig(do_not_suggest=["free shoes"])
    t = _term(text="free shoes", clicks=40, cost=200.0, conversions=0)
    assert evaluate_rules(t, cfg) == []


def test_conflict_with_positive_keyword_is_flagged_not_silent():
    cfg = EngineConfig(positive_keywords=["running shoes"])
    t = _term(text="cheap running shoes", clicks=40, cost=120.0, conversions=0)
    hits = evaluate_rules(t, cfg)
    assert hits and all(h.conflict for h in hits)


def test_cpa_above_target_fires():
    cfg = EngineConfig(target_cpa=30.0, cpa_multiple_for_negative=2.0)
    t = _term(text="expensive term", clicks=10, cost=130.0, conversions=1)  # CPA 130 > 60
    hits = evaluate_rules(t, cfg)
    assert any(h.rule == "cpa_above_target" for h in hits)


def test_lexicon_jobs_arabic():
    t = _term(text="وظائف شركة عطور", clicks=30, cost=70.0, conversions=0, language="ar")
    hits = evaluate_rules(t, EngineConfig())
    assert any(h.category_hint == "jobs" for h in hits)


def test_lexicon_free_arabic():
    t = _term(text="عطور مجانية", clicks=30, cost=90.0, conversions=0, language="ar")
    hits = evaluate_rules(t, EngineConfig())
    assert any(h.category_hint == "free" for h in hits)
