from __future__ import annotations

import hashlib
import json
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .db import init_db, replace_source_atomic
from .importers import OFAC_SOURCE_URL, PARSER_VERSION, parse_ofac_sdn

OFAC_BASE = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports"
OFAC_FILES = {
    "primary": f"{OFAC_BASE}/SDN.CSV",
    "aliases": f"{OFAC_BASE}/ALT.CSV",
    "addresses": f"{OFAC_BASE}/ADD.CSV",
    "comments": f"{OFAC_BASE}/SDN_COMMENTS.CSV",
}


@dataclass
class DownloadReceipt:
    url: str
    path: str
    sha256: str
    bytes: int
    fetched_at: str


def _download(url: str, target: Path, timeout: int = 60) -> DownloadReceipt:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Jac-Name-Screening/2.0 (+source-integrity testing)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read()
    if not data:
        raise RuntimeError(f"Downloaded empty source: {url}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return DownloadReceipt(
        url=url,
        path=str(target),
        sha256=hashlib.sha256(data).hexdigest(),
        bytes=len(data),
        fetched_at=datetime.now(timezone.utc).isoformat(),
    )


def refresh_ofac(cache_dir: str | Path = "data/source_cache", db_path: str | Path | None = None) -> dict:
    cache = Path(cache_dir)
    paths = {
        "primary": cache / "OFAC_SDN.csv",
        "aliases": cache / "OFAC_ALT.csv",
        "addresses": cache / "OFAC_ADD.csv",
        "comments": cache / "OFAC_SDN_COMMENTS.csv",
    }
    receipts = {name: _download(url, paths[name]) for name, url in OFAC_FILES.items()}
    rows = parse_ofac_sdn(
        paths["primary"].read_bytes(),
        paths["aliases"].read_bytes(),
        paths["addresses"].read_bytes(),
        paths["comments"].read_bytes(),
    )
    if not rows:
        raise RuntimeError("OFAC parser produced zero rows; keeping previous database snapshot")

    init_db(db_path)
    combined_hash = hashlib.sha256(
        b"\n--JNS-PART--\n".join(paths[name].read_bytes() for name in ("primary", "aliases", "addresses", "comments"))
    ).hexdigest()
    replacement = replace_source_atomic(
        "OFAC_SDN",
        rows,
        db_path,
        snapshot={
            "sha256": combined_hash,
            "source_url": OFAC_SOURCE_URL,
            "parser_version": PARSER_VERSION,
            "metadata": {"files": {k: asdict(v) for k, v in receipts.items()}},
        },
    )
    manifest = {
        "source": "OFAC_SDN",
        "records": len(rows),
        "replacement": replacement,
        "combined_sha256": combined_hash,
        "files": {k: asdict(v) for k, v in receipts.items()},
    }
    (cache / "OFAC_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(refresh_ofac(), indent=2))
