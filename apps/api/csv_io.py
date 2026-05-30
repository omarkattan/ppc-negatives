"""CSV import/export for the negative keyword tool.

Real Google Ads search-terms exports vary in column naming and often carry two
header rows and a totals row. This parser is lenient: it finds the header row,
maps known column aliases, and skips totals. Export produces a Google Ads bulk
upload shaped CSV for approved negatives.
"""
from __future__ import annotations

import csv
import io
import uuid
from typing import Iterable

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "services"))
from negative_keywords.arabic import contains_arabic  # noqa: E402
from negative_keywords.models import SearchTerm  # noqa: E402

# Map normalised header text -> canonical field.
_ALIASES = {
    "search term": "text", "searchterm": "text", "query": "text",
    "campaign": "campaign_id",
    "ad group": "ad_group_id", "adgroup": "ad_group_id",
    "keyword": "matched_keyword", "matched keyword": "matched_keyword",
    "impressions": "impressions", "impr": "impressions", "impr.": "impressions",
    "clicks": "clicks",
    "cost": "cost", "spend": "cost",
    "conversions": "conversions", "conv": "conversions", "conversions.": "conversions",
    "conv value": "conversion_value", "conv. value": "conversion_value",
    "conversion value": "conversion_value", "total conv. value": "conversion_value",
    "revenue": "conversion_value", "value": "conversion_value",
}


def _norm_header(h: str) -> str:
    return h.strip().lower().replace("_", " ")


def _to_float(v: str) -> float:
    if v is None:
        return 0.0
    v = str(v).replace(",", "").replace("AED", "").replace("$", "").strip()
    try:
        return float(v) if v not in ("", "-", "--") else 0.0
    except ValueError:
        return 0.0


def parse_search_terms(data: bytes) -> list[SearchTerm]:
    # Google Ads exports are often UTF-16 tab-separated or UTF-8 comma-separated.
    text = None
    for enc in ("utf-8-sig", "utf-16", "utf-8"):
        try:
            text = data.decode(enc)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    if text is None:
        text = data.decode("utf-8", errors="replace")

    delimiter = "\t" if text.count("\t") > text.count(",") else ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if not rows:
        return []

    # Find the header row: the first row containing a recognised search-term alias.
    header_idx = None
    for i, row in enumerate(rows[:5]):
        norm = [_norm_header(c) for c in row]
        if any(c in ("search term", "searchterm", "query") for c in norm):
            header_idx = i
            break
    if header_idx is None:
        header_idx = 0

    headers = [_norm_header(c) for c in rows[header_idx]]
    field_map = {idx: _ALIASES[h] for idx, h in enumerate(headers) if h in _ALIASES}

    terms: list[SearchTerm] = []
    for row in rows[header_idx + 1:]:
        if not row or all(not c.strip() for c in row):
            continue
        record = {}
        for idx, field in field_map.items():
            if idx < len(row):
                record[field] = row[idx]
        text_val = (record.get("text") or "").strip()
        if not text_val or text_val.lower().startswith("total"):
            continue
        terms.append(SearchTerm(
            term_id=str(uuid.uuid4())[:8],
            text=text_val,
            campaign_id=(record.get("campaign_id") or "unknown").strip(),
            ad_group_id=(record.get("ad_group_id") or "unknown").strip(),
            matched_keyword=(record.get("matched_keyword") or None),
            impressions=int(_to_float(record.get("impressions", 0))),
            clicks=int(_to_float(record.get("clicks", 0))),
            cost=_to_float(record.get("cost", 0)),
            conversions=_to_float(record.get("conversions", 0)),
            conversion_value=_to_float(record.get("conversion_value", 0)),
            language="ar" if contains_arabic(text_val) else "en",
        ))
    return terms


def export_negatives_csv(recommendations: Iterable[dict]) -> str:
    """Google Ads Editor friendly bulk negative format."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Keyword", "Match type", "Level", "Campaign", "Notes"])
    for r in recommendations:
        p = r.get("payload", {})
        writer.writerow([
            p.get("suggested_negative", ""),
            p.get("match_type", "phrase").title(),
            p.get("scope", "campaign"),
            "", r.get("explanation", "")[:200],
        ])
    return out.getvalue()
