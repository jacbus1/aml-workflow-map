# Jac-Name-Screening v2.0 Development Plan (English)

## 1. Objective

Jac-Name-Screening v2.0 is not just a fuzzy-search demo. It is intended to become a reproducible, explainable and auditable sanctions/name-screening workstation with measurable false-negative performance.

Priorities:

1. **Reduce false negatives** across spelling variants, aliases, transliteration, name order and incomplete secondary identifiers.
2. **Control false positives** from short names, corporate suffixes and low-quality aliases.
3. **Prefer official sources** and retain source IDs, versions, timestamps, hashes and provenance.
4. **Explain every candidate** with matched name/alias, name score, DOB/country evidence and penalties.
5. **Audit screenings** with thresholds, source snapshots, result counts and version data.
6. **Measure recall** using a known-positive benchmark before release.
7. **Keep photo verification separate**: official-photo side-by-side review first; optional local face similarity remains assistive and off by default.

## 2. v2 Architecture

```text
Official Sources
OFAC / UK / Canada / UN
        │
        ▼
Source adapters + validation
        │
        ▼
Canonical screening records
primary / strong aliases / weak aliases / native names
DOBs / countries / programs / source IDs
        │
        ▼
Explainable Matching Engine
        │
        ├── exact / normalized
        ├── token/order similarity
        ├── transliteration
        ├── strong vs weak alias weighting
        ├── DOB evidence
        └── country evidence
        │
        ▼
Candidate ranking
        │
        ▼
Analyst review + audit trail
```

## 3. P0 Data Sources

### OFAC
- SDN first; Consolidated Non-SDN follows.
- Legacy importer accepts primary, ALT, ADD and comments files.
- Strong and weak aliases are separated.
- Records are joined by UID before storage.

### UK Sanctions List
- Use the current UK Sanctions List rather than the closed OFSI Consolidated List.
- Group CSV rows by `Unique ID`.
- Treat `Primary Name`, `Primary Name Variation` and `Alias` separately.
- Low-quality aliases are stored as weak aliases.

### Canada
- Adapter for the Consolidated Canadian Autonomous Sanctions List XML.
- Preserve regulation/schedule/item/listing metadata where available.

### UN
- Adapter for the UN Security Council Consolidated List XML.
- Good-quality a.k.a. → strong alias.
- Low-quality a.k.a. → weak alias.
- Preserve multiple DOBs, nationalities and original-script names.

## 4. Matching Engine v2

### 4.1 Normalization
- Unicode NFKD
- case normalization
- punctuation / whitespace
- accents
- transliteration
- tokenization

### 4.2 Candidate names
- primary name
- strong alias
- weak alias
- native-script transliteration

### 4.3 False-positive controls
- Penalize single-token queries.
- Penalize subset matches driven by corporate suffixes such as LTD/LLC/PLC/HOLDINGS/GROUP.
- Apply a weak-alias penalty and confidence cap.

### 4.4 DOB / country evidence
- Use DOB/country as supporting or contradicting evidence rather than universal hard filters.
- Support multiple and year-only DOB values.
- Apply only limited country mismatch penalties where source data may be incomplete.

### 4.5 Output
- `score`
- `name_score`
- `match_kind`
- `matched_name`
- `dob_status`
- `country_status`
- `risk_band` (candidate priority only, not a legal conclusion)
- `score_breakdown`

## 5. Source Refresh and Integrity

All formal replacements must be atomic:

```text
Download / Upload
→ parse
→ validation
→ non-empty / sanity check
→ SHA-256
→ BEGIN TRANSACTION
→ delete old source
→ insert new source
→ write source snapshot receipt
→ COMMIT
```

A parser or validation failure must leave the previous source dataset intact.

## 6. API / Security

- upload size limit
- batch row limit
- reject blank names
- CSV formula-injection escaping
- security headers
- never commit production PII
- do not require persistent biometric embeddings

## 7. Photo Verification (Optional v2 Module)

```text
Candidate hit
→ official photo provenance
→ manual side-by-side review
→ optional local face detection/alignment/embedding
→ similarity score
→ human review required
```

Principles:
- Off by default.
- 1:1 verification for a selected candidate; no open-web reverse face search.
- Output `LOW / REVIEW / HIGH similarity`, not automatic identity confirmation.
- Retain source URL, retrieval time, image SHA-256 and model/version; prefer ephemeral KYC embeddings.

## 8. Multi-Agent QA Workflow

### Manager Agent
Accepts only releases that satisfy all gates and consolidates agent results.

### Source Agent
Tests parsers, source IDs, aliases, DOBs, atomic refresh and stale deletion.

### Matching/Data Scientist Agent
Runs known-positive recall, mutation tests, false-positive controls and threshold regressions.

### Security/QA Agent
Tests malformed uploads, oversized batches, blank names, CSV injection, security headers and error paths.

### Identity Agent
Checks alias strength, multiple DOBs, native script, entity resolution and photo provenance.

v2 starts with **deterministic reproducible QA agents**. LLMs do not make final sanctions dispositions.

## 9. Release Gates

- all unit/integration tests pass
- runtime smoke test passes
- atomic source replacement passes
- empty-refresh protection passes
- stale rows are removed
- strong/weak alias routing passes
- multiple DOB support passes
- subset false-positive regression passes
- Unicode/transliteration passes
- batch limits / malformed CSV pass
- CSV injection protection passes
- known-positive benchmark reaches the target threshold
- source snapshot/hash receipt is reproducible

## 10. Famous/Public-Person Benchmark Rules

- Positive controls must be verifiable in official sources.
- Each test retains `source + source_id + as_of + official URL`.
- Test exact names, common short forms, reordering and small spelling variations.
- Negative controls mean only “not present in this benchmark fixture”; they are **not** global legal conclusions about sanctions status.

## 11. Implementation Phases

### Phase 1 — Executed in this iteration
- v2 matching engine
- strong / weak aliases
- multiple DOBs
- atomic source replacement + source snapshots
- OFAC four-file importer
- UK CSV adapter
- UN XML adapter
- Canada XML adapter (tolerant schema mapping)
- API hardening
- deterministic multi-agent QA runner
- public-person benchmark

### Phase 2
- OFAC Advanced XML / Consolidated Non-SDN
- canonical cross-source entity resolution
- PostgreSQL production schema
- source-diff dashboard

### Phase 3
- official-photo provenance
- manual photo-compare UI
- optional local face similarity
- threshold validation dataset

### Phase 4
- PEP/RCA connector
- adverse media as a separate risk signal
- ownership/network graph
