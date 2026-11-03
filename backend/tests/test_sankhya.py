import pytest
from fastapi import HTTPException
from app.services import sankhya


def test_invoice_mapping_and_invalid_volume(monkeypatch):
    row = dict(NUNOTA=321, NUMNOTA=123, CODEMP=1, SERIENOTA='A', QTDVOL='4', NOMEPARC='Cliente', TIPO='Rua', NOMEEND='Teste', NUMEND='10', NOMECID='São Paulo', UF='SP', CEP='01001000')
    monkeypatch.setattr(sankhya, 'query', lambda sql: [row])
    result = sankhya.lookup_invoice('123')[0]
    assert result['volumes'] == 4
    assert result['external_id'] == '321'
    assert result['address'] == 'Rua Teste, 10, São Paulo, SP, 01001000'
    row['QTDVOL'] = '2.5'
    assert sankhya.lookup_invoice('123')[0]['volumes'] is None
    row['NOMEEND'] = None
    assert sankhya.lookup_invoice('123')[0]['address'] == ''


def test_lookup_rejects_sql_injection():
    with pytest.raises(HTTPException) as exc:
        sankhya.lookup_invoice('1 OR 1=1')
    assert exc.value.status_code == 422


def test_lookup_endpoint_permissions_and_ambiguity(client, admin_headers, driver_headers, monkeypatch):
    matches = [{'external_id': '1'}, {'external_id': '2'}]
    monkeypatch.setattr(sankhya, 'lookup_invoice', lambda number: matches)
    url = '/api/route-plans/invoice-lookup?number=123'
    assert client.get(url).status_code == 401
    assert client.get(url, headers=driver_headers).status_code == 403
    assert client.get(url, headers=admin_headers).json()['invoices'] == matches
    assert client.get(url.replace('123','abc'), headers=admin_headers).status_code == 422


def test_unconfigured_integration(monkeypatch):
    monkeypatch.setattr(sankhya.settings, 'sankhya_client_id', '')
    with pytest.raises(HTTPException) as exc:
        sankhya.query('SELECT 1')
    assert exc.value.status_code == 503
