# Test Receipt — Name Screening System v0.1.0

Date: 2026-09-16

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

**NOT_RUN in the local execution sandbox.** Python/container outbound DNS was unavailable. The OFAC-format parser, HTTP import endpoint, alias join and screening flow were tested with committed fixtures. Run `python -m app.source_sync` on a networked machine to exercise live list retrieval and generate SHA-256 download receipts.
