from pathlib import Path

from app.importers import (
    parse_canada_xml,
    parse_ofac_sdn,
    parse_uk_sanctions_csv,
    parse_un_xml,
)

FIX = Path(__file__).parent / "fixtures"


def test_ofac_four_file_join_and_weak_alias():
    rows = parse_ofac_sdn(
        (FIX/"ofac_sdn.csv").read_bytes(),
        (FIX/"ofac_alt_v2.csv").read_bytes(),
        (FIX/"ofac_add.csv").read_bytes(),
        (FIX/"ofac_comments.csv").read_bytes(),
    )
    p = next(x for x in rows if x["source_id"] == "12345")
    assert "Oleg Deripaska" in p["aliases"]
    assert "Oleg D" in p["weak_aliases"]
    assert "OLEG THE TALL" in p["weak_aliases"]
    assert "Russia" in p["countries"]
    assert "Additional identifier information" in p["remarks"]


def test_uk_csv_groups_name_records_and_alias_strength():
    rows = parse_uk_sanctions_csv((FIX/"uk_sanctions.csv").read_bytes())
    assert len(rows) == 1
    r = rows[0]
    assert r["source_id"] == "RUS0270"
    assert r["primary_name"] == "Roman Arkadyevich ABRAMOVICH"
    assert "Roman ABRAMOVICH" in r["aliases"]
    assert "Roma RA" in r["weak_aliases"]
    assert r["dob"] == "24/10/1966"
    assert "Роман Аркадьевич АБРАМОВИЧ" in r["native_names"]


def test_un_xml_good_low_alias_multiple_dob_and_native_script():
    rows = parse_un_xml((FIX/"un_consolidated.xml").read_bytes())
    person = next(x for x in rows if x["entity_type"] == "individual")
    assert person["source_id"] == "QDi.999"
    assert "Mohamed Example Person" in person["aliases"]
    assert "Abu Example" in person["weak_aliases"]
    assert person["dobs"] == ["1970-05-10", "1971"]
    assert "Exampleland" in person["countries"]
    assert "محمد مثال" in person["native_names"]


def test_canada_xml_tolerant_parser():
    rows = parse_canada_xml((FIX/"canada.xml").read_bytes())
    assert len(rows) == 1
    r = rows[0]
    assert r["primary_name"] == "Jane Marie DOE"
    assert "Jane M Doe" in r["aliases"]
    assert r["dob"] == "1980/03/12"
    assert "Special Economic Measures Example Regulations" in r["programs"]
