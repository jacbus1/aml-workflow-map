import importlib
from fastapi.testclient import TestClient


def build_client(tmp_path, monkeypatch):
    db = tmp_path / "api.db"
    monkeypatch.setenv("SCREENING_DB", str(db))
    import app.main as main
    importlib.reload(main)
    return TestClient(main.app), main


def test_health_import_screen_and_batch(tmp_path, monkeypatch):
    client, main = build_client(tmp_path, monkeypatch)
    with client:
        assert client.get("/health").status_code == 200
        data = "source,source_id,entity_type,primary_name,aliases,dob,countries,programs\nTEST,1,individual,Oleg Vladimirovich Deripaska,Oleg Deripaska,1968-01-02,Russia,TEST\n"
        r = client.post("/api/import/generic", files={"file": ("watch.csv", data, "text/csv")}, data={"source":"TEST"})
        assert r.status_code == 200 and r.json()["upserted"] == 1
        r = client.post("/api/screen", json={"name":"Oleg Deripaska","dob":"1968-01-02","country":"Russia","threshold":80})
        assert r.status_code == 200
        assert r.json()["matches"][0]["score"] == 100
        batch = "name,dob,country\nOleg Deripaska,1968-01-02,Russia\nNo Match,1990-01-01,Canada\n"
        r = client.post("/api/batch", files={"file": ("customers.csv", batch, "text/csv")}, data={"threshold":"80"})
        assert r.status_code == 200
        text = r.text
        assert "Oleg Deripaska" in text and "100.0" in text


def test_home_and_ofac_import_endpoint(tmp_path, monkeypatch):
    client, main = build_client(tmp_path, monkeypatch)
    from pathlib import Path
    fix = Path(__file__).parent / "fixtures"
    with client:
        home = client.get("/")
        assert home.status_code == 200
        assert "Jac Name Screening v2" in home.text
        r = client.post(
            "/api/import/ofac",
            files={
                "primary": ("SDN.CSV", (fix / "ofac_sdn.csv").read_bytes(), "text/csv"),
                "aliases": ("ALT.CSV", (fix / "ofac_alt.csv").read_bytes(), "text/csv"),
            },
            data={"replace_source":"true"},
        )
        assert r.status_code == 200
        assert r.json()["upserted"] == 2
        r = client.post("/api/screen", json={"name":"Oleg Deripaska","dob":"1968-01-02","country":"Russia","threshold":80,"source":"OFAC_SDN"})
        assert r.status_code == 200
        m = r.json()["matches"][0]
        assert m["source"] == "OFAC_SDN"
        assert m["match_kind"] == "alias"
        assert m["score"] == 100
