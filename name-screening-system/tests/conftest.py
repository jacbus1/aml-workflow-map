import os
from pathlib import Path
import pytest

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db = tmp_path / "screening.db"
    monkeypatch.setenv("SCREENING_DB", str(db))
    return db
