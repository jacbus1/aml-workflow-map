from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from pathlib import Path

OFAC_SOURCE_URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV"


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    v = value.strip().strip('\ufeff').strip('\x1a')
    return "" if v in {"-0-", "-0- "} else v


def split_multi(value: str | None) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in re.split(r"\s*[;|]\s*", value) if x.strip()]


def parse_generic_csv(content: bytes | str, source: str = "custom", source_url: str | None = None) -> list[dict]:
    text = content.decode("utf-8-sig", errors="replace") if isinstance(content, bytes) else content
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return []
    out = []
    for idx, row in enumerate(reader, start=1):
        primary = _clean(row.get("primary_name") or row.get("name") or row.get("full_name"))
        if not primary:
            continue
        out.append({
            "source": _clean(row.get("source")) or source,
            "source_id": _clean(row.get("source_id") or row.get("id")) or f"row-{idx}",
            "entity_type": _clean(row.get("entity_type") or row.get("type")) or "unknown",
            "primary_name": primary,
            "aliases": split_multi(row.get("aliases") or row.get("alias")),
            "dob": _clean(row.get("dob") or row.get("date_of_birth")) or None,
            "countries": split_multi(row.get("countries") or row.get("country") or row.get("nationality")),
            "programs": split_multi(row.get("programs") or row.get("program")),
            "source_url": _clean(row.get("source_url")) or source_url,
            "remarks": _clean(row.get("remarks") or row.get("notes")) or None,
            "raw": dict(row),
        })
    return out


def parse_ofac_sdn(primary_csv: bytes | str, alt_csv: bytes | str | None = None) -> list[dict]:
    ptext = primary_csv.decode("utf-8-sig", errors="replace") if isinstance(primary_csv, bytes) else primary_csv
    atext = alt_csv.decode("utf-8-sig", errors="replace") if isinstance(alt_csv, bytes) else alt_csv
    aliases: dict[str, list[str]] = defaultdict(list)
    if atext:
        for row in csv.reader(io.StringIO(atext)):
            if len(row) < 4:
                continue
            ent_num, _alt_num, _alt_type, alt_name = [_clean(x) for x in row[:4]]
            if ent_num and alt_name:
                aliases[ent_num].append(alt_name)

    out = []
    for row in csv.reader(io.StringIO(ptext)):
        if len(row) < 4:
            continue
        row = [_clean(x) for x in row]
        ent_num, name, entity_type, program = row[:4]
        remarks = row[11] if len(row) > 11 else ""
        if not ent_num or not name:
            continue
        dob_match = re.search(r"\bDOB\s+([0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4}|[0-9]{4})\b", remarks, re.I)
        country_matches = re.findall(r"\bcitizen\s+([^;]+)", remarks, re.I)
        out.append({
            "source": "OFAC_SDN", "source_id": ent_num,
            "entity_type": entity_type.lower() if entity_type else "entity", "primary_name": name,
            "aliases": sorted(set(aliases.get(ent_num, []))), "dob": dob_match.group(1) if dob_match else None,
            "countries": sorted(set(x.strip() for x in country_matches if x.strip())),
            "programs": [program] if program else [], "source_url": OFAC_SOURCE_URL,
            "remarks": remarks or None, "raw": {"row": row},
        })
    return out


def read_file(path: str | Path) -> bytes:
    return Path(path).read_bytes()
