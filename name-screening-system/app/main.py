from __future__ import annotations

import csv
import io
import os
import uuid
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from .db import clear_source, get_entities, init_db, record_screening, stats, upsert_entities
from .importers import parse_generic_csv, parse_ofac_sdn
from .matching import screen

DB_PATH = os.environ.get("SCREENING_DB", "data/screening.db")
STATIC = Path(__file__).parent / "static"

@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db(DB_PATH)
    yield

app = FastAPI(title="Name Screening System", version="0.1.0", lifespan=lifespan)

class ScreenRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    dob: str | None = None
    country: str | None = None
    threshold: float = Field(default=80, ge=0, le=100)
    limit: int = Field(default=20, ge=1, le=100)
    source: str | None = None

@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse(STATIC / "index.html")

@app.get("/health")
def health():
    return {"ok": True, "stats": stats(DB_PATH)}

@app.get("/api/stats")
def api_stats():
    return stats(DB_PATH)

@app.post("/api/screen")
def api_screen(req: ScreenRequest):
    entities = get_entities(DB_PATH, req.source)
    request_id = str(uuid.uuid4())
    results = screen(req.name, entities, req.dob, req.country, req.threshold, req.limit)
    record_screening({"request_id": request_id, "query_name": req.name, "query_dob": req.dob, "query_country": req.country, "threshold": req.threshold, "candidate_count": len(entities), "matched_count": len(results)}, DB_PATH)
    return {"request_id": request_id, "query": req.model_dump(), "candidate_count": len(entities), "matches": results}

@app.post("/api/import/generic")
async def import_generic(file: UploadFile = File(...), source: str = Form("custom"), replace_source: bool = Form(False)):
    data = await file.read()
    rows = parse_generic_csv(data, source=source)
    if not rows:
        raise HTTPException(400, "No valid rows. Expected a primary_name/name/full_name column.")
    if replace_source:
        clear_source(source, DB_PATH)
    return {"source": source, "upserted": upsert_entities(rows, DB_PATH)}

@app.post("/api/import/ofac")
async def import_ofac(primary: UploadFile = File(...), aliases: UploadFile | None = File(None), replace_source: bool = Form(True)):
    p = await primary.read()
    a = await aliases.read() if aliases else None
    rows = parse_ofac_sdn(p, a)
    if not rows:
        raise HTTPException(400, "No OFAC rows parsed")
    if replace_source:
        clear_source("OFAC_SDN", DB_PATH)
    return {"source": "OFAC_SDN", "upserted": upsert_entities(rows, DB_PATH)}

@app.post("/api/batch")
async def batch_screen(file: UploadFile = File(...), threshold: float = Form(80), source: str | None = Form(None)):
    data = (await file.read()).decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(data))
    if not reader.fieldnames or not any(x in reader.fieldnames for x in ("name", "full_name", "primary_name")):
        raise HTTPException(400, "CSV must include name, full_name, or primary_name")
    entities = get_entities(DB_PATH, source)
    output = io.StringIO()
    fields = ["input_name", "input_dob", "input_country", "best_score", "matched_name", "primary_name", "source", "source_id", "match_kind", "dob_status", "country_status"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    for row in reader:
        name = row.get("name") or row.get("full_name") or row.get("primary_name") or ""
        dob = row.get("dob") or row.get("date_of_birth") or None
        country = row.get("country") or row.get("nationality") or None
        matches = screen(name, entities, dob, country, threshold, 1)
        m = matches[0] if matches else {}
        writer.writerow({"input_name": name, "input_dob": dob or "", "input_country": country or "", "best_score": m.get("score", ""), "matched_name": m.get("matched_name", ""), "primary_name": m.get("primary_name", ""), "source": m.get("source", ""), "source_id": m.get("source_id", ""), "match_kind": m.get("match_kind", ""), "dob_status": m.get("dob_status", ""), "country_status": m.get("country_status", "")})
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=screening_results.csv"})
