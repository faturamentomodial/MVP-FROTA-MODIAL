"""On-demand route sheets. No persistence or routing/provider calls."""
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle


PRODUCTS = {'COSTUREIRA': 'Costureira', 'FLORISTA': 'Florista', 'FORNECEDOR': 'Fornecedor'}


def sheet_rows(data, pickups):
    # Persisted stops are authoritative; never optimize or sort during export.
    stops = data.get('stops') or [
        {**point, 'invoices': []} for point in data.get('addresses', [])
    ] or [{**n['destination'], 'invoices': [n['number']]} for n in data.get('invoices', [])]
    notes = {n['number']: n for n in data.get('invoices', [])}
    rows = []
    for index, stop in enumerate(stops, 1):
        address = stop['address']
        # Existing collection stops store "name · address", not a collection ID.
        matches = [p for p in pickups if address == f'{p.nome} · {p.endereco}'[:500]]
        if not matches:
            matches = [p for p in pickups if address == p.endereco]
        pickup = matches[0] if len(matches) == 1 else None
        volumes = sum(notes[number]['volumes'] for number in stop.get('invoices', []) if number in notes)
        rows.append([str(index), pickup.nome if pickup else '', pickup.telefone if pickup else '',
                     pickup.endereco if pickup else address,
                     PRODUCTS.get(pickup.tipo, '') if pickup else '',
                     stop.get('pickup_volume') or (str(volumes) if volumes else ''), '', ''])
    return rows


def render_sheet(data, pickups, driver='', vehicle='', date=''):
    buffer = BytesIO()
    width, height = landscape(A4)
    doc = SimpleDocTemplate(buffer, pagesize=(width, height), leftMargin=18, rightMargin=18,
                            topMargin=88, bottomMargin=26, title='Folha de rota')
    style = ParagraphStyle('cell', fontName='Helvetica', fontSize=8, leading=10)
    heading = ParagraphStyle('heading', parent=style, fontName='Helvetica-Bold', alignment=1)
    def cell(value, header=False):
        return Paragraph(escape(str(value)).replace('\n', '<br/>'), heading if header else style)
    headers = ['Nº', 'Nome', 'Telefone', 'Endereço', 'Produto', 'Volumes',
               'Volumes para deixar', 'Volumes recolhidos']
    rows = sheet_rows(data, pickups)
    table = Table([[cell(h, True) for h in headers]] + [[cell(v) for v in row] for row in rows],
                  colWidths=[26, 120, 80, width-36-26-120-80-85-48-75-75, 85, 48, 75, 75],
                  minRowHeights=[36] + [26]*len(rows), repeatRows=1)
    table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), .5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eeeeee')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    def page(canvas, document):
        canvas.saveState()
        title = Paragraph('FOLHA DE ROTA · ' + escape(data.get('name', '')), heading)
        _, title_height = title.wrap(width-36, 30)
        title.drawOn(canvas, 18, height-18-title_height)
        details = Paragraph(f'Motorista: {escape(driver) or "________________"} · '
                            f'Veículo: {escape(vehicle) or "________________"} · '
                            f'Data: {escape(date) or "____/____/________"}', style)
        details.wrap(width-36, 24)
        details.drawOn(canvas, 18, height-54)
        canvas.setFont('Helvetica', 8)
        canvas.drawString(18, height-72, 'Hora de chegada: ______________    |    Horário de saída: ______________')
        canvas.drawRightString(width-18, 12, f'Página {document.page}')
        canvas.restoreState()
    doc.build([table], onFirstPage=page, onLaterPages=page)
    return buffer.getvalue()
