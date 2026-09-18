from __future__ import annotations

import csv
import hashlib
import io
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Iterable

OFAC_SOURCE_URL = "https://sanctionslistservice.ofac.treas.gov/"
UK_SOURCE_URL = "https://www.gov.uk/government/publications/the-uk-sanctions-list"
CANADA_SOURCE_URL = "https://www.international.gc.ca/world-monde/international_relations-relations_internationales/sanctions/consolidated-consolide.aspx?lang=eng"
UN_SOURCE_URL = "https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list"
PARSER_VERSION = "2.0.0"


def _clean(value: str | None) -> str:
    if value is None:
        return ""
    v = str(value).strip().strip("\ufeff").strip("\x1a")
    return "" if v in {"-0-", "-0- ", "n/a", "N/A", "na", "NA"} else v


def split_multi(value: str | None) -> list[str]:
    if not value:
        return []
    return [x.strip() for x in re.split(r"\s*[;|]\s*", str(value)) if x.strip()]


def _uniq(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(v for v in values if _clean(v)))


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
        dobs = split_multi(row.get("dobs"))
        one_dob = _clean(row.get("dob") or row.get("date_of_birth"))
        if one_dob:
            dobs.insert(0, one_dob)
        out.append({
            "source": _clean(row.get("source")) or source,
            "source_id": _clean(row.get("source_id") or row.get("id")) or f"row-{idx}",
            "entity_type": _clean(row.get("entity_type") or row.get("type")) or "unknown",
            "primary_name": primary,
            "aliases": split_multi(row.get("aliases") or row.get("alias")),
            "weak_aliases": split_multi(row.get("weak_aliases") or row.get("weak_alias")),
            "native_names": split_multi(row.get("native_names") or row.get("native_name")),
            "dob": dobs[0] if dobs else None,
            "dobs": _uniq(dobs),
            "countries": split_multi(row.get("countries") or row.get("country") or row.get("nationality")),
            "programs": split_multi(row.get("programs") or row.get("program")),
            "identifiers": {},
            "source_url": _clean(row.get("source_url")) or source_url,
            "remarks": _clean(row.get("remarks") or row.get("notes")) or None,
            "raw": dict(row),
        })
    return out


def _extract_ofac_dobs(text: str) -> list[str]:
    if not text:
        return []
    # Capture common full-date and year-only DOB segments up to a semicolon/comma boundary.
    values = re.findall(
        r"\bDOB\s+(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{4})\b",
        text,
        flags=re.I,
    )
    return _uniq(values)




def _extract_ofac_weak_aliases(text: str) -> list[str]:
    if not text:
        return []
    values: list[str] = []
    # OFAC legacy CSV represents weak AKAs in the primary remarks field,
    # typically as quoted a.k.a. values. Keep this separate from ALT.CSV.
    for m in re.finditer(r"a\.k\.a\.\s+[\"\']([^\"\']+)[\"\']", text, flags=re.I):
        value = _clean(m.group(1))
        if value:
            values.append(value)
    return _uniq(values)

def _extract_ofac_countries(text: str) -> list[str]:
    if not text:
        return []
    values: list[str] = []
    for label in ("citizen", "nationality"):
        for m in re.finditer(rf"\b{label}\s+([^;]+)", text, flags=re.I):
            candidate = m.group(1).strip()
            candidate = re.split(r",\s*(?:Gender|Passport|National ID|Tax ID|DOB|POB)\b", candidate, maxsplit=1, flags=re.I)[0]
            if candidate:
                values.append(candidate)
    return _uniq(values)


def parse_ofac_sdn(
    primary_csv: bytes | str,
    alt_csv: bytes | str | None = None,
    add_csv: bytes | str | None = None,
    comments_csv: bytes | str | None = None,
) -> list[dict]:
    """Parse OFAC legacy CSV files and join related rows by ent_num/UID.

    The parser accepts the legacy primary + ALT + ADD + COMMENTS family.  It is
    intentionally tolerant because OFAC has historically published sentinel values
    and variable trailing columns.
    """
    ptext = primary_csv.decode("utf-8-sig", errors="replace") if isinstance(primary_csv, bytes) else primary_csv
    atext = alt_csv.decode("utf-8-sig", errors="replace") if isinstance(alt_csv, bytes) else alt_csv
    dtext = add_csv.decode("utf-8-sig", errors="replace") if isinstance(add_csv, bytes) else add_csv
    ctext = comments_csv.decode("utf-8-sig", errors="replace") if isinstance(comments_csv, bytes) else comments_csv

    strong_aliases: dict[str, list[str]] = defaultdict(list)
    weak_aliases: dict[str, list[str]] = defaultdict(list)
    native_names: dict[str, list[str]] = defaultdict(list)
    address_countries: dict[str, list[str]] = defaultdict(list)
    extra_comments: dict[str, list[str]] = defaultdict(list)

    if atext:
        for row in csv.reader(io.StringIO(atext)):
            if len(row) < 4:
                continue
            fields = [_clean(x) for x in row]
            ent_num, _alt_num, alt_type, alt_name = fields[:4]
            alt_remarks = fields[4] if len(fields) > 4 else ""
            if not ent_num or not alt_name:
                continue
            descriptor = f"{alt_type} {alt_remarks}".lower()
            if "weak" in descriptor or "low quality" in descriptor:
                weak_aliases[ent_num].append(alt_name)
            else:
                strong_aliases[ent_num].append(alt_name)
            if re.search(r"cyrillic|arabic|farsi|chinese|original script|non-latin", descriptor, re.I):
                native_names[ent_num].append(alt_name)

    if dtext:
        for row in csv.reader(io.StringIO(dtext)):
            if len(row) < 2:
                continue
            fields = [_clean(x) for x in row]
            ent_num = fields[0]
            # Legacy ADD rows are commonly ent_num, add_num, address, city/state, country, remarks.
            country = fields[4] if len(fields) > 4 else ""
            if ent_num and country:
                address_countries[ent_num].append(country)

    if ctext:
        for row in csv.reader(io.StringIO(ctext)):
            if len(row) < 2:
                continue
            fields = [_clean(x) for x in row]
            ent_num = fields[0]
            comment = next((x for x in reversed(fields[1:]) if x), "")
            if ent_num and comment:
                extra_comments[ent_num].append(comment)

    out = []
    for row in csv.reader(io.StringIO(ptext)):
        if len(row) < 4:
            continue
        row = [_clean(x) for x in row]
        ent_num, name, entity_type, program = row[:4]
        remarks = row[11] if len(row) > 11 else ""
        if not ent_num or not name:
            continue
        combined_remarks = "; ".join(_uniq([remarks, *extra_comments.get(ent_num, [])]))
        dobs = _extract_ofac_dobs(combined_remarks)
        countries = _uniq([
            *_extract_ofac_countries(combined_remarks),
            *address_countries.get(ent_num, []),
        ])
        remark_weak_aliases = _extract_ofac_weak_aliases(combined_remarks)
        out.append({
            "source": "OFAC_SDN",
            "source_id": ent_num,
            "entity_type": entity_type.lower() if entity_type else "entity",
            "primary_name": name,
            "aliases": _uniq(strong_aliases.get(ent_num, [])),
            "weak_aliases": _uniq([*weak_aliases.get(ent_num, []), *remark_weak_aliases]),
            "native_names": _uniq(native_names.get(ent_num, [])),
            "dob": dobs[0] if dobs else None,
            "dobs": dobs,
            "countries": countries,
            "programs": [program] if program else [],
            "identifiers": {"ofac_uid": ent_num},
            "source_url": OFAC_SOURCE_URL,
            "remarks": combined_remarks or None,
            "raw": {"row": row},
        })
    return out


def _row_ci(row: dict[str, str]) -> dict[str, str]:
    return {re.sub(r"\s+", " ", str(k).strip()).lower(): _clean(v) for k, v in row.items()}


def _uk_name(r: dict[str, str]) -> str:
    parts = [r.get(f"name {i}", "") for i in range(1, 7)]
    return " ".join(x for x in parts if x).strip()


def parse_uk_sanctions_csv(content: bytes | str) -> list[dict]:
    text = content.decode("utf-8-sig", errors="replace") if isinstance(content, bytes) else content
    reader = csv.DictReader(io.StringIO(text))
    grouped: dict[str, dict] = {}
    for raw in reader:
        r = _row_ci(raw)
        uid = r.get("unique id") or r.get("uk sanctions list ref")
        if not uid:
            continue
        obj = grouped.setdefault(uid, {
            "source": "UK_SANCTIONS",
            "source_id": uid,
            "entity_type": (r.get("individual, entity, ship") or "unknown").lower(),
            "primary_name": "",
            "aliases": [],
            "weak_aliases": [],
            "native_names": [],
            "dobs": [],
            "countries": [],
            "programs": [],
            "identifiers": {"uk_unique_id": uid},
            "source_url": UK_SOURCE_URL,
            "remarks": None,
            "raw": [],
        })
        name = _uk_name(r)
        name_type = (r.get("name type") or "").lower()
        alias_strength = (r.get("alias strength") or "").lower()
        if name:
            if name_type == "primary name" or (not obj["primary_name"] and not name_type):
                obj["primary_name"] = name
            elif name_type == "alias" and ("low" in alias_strength or "weak" in alias_strength):
                obj["weak_aliases"].append(name)
            else:
                obj["aliases"].append(name)
        native = r.get("name non-latin script") or ""
        if native:
            obj["native_names"].append(native)
        if r.get("d.o.b"):
            obj["dobs"].extend(split_multi(r["d.o.b"].replace(",", ";")))
        if r.get("nationality(/ies)"):
            obj["countries"].extend(split_multi(r["nationality(/ies)"].replace(",", ";")))
        if r.get("regime name"):
            obj["programs"].append(r["regime name"])
        if r.get("un reference number"):
            obj["identifiers"]["un_reference"] = r["un reference number"]
        if r.get("ofsi group id"):
            obj["identifiers"]["ofsi_group_id"] = r["ofsi group id"]
        remarks = "; ".join(x for x in [r.get("other information"), r.get("uk statement of reasons")] if x)
        if remarks and not obj["remarks"]:
            obj["remarks"] = remarks
        obj["raw"].append(raw)

    out = []
    for obj in grouped.values():
        obj["aliases"] = _uniq(obj["aliases"])
        obj["weak_aliases"] = _uniq(obj["weak_aliases"])
        obj["native_names"] = _uniq(obj["native_names"])
        obj["dobs"] = _uniq(obj["dobs"])
        obj["dob"] = obj["dobs"][0] if obj["dobs"] else None
        obj["countries"] = _uniq(obj["countries"])
        obj["programs"] = _uniq(obj["programs"])
        if obj["primary_name"]:
            out.append(obj)
    return out


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_texts(el: ET.Element, local_name: str) -> list[str]:
    return [_clean(x.text) for x in el.iter() if _local(x.tag).upper() == local_name.upper() and _clean(x.text)]


def _direct_text(el: ET.Element, local_name: str) -> str:
    for x in list(el):
        if _local(x.tag).upper() == local_name.upper():
            return _clean(x.text)
    return ""


def parse_un_xml(content: bytes | str) -> list[dict]:
    data = content.encode("utf-8") if isinstance(content, str) else content
    root = ET.fromstring(data)
    out: list[dict] = []

    for el in root.iter():
        kind = _local(el.tag).upper()
        if kind not in {"INDIVIDUAL", "ENTITY"}:
            continue
        source_id = _direct_text(el, "REFERENCE_NUMBER") or _direct_text(el, "DATAID")
        if kind == "INDIVIDUAL":
            primary = " ".join(
                x for x in [
                    _direct_text(el, "FIRST_NAME"), _direct_text(el, "SECOND_NAME"),
                    _direct_text(el, "THIRD_NAME"), _direct_text(el, "FOURTH_NAME")
                ] if x
            )
            aliases, weak_aliases = [], []
            for alias_el in [x for x in el.iter() if _local(x.tag).upper() == "INDIVIDUAL_ALIAS"]:
                name = _direct_text(alias_el, "ALIAS_NAME")
                quality = _direct_text(alias_el, "QUALITY").lower()
                if name:
                    (weak_aliases if "low" in quality else aliases).append(name)
            dobs = []
            for dob_el in [x for x in el.iter() if _local(x.tag).upper() == "INDIVIDUAL_DATE_OF_BIRTH"]:
                date = _direct_text(dob_el, "DATE")
                year = _direct_text(dob_el, "YEAR")
                if date:
                    dobs.append(date)
                elif year:
                    dobs.append(year)
            countries = []
            for nat_el in [x for x in el.iter() if _local(x.tag).upper() == "NATIONALITY"]:
                countries.extend(_child_texts(nat_el, "VALUE"))
            native = _child_texts(el, "NAME_ORIGINAL_SCRIPT")
            entity_type = "individual"
        else:
            primary = _direct_text(el, "FIRST_NAME") or _direct_text(el, "NAME")
            aliases, weak_aliases = [], []
            for alias_el in [x for x in el.iter() if _local(x.tag).upper() == "ENTITY_ALIAS"]:
                name = _direct_text(alias_el, "ALIAS_NAME")
                if name:
                    aliases.append(name)
            dobs, countries = [], []
            native = _child_texts(el, "NAME_ORIGINAL_SCRIPT")
            entity_type = "entity"
        if not primary:
            continue
        listed_on = _direct_text(el, "LISTED_ON")
        comments = _direct_text(el, "COMMENTS1")
        out.append({
            "source": "UN_CONSOLIDATED",
            "source_id": source_id or hashlib.sha256(primary.encode()).hexdigest()[:16],
            "entity_type": entity_type,
            "primary_name": primary,
            "aliases": _uniq(aliases),
            "weak_aliases": _uniq(weak_aliases),
            "native_names": _uniq(native),
            "dob": dobs[0] if dobs else None,
            "dobs": _uniq(dobs),
            "countries": _uniq(countries),
            "programs": _uniq([
                value
                for list_type in [x for x in el.iter() if _local(x.tag).upper() == "UN_LIST_TYPE"]
                for value in _child_texts(list_type, "VALUE")
            ]),
            "identifiers": {"un_reference": source_id} if source_id else {},
            "source_url": UN_SOURCE_URL,
            "remarks": "; ".join(x for x in [f"Listed on {listed_on}" if listed_on else "", comments] if x) or None,
            "raw": {"reference": source_id},
        })
    return out


def _norm_tag(tag: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _local(tag).lower())


def _flatten_leaf_texts(el: ET.Element) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for x in el.iter():
        if len(list(x)) == 0 and _clean(x.text):
            result[_norm_tag(x.tag)].append(_clean(x.text))
    return result


def _first(mapping: dict[str, list[str]], *keys: str) -> str:
    for key in keys:
        vals = mapping.get(_norm_tag(key), [])
        if vals:
            return vals[0]
    return ""


def parse_canada_xml(content: bytes | str) -> list[dict]:
    """Tolerant adapter for Canada's consolidated autonomous sanctions XML.

    The official presentation fields include regulation, entity/ship, last name,
    given names, aliases, DOB/build date, schedule, item and listing date.  This
    parser is deliberately tag-tolerant so minor XML wrapper changes do not silently
    drop the entire source.
    """
    data = content.encode("utf-8") if isinstance(content, str) else content
    root = ET.fromstring(data)
    out: list[dict] = []
    seen_nodes: set[int] = set()

    for el in root.iter():
        direct_keys = {_norm_tag(c.tag) for c in list(el)}
        marker_keys = {"lastname", "givennames", "aliases", "entity", "entityorship", "dateofbirth", "dateofbirthorshipbuilddate"}
        if len(direct_keys & marker_keys) < 1:
            continue
        if id(el) in seen_nodes:
            continue
        flat = _flatten_leaf_texts(el)
        last = _first(flat, "Last Name", "LastName")
        given = _first(flat, "Given Names", "GivenNames", "GivenName")
        entity_name = _first(flat, "Entity or Ship", "Entity", "EntityOrShip")
        primary = " ".join(x for x in [given, last] if x).strip() or entity_name
        if not primary:
            continue
        regulation = _first(flat, "Regulation")
        schedule = _first(flat, "Schedule")
        item = _first(flat, "Item Number", "ItemNumber")
        source_id = "|".join(x for x in [regulation, schedule, item, primary] if x)
        aliases_raw = _first(flat, "Aliases", "Alias")
        dob = _first(flat, "Date of Birth or Ship build date", "DateOfBirth", "DOB")
        listing_date = _first(flat, "Date of Listing", "DateOfListing")
        title = _first(flat, "Title or Ship type", "Title", "ShipType")
        out.append({
            "source": "CANADA_CONSOLIDATED",
            "source_id": source_id or hashlib.sha256(primary.encode()).hexdigest()[:16],
            "entity_type": "entity" if entity_name else "individual",
            "primary_name": primary,
            "aliases": _uniq(split_multi(aliases_raw.replace(",", ";")) if aliases_raw else []),
            "weak_aliases": [],
            "native_names": [],
            "dob": dob or None,
            "dobs": [dob] if dob else [],
            "countries": [],
            "programs": [regulation] if regulation else [],
            "identifiers": {"schedule": schedule, "item": item},
            "source_url": CANADA_SOURCE_URL,
            "remarks": "; ".join(x for x in [title, f"Listed {listing_date}" if listing_date else ""] if x) or None,
            "raw": {k: v for k, v in flat.items()},
        })
        seen_nodes.add(id(el))
    # Avoid accidental duplicates created by nested wrappers.
    dedup: dict[tuple[str, str], dict] = {}
    for row in out:
        dedup[(row["source_id"], row["primary_name"])] = row
    return list(dedup.values())


def read_file(path: str | Path) -> bytes:
    return Path(path).read_bytes()
