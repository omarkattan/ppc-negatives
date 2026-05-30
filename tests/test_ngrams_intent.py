from negative_keywords.intent import LexiconIntentClassifier
from negative_keywords.models import IntentLabel, SearchTerm
from negative_keywords.ngrams import assisting_ngrams, mine_ngrams, wasted_ngrams


def _t(tid, text, cost, conv, val=0.0, clicks=10):
    return SearchTerm(tid, text, "c", "g", None, 100, clicks, cost, conv, val)


def test_wasted_ngram_detected():
    terms = [
        _t("1", "free shoes online", 40, 0),
        _t("2", "free running shoes", 35, 0),
        _t("3", "free shoes sale", 30, 0),
        _t("4", "buy shoes", 50, 3, 600),
    ]
    stats = mine_ngrams(terms)
    wasted = wasted_ngrams(stats, min_terms=3, min_cost=30)
    assert any(w.ngram == "free" for w in wasted)


def test_assisting_ngram_protects_converting_token():
    terms = [
        _t("1", "buy shoes", 50, 3, 600),
        _t("2", "buy boots", 40, 2, 400),
    ]
    stats = mine_ngrams(terms)
    assisting = assisting_ngrams(stats)
    assert "buy" in assisting


def test_intent_high_when_conversions_present():
    t = _t("1", "running shoes", 50, 3, 600)
    res = LexiconIntentClassifier().classify(t)
    assert res.label == IntentLabel.HIGH_PURCHASE_INTENT


def test_intent_jobs_arabic():
    t = _t("1", "وظائف عطور", 70, 0)
    res = LexiconIntentClassifier().classify(t)
    assert res.label == IntentLabel.JOBS


def test_intent_high_arabic_buy():
    t = _t("1", "شراء عطور", 70, 0)
    res = LexiconIntentClassifier().classify(t)
    assert res.label == IntentLabel.HIGH_PURCHASE_INTENT


def test_user_correction_wins():
    clf = LexiconIntentClassifier(corrections={"free shoes": IntentLabel.HIGH_PURCHASE_INTENT})
    t = _t("1", "free shoes", 40, 0)
    res = clf.classify(t)
    assert res.label == IntentLabel.HIGH_PURCHASE_INTENT
    assert "user_correction" in res.signals
