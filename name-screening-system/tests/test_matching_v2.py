import pytest

from app.matching import name_similarity, score_entity, screen

BASE = {
    "source": "TEST",
    "source_id": "A1",
    "entity_type": "individual",
    "primary_name": "DERIPASKA Oleg Vladimirovich",
    "aliases": ["Oleg Deripaska"],
    "weak_aliases": ["Falcon"],
    "native_names": ["ДЕРИПАСКА Олег Владимирович"],
    "dob": "1968-01-02",
    "dobs": ["1968-01-02", "1968"],
    "countries": ["Russian Federation"],
    "programs": ["TEST"],
}


def test_middle_name_omission_keeps_recall():
    score, meta = name_similarity("Oleg Deripaska", "Oleg Vladimirovich Deripaska")
    assert 80 <= score <= 92
    assert meta["subset_cap"] == 92.0


def test_corporate_suffix_subset_is_penalized():
    score, meta = name_similarity("John Smith", "John Smith Holdings Ltd")
    assert score <= 72
    assert meta["subset_cap"] == 72.0


def test_single_token_non_exact_is_capped():
    score, meta = name_similarity("Deripaska", "Oleg Deripaska")
    assert score <= 70
    assert meta["single_token_cap"] == 70.0


def test_weak_alias_penalty_and_cap():
    r = score_entity("Falcon", BASE)
    assert r.alias_strength == "weak"
    assert r.name_score <= 85
    assert r.score <= 85


def test_weak_alias_can_be_disabled():
    r = score_entity("Falcon", BASE, include_weak_aliases=False)
    assert not (r.matched_name == "Falcon" and r.alias_strength == "weak")


def test_multiple_dob_any_match():
    r = score_entity("Oleg Deripaska", BASE, "1968", "Russia")
    assert r.dob_status == "match"
    assert r.country_status == "match"
    assert r.score == 100


def test_blank_name_screen_returns_no_candidates():
    assert screen("   ", [BASE]) == []


def test_score_entity_blank_name_rejected():
    with pytest.raises(ValueError):
        score_entity("   ", BASE)
