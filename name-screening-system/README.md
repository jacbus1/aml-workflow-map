# Jac-Name-Screening v2.0

Self-hosted sanctions/name-screening workstation focused on **recall, explainability, source integrity and reproducible QA**.

This repository returns **candidate matches for human review**. A score or candidate band is not a legal conclusion that two people are the same person or that a customer is sanctioned.

## What changed in v2

- Strong aliases and weak/low-quality aliases are stored and scored separately.
- Multiple DOB values are supported, including year-only values.
- Native-script names can participate in transliteration matching.
- Short-name and corporate-suffix subset false positives are penalized.
- DOB/country remain evidence signals instead of universal hard filters.
- Atomic source replacement prevents a failed refresh from clearing the previous list.
- Source snapshot receipts store SHA-256, record count, parser version and source URL.
- OFAC legacy import supports primary + ALT + ADD + comments files.
- UK Sanctions List CSV adapter groups records by `Unique ID` and respects alias quality.
- UN Consolidated List XML adapter separates good- and low-quality aliases.
- Canada XML adapter uses tolerant field mapping for the consolidated autonomous list.
- Upload and batch limits, CSV-formula escaping and browser security headers are included.
- Deterministic multi-agent QA release gate: SourceAgent, Matching/DataScientistAgent, SecurityQAAgent, ManagerAgent.
- Public-person matching benchmark is included as a regression suite.

## Plans

- [中文開發計劃](PLAN-ZH.md)
- [English development plan](PLAN-EN.md)

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts_bootstrap.py
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

### Docker

```bash
docker build -t jac-name-screening .
docker run --rm -p 8000:8000 -v "$PWD/data:/app/data" jac-name-screening
```

## Matching model

### Candidate names

Each entity can contain:

```text
primary_name
aliases          # strong aliases / primary-name variations
weak_aliases     # low-quality aliases
native_names     # original/non-Latin script
multiple DOBs
countries
programs
source identifiers
```

### Name scoring

The engine performs Unicode normalization, transliteration, punctuation/space cleanup and multiple string views. It then applies controls including:

- weak alias penalty and cap;
- single-token non-exact cap;
- corporate suffix subset cap (`LTD`, `LLC`, `PLC`, `HOLDINGS`, `GROUP`, etc.);
- middle/patronymic omission support to protect recall.

DOB/country evidence is added after the best name candidate is selected.

Example response fields:

```json
{
  "score": 96.97,
  "name_score": 96.97,
  "risk_band": "HIGH_CANDIDATE",
  "matched_name": "Roman ABRAMOVICH",
  "match_kind": "alias",
  "alias_strength": "strong",
  "dob_status": "not_provided",
  "country_status": "not_provided"
}
```

`risk_band` is a review-priority label, not an identity or sanctions determination.

## Official-list importers

### OFAC legacy CSV family

`POST /api/import/ofac` accepts:

- `primary` — SDN.CSV
- `aliases` — ALT.CSV (optional)
- `addresses` — ADD.CSV (optional)
- `comments` — SDN_COMMENTS.CSV (optional)
- `replace_source=true|false`

Automatic network refresh on a networked host:

```bash
python -m app.source_sync
```

The refresh downloads fixed official endpoints, validates non-empty data, computes hashes, parses all four files and performs one atomic database replacement.

### UK Sanctions List

`POST /api/import/uk` with the official CSV. Rows are grouped by `Unique ID`; primary names, primary-name variations, aliases and low-quality aliases are separated.

### UN Consolidated List

`POST /api/import/un` with the official XML. The adapter supports individuals/entities, good- vs low-quality aliases, original-script names, multiple DOBs and nationality values.

### Canada Consolidated Autonomous Sanctions List

`POST /api/import/canada` with the official XML. The adapter is tag-tolerant to reduce brittle failures when wrappers change; schema changes must still be regression-tested before production use.

## Generic CSV

Recommended fields:

```csv
source,source_id,entity_type,primary_name,aliases,weak_aliases,native_names,dobs,countries,programs,source_url,remarks
CUSTOM,1,individual,Jane Doe,"Jane D|J Doe","JD","珍·多伊","1985-01-01|1985","Canada|USA",LIST-A,https://example.invalid,Example
```

Multi-values use `|` or `;`.

## Batch screening

Input:

```csv
name,dob,country
Jane Doe,1985-01-01,Canada
```

Output includes best score, candidate band, matched name, source/source ID, alias strength, DOB status and country status.

Limits default to:

- upload: 5 MiB
- batch: 5,000 rows

Override with:

```bash
SCREENING_MAX_UPLOAD_BYTES=10485760
SCREENING_MAX_BATCH_ROWS=10000
```

## Public-person regression benchmark

Run:

```bash
python scripts/run_public_benchmark.py
```

Generated reports:

- `BENCHMARK-ZH.md`
- `BENCHMARK-EN.md`
- `BENCHMARK-RESULTS.json`

The benchmark uses official-source positive controls for well-known public persons and deliberately separate fixture-only negative controls. It is **not** a legal/current global sanctions-status certification.

## Multi-agent QA release gate

```bash
python scripts/release_gate.py
```

Roles:

- **SourceAgent** — source parsing + database replacement integrity
- **MatchingDataScientistAgent** — matching regressions + public-person benchmark
- **SecurityQAAgent** — API/upload/CSV/security controls
- **ManagerAgent** — release only if every role passes

These are deterministic QA roles so the release result is reproducible. LLM output is not used to make final sanctions dispositions.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
python scripts/release_gate.py
python scripts/run_public_benchmark.py
```

See [TEST-RECEIPT.md](TEST-RECEIPT.md) for the latest executed receipt.

## Photo verification roadmap

The v2 plan includes a later optional module for a selected candidate:

```text
customer KYC photo
+ official watchlist photo with provenance
→ manual side-by-side review
→ optional local 1:1 face similarity
→ human review required
```

It will be off by default. The design explicitly avoids open-web reverse face search and automatic identity decisions.

## Data safety

The repository contains only demo/fixture/benchmark data. Do not commit real customer PII, credentials, production investigation notes or biometric templates.

## License

MIT for this repository's code. External sanctions/watchlist data is governed by the publishing authority and applicable law.
