"""Layer 3: semantic clustering.

Embed every search term, cluster by similarity, then score each cluster on
aggregate performance. A cluster that costs money across many terms with no
conversions is a far stronger negative signal than any single term, and gives a
human reviewer one decision instead of fifty. Cluster labels are derived from
the most distinctive tokens so the reviewer sees "free + download + pdf" rather
than an opaque cluster id.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np
from sklearn.cluster import KMeans

from .arabic import tokens
from .embeddings import Embedder, TfidfCharEmbedder
from .models import SearchTerm


@dataclass
class TermCluster:
    cluster_id: int
    label: str
    term_ids: list[str]
    cost: float
    clicks: int
    conversions: float
    conversion_value: float
    member_terms: list[str] = field(default_factory=list)

    @property
    def wasteful(self) -> bool:
        return self.conversions == 0 and self.cost > 0


def _label(terms: list[SearchTerm]) -> str:
    counter: Counter[str] = Counter()
    for t in terms:
        counter.update(tokens(t.text))
    common = [w for w, _ in counter.most_common(3)]
    return " + ".join(common) if common else "cluster"


def cluster_terms(
    terms: list[SearchTerm],
    embedder: Embedder | None = None,
    n_clusters: int | None = None,
) -> list[TermCluster]:
    if len(terms) < 4:
        return []  # not enough data to cluster meaningfully
    embedder = embedder or TfidfCharEmbedder()
    vectors = embedder.fit_transform([t.text for t in terms])
    k = n_clusters or max(2, min(12, len(terms) // 5))
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(vectors)

    grouped: dict[int, list[SearchTerm]] = {}
    for term, lab in zip(terms, labels):
        grouped.setdefault(int(lab), []).append(term)

    clusters: list[TermCluster] = []
    for cid, members in grouped.items():
        clusters.append(TermCluster(
            cluster_id=cid,
            label=_label(members),
            term_ids=[m.term_id for m in members],
            cost=sum(m.cost for m in members),
            clicks=sum(m.clicks for m in members),
            conversions=sum(m.conversions for m in members),
            conversion_value=sum(m.conversion_value for m in members),
            member_terms=[m.text for m in members],
        ))
    return sorted(clusters, key=lambda c: c.cost, reverse=True)
