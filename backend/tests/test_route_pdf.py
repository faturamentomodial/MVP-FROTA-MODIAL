from copy import deepcopy
from io import BytesIO
from types import SimpleNamespace

from pypdf import PdfReader

from app.core.database import SessionLocal
from app.models import Pickup
from app.models.route_templates import RouteTemplate
from app.services.route_pdf import render_sheet, sheet_rows
from test_route_templates import template, booking, schedule


def test_pdf_download_is_read_only_and_uses_collection_data(client, admin_headers, driver_headers, monkeypatch):
    route = template(client, admin_headers, monkeypatch)
    with SessionLocal() as db:
        item = db.get(RouteTemplate, route['id'])
        data = deepcopy(item.data)
        data['stops'] = [
            {'address': 'Maria · Rua das Flores, 10', 'invoices': []},
            {'address': 'Ana · Rua das Rosas, 20', 'invoices': []},
        ]
        item.data = data
        db.add_all([
            Pickup(nome='Ana', endereco='Rua das Rosas, 20', telefone='2222', tipo='FLORISTA'),
            Pickup(nome='Maria', endereco='Rua das Flores, 10', telefone='1111', tipo='COSTUREIRA'),
        ])
        db.commit()
        revision = item.revision
    url = f"/api/route-templates/{route['id']}/pdf"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=driver_headers).status_code == 403
    response = client.get(url, headers=admin_headers)
    assert response.status_code == 200
    assert response.headers['content-type'] == 'application/pdf'
    assert response.headers['cache-control'] == 'no-store'
    assert 'attachment' in response.headers['content-disposition']
    reader = PdfReader(BytesIO(response.content))
    assert len(reader.pages) == 1
    assert abs(float(reader.pages[0].mediabox.width)-841.89) < .1
    assert abs(float(reader.pages[0].mediabox.height)-595.28) < .1
    text = ' '.join(reader.pages[0].extract_text().split())
    assert text.index('Maria') < text.index('Ana')
    assert all(value in text for value in ['1111', '2222', 'Costureira', 'Florista', 'Volumes para deixar', 'Volumes recolhidos'])
    assert 'Lastex' not in text
    with SessionLocal() as db:
        item = db.get(RouteTemplate, route['id'])
        assert item.data == data and item.revision == revision
    assert client.get('/api/route-templates/999999/pdf', headers=admin_headers).status_code == 404


def test_execution_pdf_contains_assignment_and_date(client, admin_headers, monkeypatch):
    route = template(client, admin_headers, monkeypatch)
    execution = schedule(client, admin_headers, booking(route)).json()
    response = client.get(f"/api/route-plans/{execution['plan_id']}/pdf", headers=admin_headers)
    assert response.status_code == 200
    text = PdfReader(BytesIO(response.content)).pages[0].extract_text()
    assert execution['driver_name'] in text
    assert execution['vehicle_plate'] in text
    assert '/'.join(reversed(execution['date'].split('-'))) in text


def test_rows_keep_stop_order_and_blank_manual_columns():
    pickups = [SimpleNamespace(nome='Ana', endereco='Rua A', telefone='111', tipo='FLORISTA'),
               SimpleNamespace(nome='Outra', endereco='Rua A', telefone='222', tipo='COSTUREIRA')]
    data = {'stops': [{'address': 'Rua desconhecida', 'invoices': ['2', '1']},
                      {'address': 'Ana · Rua A', 'invoices': []},
                      {'address': 'Rua A', 'invoices': []}],
            'invoices': [{'number': '1', 'volumes': 3}, {'number': '2', 'volumes': 4}]}
    rows = sheet_rows(data, pickups)
    assert rows[0] == ['1', '', '', 'Rua desconhecida', '', '7', '', '']
    assert rows[1][1:5] == ['Ana', '111', 'Rua A', 'Florista']
    assert rows[2][1:3] == ['', '']  # Never guess between contacts at the same address.
    assert all(row[-2:] == ['', ''] for row in rows)
    data['stops'][1]['pickup_volume'] = '10 caixas e 2 paletes'
    assert sheet_rows(data, pickups)[1][5] == '10 caixas e 2 paletes'


def test_long_route_repeats_headers_without_losing_stops():
    data = {'name': 'Rota longa <teste> & impressão',
            'addresses': [{'address': f'PARADA-{i:03d} ' + 'endereço longo '*15} for i in range(100)]}
    reader = PdfReader(BytesIO(render_sheet(data, [])))
    assert len(reader.pages) > 1
    texts = [' '.join(page.extract_text().split()) for page in reader.pages]
    assert all('Volumes recolhidos' in text and 'Motorista:' in text for text in texts)
    combined = '\n'.join(texts)
    assert all(combined.count(f'PARADA-{i:03d}') == 1 for i in range(100))
