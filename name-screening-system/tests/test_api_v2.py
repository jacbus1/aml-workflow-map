import importlib

from fastapi.testclient import TestClient


def build_client(tmp_path, monkeypatch, *, max_upload=None, max_rows=None):
    db = tmp_path / "api-v2.db"
    monkeypatch.setenv("SCREENING_DB", str(db))
    if max_upload is not None:
        monkeypatch.setenv("SCREENING_MAX_UPLOAD_BYTES", str(max_upload))
    else:
        monkeypatch.delenv("SCREENING_MAX_UPLOAD_BYTES", raising=False)
    if max_rows is not None:
        monkeypatch.setenv("SCREENING_MAX_BATCH_ROWS", str(max_rows))
    else:
        monkeypatch.delenv("SCREENING_MAX_BATCH_ROWS", raising=False)
    import app.main as main
    importlib.reload(main)
    return TestClient(main.app), main


def test_security_headers_and_version(tmp_path, monkeypatch):
    client, _ = build_client(tmp_path, monkeypatch)
    with client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["version"] == "2.0.0"
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["x-frame-options"] == "DENY"
        assert r.headers["cache-control"] == "no-store"


def test_blank_name_rejected(tmp_path, monkeypatch):
    client, _ = build_client(tmp_path, monkeypatch)
    with client:
        r = client.post("/api/screen", json={"name":"   "})
        assert r.status_code == 422


def test_upload_limit(tmp_path, monkeypatch):
    client, _ = build_client(tmp_path, monkeypatch, max_upload=50)
    with client:
        data = "primary_name,aliases\n" + ("A" * 100) + ",\n"
        r = client.post("/api/import/generic", files={"file": ("watch.csv", data, "text/csv")})
        assert r.status_code == 413


def test_batch_row_limit(tmp_path, monkeypatch):
    client, _ = build_client(tmp_path, monkeypatch, max_rows=2)
    with client:
        batch = "name\nOne\nTwo\nThree\n"
        r = client.post("/api/batch", files={"file": ("customers.csv", batch, "text/csv")})
        assert r.status_code == 413


def test_csv_formula_injection_is_escaped(tmp_path, monkeypatch):
    client, _ = build_client(tmp_path, monkeypatch)
    with client:
        batch = 'name\n"=HYPERLINK(""https://example.invalid"")"\n'
        r = client.post("/api/batch", files={"file": ("customers.csv", batch, "text/csv")})
        assert r.status_code == 200
        assert "'=HYPERLINK" in r.text


def test_atomic_generic_replace_removes_stale(tmp_path, monkeypatch):
    client, _ = build_client(tmp_path, monkeypatch)
    with client:
        first = "source_id,primary_name\n1,One\n2,Two\n"
        second = "source_id,primary_name\n2,Two Updated\n3,Three\n"
        r = client.post("/api/import/generic", files={"file": ("a.csv", first, "text/csv")}, data={"source":"X", "replace_source":"true"})
        assert r.status_code == 200 and r.json()["inserted"] == 2
        r = client.post("/api/import/generic", files={"file": ("b.csv", second, "text/csv")}, data={"source":"X", "replace_source":"true"})
        assert r.status_code == 200 and r.json()["inserted"] == 2
        r = client.post("/api/screen", json={"name":"One", "threshold":80, "source":"X"})
        assert r.status_code == 200 and r.json()["matches"] == []
        r = client.post("/api/screen", json={"name":"Three", "threshold":80, "source":"X"})
        assert r.json()["matches"][0]["primary_name"] == "Three"
