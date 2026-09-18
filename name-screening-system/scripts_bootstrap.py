from pathlib import Path
from app.db import init_db, upsert_entities
from app.importers import parse_generic_csv

if __name__ == "__main__":
    init_db()
    rows = parse_generic_csv(Path("sample_data/watchlist_sample.csv").read_bytes(), source="DEMO")
    print({"upserted": upsert_entities(rows)})
