from app.matching import normalize_name, name_similarity, score_entity, screen

ENTITY = {
    "source":"TEST","source_id":"1","entity_type":"individual",
    "primary_name":"DERIPASKA, Oleg Vladimirovich",
    "aliases":["Oleg Deripaska"],"dob":"02 Jan 1968","countries":["Russia"],
    "programs":["RUSSIA-EO14024"],"source_url":"https://example.invalid","remarks":None
}

def test_normalization_handles_diacritics_punctuation_and_order():
    assert normalize_name("José-Luís O’Neill") == "JOSE LUIS O NEILL"
    score, _ = name_similarity("Oleg Deripaska", "Deripaska Oleg")
    assert score >= 95

def test_alias_can_be_best_match():
    r = score_entity("Oleg Deripaska", ENTITY, "1968-01-02", "Russia")
    assert r.match_kind == "alias"
    assert r.score == 100
    assert r.dob_status == "match"
    assert r.country_status == "match"

def test_dob_mismatch_penalizes_but_does_not_hard_filter():
    r = score_entity("Oleg Deripaska", ENTITY, "1970-01-01", "Russia")
    assert r.name_score == 100
    assert r.dob_status == "mismatch"
    assert r.score >= 90

def test_transliteration():
    e = {**ENTITY, "primary_name":"張偉", "aliases":[]}
    r = score_entity("Zhang Wei", e)
    # Unidecode transliterates 張偉 close enough for candidate generation.
    assert r.name_score >= 70

def test_threshold_filters():
    results = screen("Completely Different Person", [ENTITY], threshold=80)
    assert results == []
