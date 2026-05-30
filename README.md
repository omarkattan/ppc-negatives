# PPC Optimisation Platform

An AI PPC optimisation platform for agencies and GCC-first advertisers, with Arabic localisation treated as a day-one requirement rather than a translation afterthought.

This repository is an honest, incremental build. It does not pretend to be the full production platform described in the original brief, because that is a multi-team programme spanning four ad-platform connectors, two ML-heavy engines, a Next.js workbench, an analytics store, and an evaluation suite. What is here is a real, runnable, tested core of the highest-value and most self-contained piece, plus the data contract everything else has to conform to.

## What is built and runnable right now

1. **Shared recommendation contract** (`packages/shared/ppc_shared/recommendation.py`)
   A single pydantic-validated envelope that every engine must emit: recommendation id, account id, feature type, confidence, estimated impact (with optional confidence interval), explanation, constraints, risk flags, approval status, autopilot-safe flag, generated_at, model_version, and source references back to the raw data. This is priority #1 from the brief: data-model correctness comes before everything.

2. **Negative keyword engine, Feature C** (`apps/api/services/negative_keywords/`)
   The brief states this must be excellent and it needs no live credentials, so it is the first thing built end to end. Four layers:
   - **Layer 1, deterministic rules** (`rules.py`): no-conversion-after-threshold, cost-with-no-value, CPA-far-above-target, off-target lexicon matches (jobs, support, free, student/research) in English and Gulf Arabic, competitor terms, brand-whitelist protection, and conflict detection against active positive keywords.
   - **Layer 2, n-gram mining** (`ngrams.py`): unigram/bigram/trigram aggregation across the whole report to find recurring wasteful n-grams, plus a protective conversion-assisting set used as a veto so the engine never recommends a token that also drives sales.
   - **Layer 3, semantic clustering** (`clustering.py` + `embeddings.py`): embeds every search term and clusters by similarity, then scores clusters on aggregate performance so a reviewer makes one decision instead of fifty. The embedder is behind a `Embedder` protocol.
   - **Layer 4, intent classification** (`intent.py`): a transparent lexicon classifier across the brief's nine-label taxonomy, English and Arabic, with a user-correction feedback map and a swappable `IntentClassifier` protocol.
   - **Engine** (`engine.py`): orchestrates the layers, applies the safety model, and emits contract-conformant `Recommendation` objects.

3. **Arabic normalisation** (`arabic.py`): diacritic and tatweel stripping, alef/taa-marbuta/alef-maqsura folding, Arabic-Indic and Eastern Arabic-Indic digit folding, mixed-script tokenisation.

4. **Seeded demo data** (`apps/api/data/demo_search_terms.py`): an English-first account and a bilingual GCC account, each with genuine off-target and genuine high-intent terms so the engine has to discriminate.

5. **Tests** (`tests/`): 26 passing tests covering normalisation, every rule, n-gram mining, intent classification, and full-pipeline integration including contract conformance and the safety invariants.

## The safety model (what makes this beat naive tools)

Naive negative-keyword tools blanket-negate anything with spend and no conversions, which quietly kills demand. This engine is conservative by construction:

- Brand-whitelisted terms never produce a suggestion.
- A converting token can never become a shared-list negative (the assisting-n-gram veto).
- The assist veto is correctly scoped to match type: a phrase negative of a full multi-word term cannot block a different query that merely shares a token, so it is not vetoed, but a broad or single-token negative that overlaps converting traffic is.
- `autopilot_safe` is granted only for high-confidence, zero-conversion, low-risk, no-conflict suggestions. Portfolio-wide and shared-list actions are always approval-only. Everything else defaults to pending approval. There is no unsafe autopilot by default.

## What is mocked or deferred (honest map)

- **Embeddings**: the default `TfidfCharEmbedder` runs offline. The production multilingual / Arabic-specialised model path (`MultilingualModelEmbedder`) is a deliberate `NotImplementedError` seam, not a silent stub, because the sandbox cannot download model weights.
- **Intent model**: lexicon-based for the MVP. The `IntentClassifier` protocol lets a fine-tuned multilingual model drop in without touching the engine.
- **Features A (text ads) and B (budget optimiser)**: not built in this increment. The recommendation contract is designed so they slot in as additional `FeatureType` values.
- **Connectors, ingestion, approval workflow service, reporting, web UI, Slack/WhatsApp, ClickHouse, Docker**: not in this increment.
- **Scoring model for ranking**: the brief's gradient-boosted ranker is represented here by the transparent weighted-evidence aggregation in `engine.py`. It is intentionally explainable for the MVP and the interface is modular so a learned ranker can replace it once labelled acceptance data exists.

## Model and rule choices

- Confidence aggregates multiple weak signals with diminishing returns (`1 - prod(1 - w)`) rather than summing, so three soft hits raise confidence without ever reaching certainty.
- High-purchase-intent classification down-weights confidence by 0.7, because the cost of negating a converting term dwarfs the cost of missing a bit of waste.
- Character n-gram TF-IDF was chosen as the offline embedder because it is genuinely script-agnostic: character trigrams handle Arabic morphology and English equally without a downloaded model.

## Running it

```bash
pip install pydantic scikit-learn numpy pytest
cd ppc-platform
python -m pytest -q                 # 26 tests
PYTHONPATH=packages/shared:apps/api/services:apps/api/data \
  python3 -c "from demo_search_terms import gcc_bilingual_account; \
  from negative_keywords.engine import run_engine; \
  a,t,c = gcc_bilingual_account(); r = run_engine(a,t,c); print(r.summary())"
```

## Next-step upgrade plan (priority order)

1. Wire a multilingual sentence model behind `Embedder` and an Arabic reranker, keeping the offline default as fallback.
2. Add a labelled-review store and an evaluation harness for the negative engine: precision@k, recall@k, false-positive rate, wasted-spend-prevented, value-lost-from-incorrect-negatives.
3. Build the Google Ads connector in mock-first mode (search-terms report ingest), then the approval workflow service (draft, approve, reject, push, rollback) so suggestions become applied actions with an audit trail.
4. Replace the weighted-evidence ranker with a gradient-boosted ranker trained on accumulated acceptance feedback.
5. Build Feature A (text ads) against the same contract, reusing the policy validators.
6. Build Feature B (budget optimiser): forecasting, response curves, constrained reallocation, scenario simulator.
7. Build the Next.js workbench with RTL-safe layout, then connectors for Meta, TikTok, LinkedIn in read-only mode.
