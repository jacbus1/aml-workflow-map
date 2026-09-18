from pathlib import Path
from app.importers import parse_generic_csv, parse_ofac_sdn

FIX = Path(__file__).parent / "fixtures"

def test_generic_csv():
    rows = parse_generic_csv("primary_name,aliases,dob,country\nJane Doe,Jane D;J Doe,1985-01-01,Canada\n", source="X")
    assert rows[0]["primary_name"] == "Jane Doe"
    assert rows[0]["aliases"] == ["Jane D", "J Doe"]
    assert rows[0]["countries"] == ["Canada"]

def test_ofac_primary_and_alias_join():
    rows = parse_ofac_sdn((FIX/"ofac_sdn.csv").read_bytes(), (FIX/"ofac_alt.csv").read_bytes())
    assert len(rows) == 2
    p = rows[0]
    assert p["source"] == "OFAC_SDN"
    assert "Oleg Deripaska" in p["aliases"]
    assert p["dob"] == "02 Jan 1968"
    assert p["countries"] == ["Russia"]
