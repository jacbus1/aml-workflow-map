# Jac-Name-Screening v2.0 — Test Receipt

Date: 2026-09-18

## Automated suite

Command:

```bash
python -m pytest -q
```

Result:

```text
31 passed
```

Coverage by behaviour includes:

- Unicode/diacritic/punctuation normalization
- reversed/token-order names
- transliteration
- strong aliases
- weak aliases and weak-alias disable switch
- weak alias score penalty/cap
- multiple DOB values / year-only DOB
- DOB mismatch remains evidence, not a universal hard filter
- country equivalence (`Russian Federation` ↔ `Russia`)
- single-token non-exact cap
- corporate-suffix subset penalty
- blank-name rejection
- generic CSV import
- OFAC primary + ALT join
- OFAC primary + ALT + ADD + comments join
- UK `Unique ID` grouping and alias strength
- UN good/low-quality alias routing, multiple DOB, native script
- Canada tolerant XML adapter
- atomic source replacement
- stale-record deletion
- empty-replacement protection
- source snapshot receipt
- HTTP health/import/screen/batch flow
- browser security headers
- upload size limit
- batch row limit
- CSV formula-injection escaping
- atomic generic source replacement via API
- public-person benchmark regression

## Deterministic multi-agent release gate

Command:

```bash
python scripts/release_gate.py
```

Result:

```text
SourceAgent: PASS       (9 tests)
MatchingDataScientistAgent: PASS  (14 tests)
SecurityQAAgent: PASS   (8 tests)
ManagerAgent: PASS
RELEASE_GATE: PASS
```

## Public-person benchmark

Command:

```bash
python scripts/run_public_benchmark.py
```

Result:

```text
Positive cases: 11/11 PASS
Fixture negative controls: 3/3 PASS
Threshold: 80
```

Name-only typo examples:

```text
Roman Abramovitch  -> Roman ABRAMOVICH      name score 96.97
Viktor Vekselburg  -> Viktor Vekselberg     name score 94.12
```

See `BENCHMARK-ZH.md`, `BENCHMARK-EN.md` and `BENCHMARK-RESULTS.json`.

## Runtime smoke test

A real Uvicorn process was started on `127.0.0.1:8765` using a fresh SQLite database.

Verified:

```text
GET  /health              200
GET  /                    200
POST /api/import/generic  200 (4 records, atomic replace)
POST /api/screen          200
```

End-to-end smoke query:

```text
Input: Oleg Deripaska / 1968-01-02 / Russia
Matched fixture: Oleg Vladimirovich Deripaska
Matched alias: Oleg Deripaska
Final score: 100
Risk band: HIGH_CANDIDATE
```

## Live official-source network sync

`app.source_sync` now uses the OFAC four-file family and an atomic replacement/hash receipt flow.

**Live remote download is NOT_RUN in this receipt.** The execution environment did not provide reliable direct binary/XML download access to the official endpoints. Parser behaviour, joins, source replacement and hashing logic were exercised with fixtures and local integration tests instead.

A networked deployment should run:

```bash
python -m app.source_sync
```

and retain `data/source_cache/OFAC_manifest.json` as source-sync evidence.
