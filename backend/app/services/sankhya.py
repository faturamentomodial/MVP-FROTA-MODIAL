"""Read-only query definitions for the upcoming Sankhya integration."""

import re


def invoice_lookup_query(invoice_number: str) -> str:
    """Find sales only; the invoice number may still match several companies."""
    number = str(invoice_number).strip()
    if not re.fullmatch(r"[0-9]{1,18}", number):
        raise ValueError("Número da nota deve conter de 1 a 18 dígitos.")

    return (
        "SELECT NUNOTA, NUMNOTA, CODEMP, SERIENOTA, DTNEG, CODPARC, "
        "CODCONTATO, CODCONTATOENTREGA FROM TGFCAB "
        f"WHERE NUMNOTA = {int(number)} AND TIPMOV = 'V' "
        "ORDER BY DTNEG DESC, NUNOTA DESC"
    )

import json
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from fastapi import HTTPException
from app.core.config import settings


def _post(path, data, headers):
    try:
        request = Request(settings.sankhya_base_url.rstrip('/') + path, data=data, headers=headers, method='POST')
        with urlopen(request, timeout=settings.sankhya_timeout_seconds) as response:
            return json.loads(response.read(5_000_001))
    except (OSError, ValueError) as exc:
        raise HTTPException(503, 'Falha ao consultar o Sankhya. Confira acesso, permissões e disponibilidade.') from exc


def query(sql):
    if not all((settings.sankhya_client_id, settings.sankhya_client_secret.get_secret_value(), settings.sankhya_token.get_secret_value())):
        raise HTTPException(503, 'Integração Sankhya não configurada no servidor.')
    auth = _post('/authenticate', urlencode({
        'grant_type': 'client_credentials', 'client_id': settings.sankhya_client_id,
        'client_secret': settings.sankhya_client_secret.get_secret_value(),
    }).encode(), {'Content-Type': 'application/x-www-form-urlencoded', 'X-Token': settings.sankhya_token.get_secret_value()})
    if not isinstance(auth, dict) or not auth.get('access_token'):
        raise HTTPException(503, 'Autenticação Sankhya recusada.')
    result = _post('/gateway/v1/mge/service.sbr?serviceName=DbExplorerSP.executeQuery&outputType=json',
                   json.dumps({'serviceName': 'DbExplorerSP.executeQuery', 'requestBody': {'sql': sql}}).encode(),
                   {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + auth['access_token']})
    try:
        if str(result.get('status')) != '1':
            raise HTTPException(502, 'Consulta Sankhya recusada. Solicite ao administrador autorização para DbExplorerSP.executeQuery e acesso às tabelas de notas e endereços. Nenhum endpoint alternativo foi utilizado.')
        body = result['responseBody']
        fields = [f['name'].upper() for f in body['fieldsMetadata']]
        rows = body['rows']
        if any(not isinstance(row, list) or len(row) != len(fields) for row in rows):
            raise ValueError()
        return [dict(zip(fields, row)) for row in rows]
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(502, 'Resposta inválida do Sankhya ou consulta sem permissão.') from exc


def lookup_invoice(number):
    try:
        invoice_lookup_query(number)  # Validate before constructing the read-only SQL.
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    rows = query(f"""
        SELECT CAB.NUNOTA, CAB.NUMNOTA, CAB.CODEMP, CAB.SERIENOTA,
               CAB.QTDVOL, PAR.NOMEPARC, ENDR.TIPO, ENDR.NOMEEND,
               COALESCE(CTT.NUMEND, PAR.NUMEND) AS NUMEND,
               COALESCE(CTT.COMPLEMENTO, PAR.COMPLEMENTO) AS COMPLEMENTO,
               BAI.NOMEBAI, CID.NOMECID, UFS.UF,
               COALESCE(CTT.CEP, PAR.CEP) AS CEP
        FROM TGFCAB CAB
        JOIN TGFPAR PAR ON PAR.CODPARC = CAB.CODPARC
        LEFT JOIN TGFCTT CTT ON CTT.CODPARC = CAB.CODPARC
            AND CTT.CODCONTATO = CAB.CODCONTATOENTREGA
        LEFT JOIN TSIEND ENDR ON ENDR.CODEND = COALESCE(CTT.CODEND, PAR.CODEND)
        LEFT JOIN TSIBAI BAI ON BAI.CODBAI = COALESCE(CTT.CODBAI, PAR.CODBAI)
        LEFT JOIN TSICID CID ON CID.CODCID = COALESCE(CTT.CODCID, PAR.CODCID)
        LEFT JOIN TSIUFS UFS ON UFS.CODUF = CID.UF
        WHERE CAB.NUMNOTA = {int(number)} AND CAB.TIPMOV = 'V'
        ORDER BY CAB.DTNEG DESC, CAB.NUNOTA DESC
    """)
    invoices = []
    for row in rows:
        try:
            quantity = Decimal(str(row.get('QTDVOL')))
            volumes = int(quantity) if quantity.is_finite() and quantity == quantity.to_integral_value() and 0 < quantity <= 1000000 else None
        except (InvalidOperation, ValueError, OverflowError):
            volumes = None
        street = ' '.join(str(row[k]).strip() for k in ('TIPO', 'NOMEEND') if row.get(k))
        address = ', '.join(str(v).strip() for v in [street, *[row.get(k) for k in ('NUMEND', 'COMPLEMENTO', 'NOMEBAI', 'NOMECID', 'UF', 'CEP')]] if v is not None and str(v).strip())
        if not row.get('NOMEEND') or not row.get('NOMECID'):
            address = ''
        invoices.append({'number': str(row['NUMNOTA']), 'external_id': str(row['NUNOTA']),
                         'company': str(row['CODEMP']), 'series': str(row.get('SERIENOTA') or ''),
                         'partner': str(row.get('NOMEPARC') or ''), 'volumes': volumes,
                         'address': address, 'source': 'SANKHYA'})
    return invoices
