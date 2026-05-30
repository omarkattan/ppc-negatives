"""Layer 4: intent classifier.

Classifies each search term into a purchase-intent taxonomy in English and
Arabic. The MVP is a transparent lexicon + signal classifier: every decision is
explainable, which matters because misclassifying a high-intent term as
irrelevant and negating it loses real revenue. The `IntentClassifier` protocol
lets a fine-tuned multilingual model replace this later without touching the
engine. User corrections feed back via the `corrections` map.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .arabic import normalise
from .models import IntentLabel, SearchTerm
from .rules import LOW_INTENT_LEXICON

# High-intent transactional signals.
HIGH_INTENT = {
    "en": ["buy", "price", "order", "shop", "for sale", "near me", "delivery", "quote", "book", "subscribe", "discount price", "best"],
    "ar": ["شراء", "اشتري", "سعر", "اسعار", "طلب", "توصيل", "حجز", "اشتراك", "للبيع", "قريب مني", "افضل"],
}


@dataclass
class IntentResult:
    label: IntentLabel
    confidence: float
    signals: list[str] = field(default_factory=list)


class IntentClassifier(Protocol):
    def classify(self, term: SearchTerm) -> IntentResult: ...


class LexiconIntentClassifier:
    def __init__(self, corrections: dict[str, IntentLabel] | None = None):
        # corrections: normalised term text -> human-confirmed label
        self.corrections = corrections or {}

    def classify(self, term: SearchTerm) -> IntentResult:
        norm = normalise(term.text)
        if norm in self.corrections:
            return IntentResult(self.corrections[norm], 0.99, ["user_correction"])

        signals: list[str] = []

        # Transactional signals win when present and the term actually converted
        # or shows buying language.
        high_hit = next((p for langs in [HIGH_INTENT] for plist in langs.values()
                         for p in plist if normalise(p) in norm), None)
        if term.conversions > 0:
            return IntentResult(IntentLabel.HIGH_PURCHASE_INTENT, 0.9,
                                ["recorded_conversions"] + ([high_hit] if high_hit else []))
        if high_hit:
            signals.append(f"high_intent:{high_hit}")
            return IntentResult(IntentLabel.HIGH_PURCHASE_INTENT, 0.7, signals)

        # Off-target lexicon categories map to specific labels.
        category_to_label = {
            "jobs": IntentLabel.JOBS,
            "support": IntentLabel.SUPPORT,
            "free": IntentLabel.LOW_PURCHASE_INTENT,
            "student_research": IntentLabel.STUDENT_RESEARCH,
        }
        for category, langs in LOW_INTENT_LEXICON.items():
            for plist in langs.values():
                for p in plist:
                    if normalise(p) in norm:
                        signals.append(f"{category}:{p}")
                        return IntentResult(category_to_label[category], 0.75, signals)

        # Informational question shapes with no transactional cue.
        informational_markers = ["what is", "how", "why", "guide", "ما هو", "كيف", "لماذا", "دليل"]
        if any(normalise(m) in norm for m in informational_markers):
            return IntentResult(IntentLabel.INFORMATIONAL, 0.6, ["question_shape"])

        return IntentResult(IntentLabel.UNCERTAIN, 0.4, ["no_clear_signal"])
