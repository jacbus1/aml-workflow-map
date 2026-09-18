from __future__ import annotations

import csv
import io
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from .db import (
    bytes_sha256,
    get_entities,
    init_db,
    record_screening,
    replace_source_atomic,
    stats,
    upsert_entities,
)
from .importers import (
    PARSER_VERSION,
    CANADA_SOURCE_URL,
    OFAC_SOURCE_URL,
    UK_SOURCE_URL,
    UN_SOURCE_URL,
    parse_canada_xml,
    parse_generic_csv,
    parse_ofac_sdn,
    parse_uk_sanctions_csv,
    parse_un_xml,
)
from .matching import normalize_name, screen

DB_PATH = os.environ.get("SCREENING_DB", "data/screening.db")
STATIC = Path(__file__).parent / "static"
MAX_UPLOAD_BYTES = int(os.environ.get("SCREENING_MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
MAX_BATCH_ROWS = int(os.environ.get("SCREENING_MAX_BATCH_ROWS", "5000"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db(DB_PATH)
    yield


app = FastAPI(title="Jac Name Screening", version="2.0.0", lifespan=lifespan)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cache-Control"] = "no-store"
    return response


class ScreenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    dob: str | None = Field(default=None, max_length=80)
    country: str | None = Field(default=None, max_length=120)
    threshold: float = Field(default=80, ge=0, le=100)
    limit: int = Field(default=20, ge=1, le=100)
    source: str | None = Field(default=None, max_length=100)
    include_weak_aliases: bool = True

    @field_validator("name")
    @classmethod
    def non_blank_name(cls, value: str) -> str:
        if not normalize_name(value):
            raise ValueError("name must contain non-whitespace characters")
        return value.strip()


async def _read_limited(file: UploadFile | None) -> bytes | None:
    if file is None:
        return None
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Upload exceeds {MAX_UPLOAD_BYTES} bytes")
    return data


def _snapshot(data_parts: list[bytes | None], source_url: str) -> dict:
    joined = b"\n--JNS-PART--\n".join(x for x in data_parts if x is not None)
    return {
        "sha256": bytes_sha256(joined),
        "source_url": source_url,
        "parser_version": PARSER_VERSION,
    }


def _safe_csv_cell(value: object) -> str:
    s = "" if value is None else str(value)
    if s.startswith(("=", "+", "-", "@")):
        return "'" + s
    return s


@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health():
    return {"ok": True, "version": "2.0.0", "stats": stats(DB_PATH)}


@app.get("/api/stats")
def api_stats():
    return stats(DB_PATH)


@app.post("/api/screen")
def api_screen(req: ScreenRequest):
    entities = get_entities(DB_PATH, req.source)
    request_id = str(uuid.uuid4())
    results = screen(
        req.name,
        entities,
        req.dob,
        req.country,
        req.threshold,
        req.limit,
        include_weak_aliases=req.include_weak_aliases,
    )
    record_screening({
        "request_id": request_id,
        "query_name": req.name,
        "query_dob": req.dob,
        "query_country": req.country,
        "threshold": req.threshold,
        "candidate_count": len(entities),
        "matched_count": len(results),
    }, DB_PATH)
    return {
        "request_id": request_id,
        "query": req.model_dump(),
        "candidate_count": len(entities),
        "matches": results,
    }


@app.post("/api/import/generic")
async def import_generic(
    file: UploadFile = File(...),
    source: str = Form("custom"),
    replace_source: bool = Form(False),
):
    data = await _read_limited(file)
    rows = parse_generic_csv(data or b"", source=source)
    if not rows:
        raise HTTPException(400, "No valid rows. Expected a primary_name/name/full_name column.")
    if replace_source:
        result = replace_source_atomic(
            source,
            rows,
            DB_PATH,
            snapshot=_snapshot([data], "uploaded:generic"),
        )
        return {**result, "upserted": result["inserted"], "replaced": True}
    return {"source": source, "upserted": upsert_entities(rows, DB_PATH), "replaced": False}


@app.post("/api/import/ofac")
async def import_ofac(
    primary: UploadFile = File(...),
    aliases: UploadFile | None = File(None),
    addresses: UploadFile | None = File(None),
    comments: UploadFile | None = File(None),
    replace_source: bool = Form(True),
):
    p = await _read_limited(primary)
    a = await _read_limited(aliases)
    d = await _read_limited(addresses)
    c = await _read_limited(comments)
    rows = parse_ofac_sdn(p or b"", a, d, c)
    if not rows:
        raise HTTPException(400, "No OFAC rows parsed")
    if replace_source:
        result = replace_source_atomic(
            "OFAC_SDN", rows, DB_PATH,
            snapshot=_snapshot([p, a, d, c], OFAC_SOURCE_URL),
        )
        return {**result, "upserted": result["inserted"], "replaced": True}
    return {"source": "OFAC_SDN", "upserted": upsert_entities(rows, DB_PATH), "replaced": False}


@app.post("/api/import/uk")
async def import_uk(file: UploadFile = File(...), replace_source: bool = Form(True)):
    data = await _read_limited(file)
    rows = parse_uk_sanctions_csv(data or b"")
    if not rows:
        raise HTTPException(400, "No UK Sanctions List rows parsed")
    if replace_source:
        result = replace_source_atomic(
            "UK_SANCTIONS", rows, DB_PATH,
            snapshot=_snapshot([data], UK_SOURCE_URL),
        )
        return {**result, "upserted": result["inserted"], "replaced": True}
    return {"source": "UK_SANCTIONS", "upserted": upsert_entities(rows, DB_PATH), "replaced": False}


@app.post("/api/import/un")
async def import_un(file: UploadFile = File(...), replace_source: bool = Form(True)):
    data = await _read_limited(file)
    try:
        rows = parse_un_xml(data or b"")
    except Exception as exc:
        raise HTTPException(400, f"Invalid UN XML: {exc}") from exc
    if not rows:
        raise HTTPException(400, "No UN rows parsed")
    if replace_source:
        result = replace_source_atomic(
            "UN_CONSOLIDATED", rows, DB_PATH,
            snapshot=_snapshot([data], UN_SOURCE_URL),
        )
        return {**result, "upserted": result["inserted"], "replaced": True}
    return {"source": "UN_CONSOLIDATED", "upserted": upsert_entities(rows, DB_PATH), "replaced": False}


@app.post("/api/import/canada")
async def import_canada(file: UploadFile = File(...), replace_source: bool = Form(True)):
    data = await _read_limited(file)
    try:
        rows = parse_canada_xml(data or b"")
    except Exception as exc:
        raise HTTPException(400, f"Invalid Canada XML: {exc}") from exc
    if not rows:
        raise HTTPException(400, "No Canadian consolidated-list rows parsed")
    if replace_source:
        result = replace_source_atomic(
            "CANADA_CONSOLIDATED", rows, DB_PATH,
            snapshot=_snapshot([data], CANADA_SOURCE_URL),
        )
        return {**result, "upserted": result["inserted"], "replaced": True}
    return {"source": "CANADA_CONSOLIDATED", "upserted": upsert_entities(rows, DB_PATH), "replaced": False}


@app.post("/api/batch")
async def batch_screen(
    file: UploadFile = File(...),
    threshold: float = Form(80),
    source: str | None = Form(None),
    include_weak_aliases: bool = Form(True),
):
    if threshold < 0 or threshold > 100:
        raise HTTPException(400, "threshold must be between 0 and 100")
    raw = await _read_limited(file)
    data = (raw or b"").decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(data))
    if not reader.fieldnames or not any(x in reader.fieldnames for x in ("name", "full_name", "primary_name")):
        raise HTTPException(400, "CSV must include name, full_name, or primary_name")
    rows = list(reader)
    if len(rows) > MAX_BATCH_ROWS:
        raise HTTPException(413, f"Batch exceeds {MAX_BATCH_ROWS} rows")

    entities = get_entities(DB_PATH, source)
    output = io.StringIO()
    fields = [
        "input_name", "input_dob", "input_country", "best_score", "risk_band", "matched_name",
        "primary_name", "source", "source_id", "match_kind", "alias_strength", "dob_status", "country_status",
    ]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in rows:
        name = (row.get("name") or row.get("full_name") or row.get("primary_name") or "").strip()
        dob = row.get("dob") or row.get("date_of_birth") or None
        country = row.get("country") or row.get("nationality") or None
        matches = screen(name, entities, dob, country, threshold, 1, include_weak_aliases) if normalize_name(name) else []
        m = matches[0] if matches else {}
        writer.writerow({
            "input_name": _safe_csv_cell(name),
            "input_dob": _safe_csv_cell(dob or ""),
            "input_country": _safe_csv_cell(country or ""),
            "best_score": m.get("score", ""),
            "risk_band": m.get("risk_band", ""),
            "matched_name": _safe_csv_cell(m.get("matched_name", "")),
            "primary_name": _safe_csv_cell(m.get("primary_name", "")),
            "source": _safe_csv_cell(m.get("source", "")),
            "source_id": _safe_csv_cell(m.get("source_id", "")),
            "match_kind": m.get("match_kind", ""),
            "alias_strength": m.get("alias_strength", ""),
            "dob_status": m.get("dob_status", ""),
            "country_status": m.get("country_status", ""),
        })
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=screening_results.csv"},
    )
