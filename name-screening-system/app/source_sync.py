from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .db import init_db, upsert_entities
from .importers import parse_ofac_sdn

OFAC_BASE = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports"
OFAC_FILES = {"primary": f"{OFAC_BASE}/SDN.CSV", "aliases": f"{OFAC_BASE}/ALT.CSV"}

@dataclass
class DownloadReceipt:
    url: str
    path: str
    sha256: str
    bytes: int
    fetched_at: str


def _download(url: str, target: Path, timeout: int = 60) -> DownloadReceipt:
    req = urllib.request.Request(url, headers={"User-Agent": "NameScreeningSystem/0.1 (+local compliance testing)"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return DownloadReceipt(url=url, path=str(target), sha256=hashlib.sha256(data).hexdigest(), bytes=len(data), fetched_at=datetime.now(timezone.utc).isoformat())


def refresh_ofac(cache_dir: str | Path = "data/source_cache", db_path: str | Path | None = None) -> dict:
    cache = Path(cache_dir)
    primary = cache / "OFAC_SDN.csv"
    aliases = cache / "OFAC_ALT.csv"
    receipts = [_download(OFAC_FILES["primary"], primary), _download(OFAC_FILES["aliases"], aliases)]
    rows = parse_ofac_sdn(primary.read_bytes(), aliases.read_bytes())
    init_db(db_path)
    count = upsert_entities(rows, db_path)
    manifest = {"source": "OFAC_SDN", "records_upserted": count, "files": [r.__dict__ for r in receipts]}
    (cache / "OFAC_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest

if __name__ == "__main__":
    print(json.dumps(refresh_ofac(), indent=2))
