"""Layer 2: n-gram mining.

Single search terms are noisy. Aggregating to unigram/bigram/trigram level
across the whole report surfaces systematically wasteful tokens (for example
"free" or "وظائف" appearing across dozens of terms with spend and no value) and,
critically, protective conversion-assisting n-grams so we never recommend a
negative that would block a token that also drives conversions.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .arabic import tokens
from .models import SearchTerm


@dataclass
class NgramStat:
    ngram: str
    n: int
    term_count: int
    cost: float
    clicks: int
    conversions: float
    conversion_value: float

    @property
    def wasted(self) -> bool:
        return self.conversions == 0 and self.cost > 0

    @property
    def assisting(self) -> bool:
        return self.conversions > 0


def _ngrams(toks: list[str], n: int) -> list[str]:
    return [" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1)]


def mine_ngrams(terms: list[SearchTerm], max_n: int = 3) -> dict[str, NgramStat]:
    agg: dict[str, dict] = defaultdict(lambda: {
        "n": 0, "term_count": 0, "cost": 0.0, "clicks": 0,
        "conversions": 0.0, "conversion_value": 0.0,
    })
    for term in terms:
        toks = tokens(term.text)
        seen: set[str] = set()
        for n in range(1, max_n + 1):
            for g in _ngrams(toks, n):
                if g in seen:
                    continue          # count each ngram once per term
                seen.add(g)
                a = agg[g]
                a["n"] = n
                a["term_count"] += 1
                a["cost"] += term.cost
                a["clicks"] += term.clicks
                a["conversions"] += term.conversions
                a["conversion_value"] += term.conversion_value
    return {
        g: NgramStat(ngram=g, n=a["n"], term_count=a["term_count"], cost=a["cost"],
                     clicks=a["clicks"], conversions=a["conversions"],
                     conversion_value=a["conversion_value"])
        for g, a in agg.items()
    }


def wasted_ngrams(stats: dict[str, NgramStat], min_terms: int = 3, min_cost: float = 30.0) -> list[NgramStat]:
    """N-grams that recur, cost money, and never convert. Sorted by wasted cost."""
    out = [s for s in stats.values()
           if s.wasted and s.term_count >= min_terms and s.cost >= min_cost]
    return sorted(out, key=lambda s: s.cost, reverse=True)


def assisting_ngrams(stats: dict[str, NgramStat], min_conversions: float = 1.0) -> set[str]:
    """N-grams associated with any conversions. Used as a protective veto list:
    do not suggest a negative whose key n-gram appears here."""
    return {s.ngram for s in stats.values() if s.conversions >= min_conversions}
