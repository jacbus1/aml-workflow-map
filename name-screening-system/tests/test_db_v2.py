import pytest

from app.db import get_entities, init_db, latest_snapshot, replace_source_atomic, upsert_entities


def row(source_id, name):
    return {"source":"X","source_id":source_id,"entity_type":"individual","primary_name":name,"aliases":[]}


def test_atomic_replace_removes_stale_and_writes_snapshot(tmp_path):
    db = tmp_path / "x.db"
    init_db(db)
    upsert_entities([row("1","One"), row("2","Two")], db)
    result = replace_source_atomic("X", [row("2","Two Updated"), row("3","Three")], db, snapshot={"sha256":"abc","parser_version":"2"})
    names = sorted(x["primary_name"] for x in get_entities(db, "X"))
    assert names == ["Three", "Two Updated"]
    assert result["previous"] == 2 and result["inserted"] == 2
    assert result["added"] == 1 and result["removed"] == 1
    snap = latest_snapshot("X", db)
    assert snap["sha256"] == "abc" and snap["record_count"] == 2


def test_empty_replace_is_rejected_without_destroying_old_data(tmp_path):
    db = tmp_path / "x.db"
    init_db(db)
    upsert_entities([row("1","One")], db)
    with pytest.raises(ValueError):
        replace_source_atomic("X", [], db)
    assert [x["primary_name"] for x in get_entities(db,"X")] == ["One"]


def test_rows_with_blank_primary_do_not_wipe_source(tmp_path):
    db = tmp_path / "x.db"
    init_db(db)
    upsert_entities([row("1","One")], db)
    with pytest.raises(ValueError):
        replace_source_atomic("X", [{"source_id":"2","primary_name":"   "}], db)
    assert len(get_entities(db,"X")) == 1
