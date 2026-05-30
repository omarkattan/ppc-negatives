"""Seeded demo data: one English-first account and one bilingual GCC account.

The Arabic terms include genuine off-target patterns (jobs, free, definitions)
and genuine high-intent terms (buy, price, delivery) so the engine has to
distinguish them, not just blanket-negate Arabic.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "services"))

from negative_keywords.models import EngineConfig, SearchTerm  # noqa: E402


def english_account() -> tuple[str, list[SearchTerm], EngineConfig]:
    terms = [
        SearchTerm("en-1", "buy running shoes online", "c1", "g1", "running shoes", 1200, 60, 240.0, 8, 1600.0),
        SearchTerm("en-2", "running shoes price", "c1", "g1", "running shoes", 800, 40, 120.0, 5, 950.0),
        SearchTerm("en-3", "free running shoes", "c1", "g1", "running shoes", 500, 35, 95.0, 0, 0.0),
        SearchTerm("en-4", "running shoes repair near me", "c1", "g1", "running shoes", 300, 28, 70.0, 0, 0.0),
        SearchTerm("en-5", "nike shoes jobs", "c1", "g1", "shoes", 200, 30, 60.0, 0, 0.0),
        SearchTerm("en-6", "how to clean running shoes", "c1", "g2", "running shoes", 400, 26, 65.0, 0, 0.0),
        SearchTerm("en-7", "best running shoes for marathon", "c1", "g2", "running shoes", 900, 45, 180.0, 4, 720.0),
        SearchTerm("en-8", "running shoes coupon code", "c1", "g2", "running shoes", 350, 27, 80.0, 0, 0.0),
        SearchTerm("en-9", "shoe customer service number", "c1", "g2", "shoes", 150, 22, 40.0, 0, 0.0),
        SearchTerm("en-10", "running shoes pdf size guide", "c1", "g2", "running shoes", 120, 18, 30.0, 0, 0.0),
        SearchTerm("en-11", "marathon shoes for sale", "c1", "g1", "running shoes", 600, 33, 130.0, 3, 540.0),
        SearchTerm("en-12", "cheap fake running shoes", "c1", "g1", "running shoes", 280, 26, 58.0, 0, 0.0),
    ]
    cfg = EngineConfig(currency="USD", target_cpa=30.0, target_roas=4.0,
                       brand_whitelist=["Acme"],
                       positive_keywords=["running shoes", "marathon shoes"])
    return "acct_english", terms, cfg


def gcc_bilingual_account() -> tuple[str, list[SearchTerm], EngineConfig]:
    terms = [
        SearchTerm("ar-1", "شراء عطور فاخرة اون لاين", "c2", "g3", "عطور فاخرة", 1000, 50, 300.0, 7, 2100.0, language="ar"),
        SearchTerm("ar-2", "اسعار العطور الفاخرة", "c2", "g3", "عطور فاخرة", 700, 38, 190.0, 4, 1200.0, language="ar"),
        SearchTerm("ar-3", "عطور مجانية", "c2", "g3", "عطور", 400, 32, 95.0, 0, 0.0, language="ar"),
        SearchTerm("ar-4", "وظائف شركة عطور", "c2", "g3", "عطور", 250, 30, 70.0, 0, 0.0, language="ar"),
        SearchTerm("ar-5", "ما هو افضل عطر", "c2", "g4", "عطر", 500, 28, 80.0, 0, 0.0, language="ar"),
        SearchTerm("ar-6", "توصيل عطور دبي", "c2", "g4", "عطور دبي", 800, 40, 200.0, 6, 1800.0, language="ar"),
        SearchTerm("ar-7", "كوبون خصم عطور", "c2", "g4", "عطور", 300, 27, 75.0, 0, 0.0, language="ar"),
        SearchTerm("ar-8", "رقم خدمة العملاء عطور", "c2", "g4", "عطور", 180, 24, 55.0, 0, 0.0, language="ar"),
        SearchTerm("ar-9", "عطور للبيع في السعودية", "c2", "g3", "عطور السعودية", 650, 34, 160.0, 5, 1500.0, language="ar"),
        SearchTerm("ar-10", "تعريف العطور العود", "c2", "g4", "عطر عود", 220, 20, 48.0, 0, 0.0, language="ar"),
        SearchTerm("en-ar-1", "buy oud perfume dubai", "c2", "g3", "oud perfume", 900, 42, 230.0, 6, 1900.0),
        SearchTerm("en-ar-2", "free perfume samples", "c2", "g3", "perfume", 380, 30, 88.0, 0, 0.0),
    ]
    cfg = EngineConfig(currency="AED", target_cpa=45.0, target_roas=5.0,
                       brand_whitelist=["Siyate", "سيات"],
                       positive_keywords=["عطور فاخرة", "oud perfume", "عطور دبي"])
    return "acct_gcc", terms, cfg
