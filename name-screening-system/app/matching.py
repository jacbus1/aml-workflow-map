from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Iterable

from rapidfuzz import fuzz
from unidecode import unidecode

SPACE_RE = re.compile(r"\s+")
NON_ALNUM_RE = re.compile(r"[^A-Z0-9 ]+")
CORPORATE_SUFFIXES = {
    "LTD", "LIMITED", "LLC", "INC", "INCORPORATED", "PLC", "CORP", "CORPORATION",
    "HOLDING", "HOLDINGS", "GROUP", "COMPANY", "CO", "BANK", "FOUNDATION", "TRUST",
    "SA", "SAS", "GMBH", "AG", "BV", "NV", "LP", "LLP",
}
COUNTRY_EQUIVALENTS = {
    "RUSSIAN FEDERATION": "RUSSIA",
    "RUSSIA FEDERATION": "RUSSIA",
    "UNITED STATES OF AMERICA": "UNITED STATES",
    "USA": "UNITED STATES",
    "U S A": "UNITED STATES",
    "UK": "UNITED KINGDOM",
    "U K": "UNITED KINGDOM",
}


def normalize_name(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = unidecode(value).upper()
    value = value.replace("’", "'")
    value = NON_ALNUM_RE.sub(" ", value)
    return SPACE_RE.sub(" ", value).strip()


def normalize_country(value: str | None) -> str:
    n = normalize_name(value)
    return COUNTRY_EQUIVALENTS.get(n, n)


def normalize_dob(value: str | None) -> str | None:
    if not value:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Prefer unambiguous and common sanctions-list formats.
    for fmt in (
        "%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%d-%m-%Y",
    ):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    if re.fullmatch(r"\d{4}", s):
        return s
    # Preserve partial/unknown formats as uppercase evidence rather than discarding them.
    return s.upper()


def _tokens(s: str) -> list[str]:
    return [x for x in normalize_name(s).split(" ") if x]


def _reversed_name(s: str) -> str:
    t = _tokens(s)
    return " ".join(reversed(t)) if len(t) > 1 else normalize_name(s)


def _corporate_subset_penalty(a_tokens: list[str], b_tokens: list[str]) -> float | None:
    a_set, b_set = set(a_tokens), set(b_tokens)
    if not a_set or not b_set or a_set == b_set:
        return None
    if not (a_set <= b_set or b_set <= a_set):
        return None
    extras = (b_set - a_set) | (a_set - b_set)
    if extras & CORPORATE_SUFFIXES:
        return 72.0
    # Omitting a middle/patronymic name is common, so keep recall while avoiding 100.
    return 92.0 if min(len(a_tokens), len(b_tokens)) >= 2 else 70.0


def name_similarity(a: str, b: str) -> tuple[float, dict]:
    a_n, b_n = normalize_name(a), normalize_name(b)
    if not a_n or not b_n:
        metrics = {
            "ratio": 0.0, "token_sort": 0.0, "token_set": 0.0,
            "wratio": 0.0, "reverse": 0.0, "exact": False,
            "subset_cap": None, "single_token_cap": None,
        }
        return 0.0, metrics

    a_tokens, b_tokens = _tokens(a_n), _tokens(b_n)
    exact = a_n == b_n
    metrics = {
        "ratio": float(fuzz.ratio(a_n, b_n)),
        "token_sort": float(fuzz.token_sort_ratio(a_n, b_n)),
        "token_set": float(fuzz.token_set_ratio(a_n, b_n)),
        "wratio": float(fuzz.WRatio(a_n, b_n)),
        "reverse": float(fuzz.ratio(a_n, _reversed_name(b_n))),
        "exact": exact,
    }
    score = 100.0 if exact else max(
        metrics["ratio"], metrics["token_sort"], metrics["wratio"], metrics["reverse"]
    )

    subset_cap = _corporate_subset_penalty(a_tokens, b_tokens)
    if subset_cap is not None:
        score = min(score, subset_cap)
    metrics["subset_cap"] = subset_cap

    single_token_cap = None
    if min(len(a_tokens), len(b_tokens)) == 1 and not exact:
        single_token_cap = 70.0
        score = min(score, single_token_cap)
    metrics["single_token_cap"] = single_token_cap

    return round(float(score), 2), {
        k: round(v, 2) if isinstance(v, float) else v for k, v in metrics.items()
    }


def _entity_dobs(entity: dict) -> list[str]:
    values = []
    for d in entity.get("dobs", []) or []:
        if d:
            values.append(str(d))
    if entity.get("dob"):
        values.append(str(entity["dob"]))
    # Stable de-duplication.
    return list(dict.fromkeys(values))


def _dob_compare(query_dob: str | None, entity_dobs: list[str]) -> tuple[str, int, str | None]:
    q = normalize_dob(query_dob)
    edobs = [(raw, normalize_dob(raw)) for raw in entity_dobs if normalize_dob(raw)]
    if q and edobs:
        for raw, e in edobs:
            if q == e or (len(q) == 4 and str(e).startswith(q)) or (len(str(e)) == 4 and q.startswith(str(e))):
                return "match", 8, raw
        return "mismatch", -8, None
    if q or edobs:
        return "missing_on_one_side", 0, None
    return "not_provided", 0, None


@dataclass
class MatchResult:
    source: str
    source_id: str
    entity_type: str
    primary_name: str
    matched_name: str
    match_kind: str
    alias_strength: str | None
    score: float
    name_score: float
    risk_band: str
    dob_status: str
    matched_dob: str | None
    country_status: str
    dobs: list[str]
    countries: list[str]
    aliases: list[str]
    weak_aliases: list[str]
    native_names: list[str]
    programs: list[str]
    source_url: str | None
    remarks: str | None
    score_breakdown: dict

    def dict(self) -> dict:
        return asdict(self)


def score_entity(
    query_name: str,
    entity: dict,
    query_dob: str | None = None,
    query_country: str | None = None,
    include_weak_aliases: bool = True,
) -> MatchResult:
    qnorm = normalize_name(query_name)
    if not qnorm:
        raise ValueError("query_name must contain non-whitespace characters")

    names: list[tuple[str, str, str | None]] = [(entity.get("primary_name", ""), "primary", None)]
    names.extend((a, "alias", "strong") for a in entity.get("aliases", []) or [] if a)
    names.extend((a, "native_name", "strong") for a in entity.get("native_names", []) or [] if a)
    if include_weak_aliases:
        names.extend((a, "alias", "weak") for a in entity.get("weak_aliases", []) or [] if a)

    best_name = ""
    best_kind = "primary"
    best_strength: str | None = None
    best_score = -1.0
    best_metrics: dict = {}
    best_exact = False
    best_raw_score = -1.0

    for candidate, kind, strength in names:
        raw_score, metrics = name_similarity(query_name, candidate)
        adjusted = raw_score
        if strength == "weak":
            adjusted = max(0.0, adjusted - 15.0)
            adjusted = min(adjusted, 85.0)
            metrics = {**metrics, "weak_alias_penalty": -15.0, "weak_alias_cap": 85.0}
        else:
            metrics = {**metrics, "weak_alias_penalty": 0.0, "weak_alias_cap": None}
        exact = normalize_name(candidate) == qnorm and bool(qnorm)
        if adjusted > best_score or (adjusted == best_score and exact and not best_exact):
            best_name, best_kind, best_strength = candidate, kind, strength
            best_score, best_raw_score, best_metrics = adjusted, raw_score, metrics
            best_exact = exact

    dobs = _entity_dobs(entity)
    dob_status, dob_adjustment, matched_dob = _dob_compare(query_dob, dobs)

    qc = normalize_country(query_country)
    ecs = [normalize_country(x) for x in entity.get("countries", []) or [] if x]
    if qc and ecs:
        if qc in ecs:
            country_status, country_adjustment = "match", 4
        else:
            country_status, country_adjustment = "mismatch", -2
    elif qc or ecs:
        country_status, country_adjustment = "missing_on_one_side", 0
    else:
        country_status, country_adjustment = "not_provided", 0

    final = max(0.0, min(100.0, best_score + dob_adjustment + country_adjustment))
    if final >= 90:
        risk_band = "HIGH_CANDIDATE"
    elif final >= 80:
        risk_band = "REVIEW_CANDIDATE"
    else:
        risk_band = "LOW_CANDIDATE"

    return MatchResult(
        source=entity.get("source", "custom"),
        source_id=str(entity.get("source_id", "")),
        entity_type=entity.get("entity_type", "unknown"),
        primary_name=entity.get("primary_name", ""),
        matched_name=best_name,
        match_kind=best_kind,
        alias_strength=best_strength,
        score=round(final, 2),
        name_score=round(best_score, 2),
        risk_band=risk_band,
        dob_status=dob_status,
        matched_dob=matched_dob,
        country_status=country_status,
        dobs=dobs,
        countries=entity.get("countries", []) or [],
        aliases=entity.get("aliases", []) or [],
        weak_aliases=entity.get("weak_aliases", []) or [],
        native_names=entity.get("native_names", []) or [],
        programs=entity.get("programs", []) or [],
        source_url=entity.get("source_url"),
        remarks=entity.get("remarks"),
        score_breakdown={
            "name": best_metrics,
            "raw_name_score": round(best_raw_score, 2),
            "adjusted_name_score": round(best_score, 2),
            "dob_adjustment": dob_adjustment,
            "country_adjustment": country_adjustment,
        },
    )


def screen(
    query_name: str,
    entities: Iterable[dict],
    query_dob: str | None = None,
    query_country: str | None = None,
    threshold: float = 80,
    limit: int = 20,
    include_weak_aliases: bool = True,
) -> list[dict]:
    if not normalize_name(query_name):
        return []
    results = [
        score_entity(query_name, e, query_dob, query_country, include_weak_aliases)
        for e in entities
    ]
    results = [r for r in results if r.score >= threshold]
    results.sort(key=lambda r: (-r.score, -r.name_score, r.primary_name))
    return [r.dict() for r in results[:limit]]
