from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Iterable

from rapidfuzz import fuzz
from unidecode import unidecode

SPACE_RE = re.compile(r"\s+")
NON_ALNUM_RE = re.compile(r"[^A-Z0-9 ]+")


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = unidecode(value).upper()
    value = value.replace("’", "'")
    value = NON_ALNUM_RE.sub(" ", value)
    return SPACE_RE.sub(" ", value).strip()


def normalize_country(value: str | None) -> str:
    return normalize_name(value)


def normalize_dob(value: str | None) -> str | None:
    if not value:
        return None
    s = value.strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    if re.fullmatch(r"\d{4}", s):
        return s
    return s.upper()


def _tokens(s: str) -> list[str]:
    return [x for x in normalize_name(s).split(" ") if x]


def _reversed_name(s: str) -> str:
    t = _tokens(s)
    return " ".join(reversed(t)) if len(t) > 1 else normalize_name(s)


def name_similarity(a: str, b: str) -> tuple[float, dict]:
    a_n, b_n = normalize_name(a), normalize_name(b)
    if not a_n or not b_n:
        return 0.0, {"ratio": 0, "token_sort": 0, "token_set": 0, "wratio": 0, "reverse": 0}
    metrics = {
        "ratio": fuzz.ratio(a_n, b_n),
        "token_sort": fuzz.token_sort_ratio(a_n, b_n),
        "token_set": fuzz.token_set_ratio(a_n, b_n),
        "wratio": fuzz.WRatio(a_n, b_n),
        "reverse": fuzz.ratio(a_n, _reversed_name(b_n)),
    }
    score = max(metrics.values())
    return round(float(score), 2), {k: round(float(v), 2) for k, v in metrics.items()}


@dataclass
class MatchResult:
    source: str
    source_id: str
    entity_type: str
    primary_name: str
    matched_name: str
    match_kind: str
    score: float
    name_score: float
    dob_status: str
    country_status: str
    dob: str | None
    countries: list[str]
    aliases: list[str]
    programs: list[str]
    source_url: str | None
    remarks: str | None
    score_breakdown: dict

    def dict(self) -> dict:
        return asdict(self)


def score_entity(query_name: str, entity: dict, query_dob: str | None = None, query_country: str | None = None) -> MatchResult:
    names = [(entity.get("primary_name", ""), "primary")]
    names.extend((a, "alias") for a in entity.get("aliases", []) if a)
    best_name = ""
    best_kind = "primary"
    best_score = -1.0
    best_metrics = {}
    qnorm = normalize_name(query_name)
    best_exact = False
    for candidate, kind in names:
        s, metrics = name_similarity(query_name, candidate)
        exact = normalize_name(candidate) == qnorm and bool(qnorm)
        if s > best_score or (s == best_score and exact and not best_exact):
            best_name, best_kind, best_score, best_metrics = candidate, kind, s, metrics
            best_exact = exact

    final = best_score
    qdob, edob = normalize_dob(query_dob), normalize_dob(entity.get("dob"))
    if qdob and edob:
        if qdob == edob or (len(qdob) == 4 and edob.startswith(qdob)) or (len(edob) == 4 and qdob.startswith(edob)):
            dob_status = "match"
            final += 8
        else:
            dob_status = "mismatch"
            final -= 8
    elif qdob or edob:
        dob_status = "missing_on_one_side"
    else:
        dob_status = "not_provided"

    qc = normalize_country(query_country)
    ecs = [normalize_country(x) for x in entity.get("countries", []) if x]
    if qc and ecs:
        if qc in ecs:
            country_status = "match"
            final += 4
        else:
            country_status = "mismatch"
            final -= 2
    elif qc or ecs:
        country_status = "missing_on_one_side"
    else:
        country_status = "not_provided"

    final = max(0.0, min(100.0, final))
    return MatchResult(
        source=entity.get("source", "custom"), source_id=str(entity.get("source_id", "")),
        entity_type=entity.get("entity_type", "unknown"), primary_name=entity.get("primary_name", ""),
        matched_name=best_name, match_kind=best_kind, score=round(final, 2), name_score=round(best_score, 2),
        dob_status=dob_status, country_status=country_status, dob=entity.get("dob"), countries=entity.get("countries", []),
        aliases=entity.get("aliases", []), programs=entity.get("programs", []), source_url=entity.get("source_url"),
        remarks=entity.get("remarks"), score_breakdown={"name": best_metrics,
        "dob_adjustment": 8 if dob_status == "match" else -8 if dob_status == "mismatch" else 0,
        "country_adjustment": 4 if country_status == "match" else -2 if country_status == "mismatch" else 0},
    )


def screen(query_name: str, entities: Iterable[dict], query_dob: str | None = None, query_country: str | None = None, threshold: float = 80, limit: int = 20) -> list[dict]:
    results = [score_entity(query_name, e, query_dob, query_country) for e in entities]
    results = [r for r in results if r.score >= threshold]
    results.sort(key=lambda r: (-r.score, -r.name_score, r.primary_name))
    return [r.dict() for r in results[:limit]]
