# Name Screening System

A runnable local sanctions/watchlist name-screening MVP with explainable fuzzy matching, aliases, DOB/country corroboration, CSV batch screening, SQLite persistence, and an OFAC SDN importer.

## What it does

- Single-name screening in a browser.
- Fuzzy name matching using RapidFuzz (`ratio`, token sort/set, WRatio, reversed-name comparison).
- Alias/AKA matching: the highest-scoring primary/alias name is used and reported.
- Unicode normalization + transliteration with `Unidecode`.
- DOB and country are **ranking signals, not hard filters**.
- Generic CSV watchlist import.
- OFAC SDN flat-file import (`SDN.CSV` + optional `ALT.CSV`).
- Batch customer CSV screening with downloadable CSV results.
- SQLite audit receipt for each single screening request.

> Candidate matches require human review. This is not a turnkey production AML control without validation, governance, list-refresh monitoring, access controls and documented threshold calibration.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts_bootstrap.py
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

## Tests

```bash
pip install -r requirements-dev.txt
pytest -q
```

Local receipt for this version: **9 passed** plus Uvicorn `/health`, single-screen and batch smoke tests.

## OFAC refresh

On a networked machine:

```bash
python -m app.source_sync
```

The refresh uses fixed allow-listed OFAC SDN/ALT publication URLs, stores SHA-256 receipts, joins aliases by entity number and upserts to SQLite.

## Data safety

Only fictional demo data is committed. Do not commit real customer PII, credentials, account data or investigation notes.
