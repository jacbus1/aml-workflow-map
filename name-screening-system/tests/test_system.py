import importlib
from fastapi.testclient import TestClient
from app.importers import parse_generic_csv, parse_ofac_sdn
from app.matching import normalize_name, name_similarity, score_entity, screen

ENTITY={"source":"TEST","source_id":"1","entity_type":"individual","primary_name":"DERIPASKA, Oleg Vladimirovich","aliases":["Oleg Deripaska"],"dob":"02 Jan 1968","countries":["Russia"],"programs":["RUSSIA-EO14024"],"source_url":"https://example.invalid","remarks":None}
OFAC='12345,"DERIPASKA, Oleg Vladimirovich",individual,RUSSIA-EO14024,-0-,-0-,-0-,-0-,-0-,-0-,-0-,"DOB 02 Jan 1968; citizen Russia; Secondary sanctions risk."\n'
ALT='12345,1,aka,"Oleg Deripaska",-0-\n12345,2,aka,"DERIPASKA Oleg Vladimirovich",-0-\n'

def build_client(tmp_path, monkeypatch):
    db=tmp_path/'api.db'; monkeypatch.setenv('SCREENING_DB',str(db)); import app.main as main; importlib.reload(main); return TestClient(main.app)

def test_normalization():
    assert normalize_name("José-Luís O’Neill")=="JOSE LUIS O NEILL"

def test_reversed_name():
    score,_=name_similarity("Oleg Deripaska","Deripaska Oleg"); assert score>=95

def test_alias_and_identifiers():
    r=score_entity("Oleg Deripaska",ENTITY,"1968-01-02","Russia"); assert r.match_kind=="alias" and r.score==100 and r.dob_status=="match" and r.country_status=="match"

def test_dob_mismatch_not_hard_filter():
    r=score_entity("Oleg Deripaska",ENTITY,"1970-01-01","Russia"); assert r.name_score==100 and r.dob_status=="mismatch" and r.score>=90

def test_threshold_rejects_unrelated():
    assert screen("Completely Different Person",[ENTITY],threshold=80)==[]

def test_generic_import():
    rows=parse_generic_csv("primary_name,aliases,dob,country\nJane Doe,Jane D;J Doe,1985-01-01,Canada\n",source="X"); assert rows[0]["aliases"]==["Jane D","J Doe"] and rows[0]["countries"]==["Canada"]

def test_ofac_join():
    rows=parse_ofac_sdn(OFAC,ALT); assert rows[0]["source"]=="OFAC_SDN" and "Oleg Deripaska" in rows[0]["aliases"] and rows[0]["countries"]==["Russia"]

def test_api_import_screen_batch(tmp_path,monkeypatch):
    client=build_client(tmp_path,monkeypatch)
    with client:
        assert client.get('/health').status_code==200
        data='source,source_id,entity_type,primary_name,aliases,dob,countries,programs\nTEST,1,individual,Oleg Vladimirovich Deripaska,Oleg Deripaska,1968-01-02,Russia,TEST\n'
        r=client.post('/api/import/generic',files={'file':('watch.csv',data,'text/csv')},data={'source':'TEST'}); assert r.status_code==200
        r=client.post('/api/screen',json={'name':'Oleg Deripaska','dob':'1968-01-02','country':'Russia','threshold':80}); assert r.json()['matches'][0]['score']==100
        batch='name,dob,country\nOleg Deripaska,1968-01-02,Russia\nNo Match,1990-01-01,Canada\n'
        r=client.post('/api/batch',files={'file':('customers.csv',batch,'text/csv')},data={'threshold':'80'}); assert r.status_code==200 and '100.0' in r.text

def test_home_and_ofac_endpoint(tmp_path,monkeypatch):
    client=build_client(tmp_path,monkeypatch)
    with client:
        assert 'Name Screening System' in client.get('/').text
        r=client.post('/api/import/ofac',files={'primary':('SDN.CSV',OFAC,'text/csv'),'aliases':('ALT.CSV',ALT,'text/csv')},data={'replace_source':'true'}); assert r.status_code==200 and r.json()['upserted']==1
        r=client.post('/api/screen',json={'name':'Oleg Deripaska','dob':'1968-01-02','country':'Russia','threshold':80,'source':'OFAC_SDN'}); m=r.json()['matches'][0]; assert m['match_kind']=='alias' and m['score']==100
