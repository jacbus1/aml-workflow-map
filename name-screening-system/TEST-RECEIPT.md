# Test Receipt — Name Screening System v0.1.0

Date: 2026-09-16  
Live-gate update: 2026-09-17

## Local automated suite

```text
.........                                                                [100%]
9 passed in 0.60s
```

The suite covered normalization, reversed names, exact alias selection, DOB match/mismatch without hard filtering, threshold rejection, generic CSV import, OFAC SDN+ALT joining, HTTP health/import/screen/batch, UI route, and OFAC import followed by screening.

## Runtime smoke test

A local Uvicorn instance was started successfully after bootstrapping four fictional demo records.

Observed `/health`:

```json
{"ok":true,"stats":{"entities":4,"screenings":0,"by_source":{"DEMO":4}}}
```

Observed fuzzy case: `Muhamad Ahmad Khan` matched alias `Muhammad Ahmad Khan` with name similarity `97.3`; matching DOB and country produced final score `100.0`.

Batch smoke test returned 100.0 matches for the four intended demo variants and no result above threshold for `Completely Different Person`.

## External OFAC live refresh

**PASS in GitHub Actions.** The release-gate workflow now runs `python -m app.source_sync` on a networked GitHub-hosted runner, downloads the fixed OFAC SLS `SDN.CSV` and `ALT.CSV` sources, parses and upserts the result, recomputes SHA-256 from the saved bytes, verifies byte counts and source URLs, checks the SQLite OFAC row count, and uploads the source snapshot plus receipt files as a workflow artifact.

Initial live validation receipt:

- PR head tested: `a4f8a235f1510ad7c2e877c76d688c59d15d9b71`
- PR merge commit tested: `07b55c94f6a8add7ad70328a94e4793c3f750edd`
- GitHub Actions run: `35192054894`
- Result: `PASS`
- OFAC records parsed/upserted: `19,385`
- SQLite `OFAC_SDN` records: `19,385`
- `SDN.CSV`: 5,691,983 bytes; SHA-256 `f4424647eb39496c234a1586ef1af11f9d202813aaac732f3ceeaba21bed0884`
- `ALT.CSV`: 1,063,992 bytes; SHA-256 `fa40fd1d5143e534477735ca01f03d3bec190dcbb549c1c9685361817c71852c`
- Artifact ID: `10484197442`
- Artifact ZIP SHA-256: `3c79102e31633e0130d794cc6ca2fa14aa7dfe8e6ff01cad2b077034b18dd48d`

The OFAC source files are live publications and can change when OFAC updates its lists. The hashes above are therefore evidence for the stated retrieval run, not hard-coded expected values. Current CI repeats the live retrieval and self-consistency checks instead of requiring those historical hashes to remain unchanged.
