"""Embedding abstraction.

The brief calls for multilingual embeddings with an Arabic-specialised path. In
production you would back `Embedder` with a multilingual sentence model (and an
Arabic reranker). In this offline build the default is a character n-gram TF-IDF
embedder, which works without network access and is genuinely script-agnostic:
character trigrams handle Arabic morphology and English equally. Swapping in a
real model later is a one-class change because everything downstream depends
only on the `Embedder` protocol.
"""
from __future__ import annotations

from typing import Protocol

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .arabic import normalise


class Embedder(Protocol):
    def fit_transform(self, texts: list[str]) -> np.ndarray: ...
    @property
    def name(self) -> str: ...


class TfidfCharEmbedder:
    """Offline default. Character 3-5 grams over normalised text."""

    def __init__(self, max_features: int = 4096):
        self._vec = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(3, 5),
            max_features=max_features,
        )

    def fit_transform(self, texts: list[str]) -> np.ndarray:
        norm = [normalise(t) or " " for t in texts]
        return self._vec.fit_transform(norm).toarray().astype(np.float32)

    @property
    def name(self) -> str:
        return "tfidf_char_wb_3-5"


# Seam for the production path. Left unimplemented on purpose so it is honestly
# "not built" rather than a silent stub that returns garbage.
class MultilingualModelEmbedder:
    def __init__(self, model_id: str):
        raise NotImplementedError(
            "Wire a multilingual sentence model here (e.g. a multilingual MiniLM "
            "or an Arabic-specialised model). Interface matches TfidfCharEmbedder."
        )
