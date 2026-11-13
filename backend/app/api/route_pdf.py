from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import require_operations
from app.core.database import get_db
from app.models import Driver, Pickup, Vehicle
from app.models.route_plans import RoutePlan
from app.models.route_templates import RouteExecution, RouteTemplate
from app.services.route_pdf import render_sheet
from app.services.route_scheduling import LOCAL

router = APIRouter(tags=['Folha de rota'], dependencies=[Depends(require_operations)])


def download(db, data, filename, execution=None):
    driver = db.get(Driver, data['driver_id']) if data.get('driver_id') else None
    vehicle = db.get(Vehicle, data['vehicle_id']) if data.get('vehicle_id') else None
    date = ''
    if execution:
        starts = execution.starts_at
        date = (starts.replace(tzinfo=UTC) if starts.tzinfo is None else starts).astimezone(LOCAL).strftime('%d/%m/%Y')
    content = render_sheet(data, list(db.scalars(select(Pickup))),
                           driver.nome if driver else '', vehicle.placa if vehicle else '', date)
    return Response(content, media_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="{filename}.pdf"',
        'Cache-Control': 'no-store',
    })


@router.get('/route-templates/{id}/pdf')
def template_pdf(id: int, db: Session = Depends(get_db)):
    item = db.get(RouteTemplate, id)
    if not item or item.data.get('deleted'):
        raise HTTPException(404, 'Rota não encontrada')
    return download(db, item.data, f'rota-{id}')


@router.get('/route-plans/{id}/pdf')
def plan_pdf(id: int, db: Session = Depends(get_db)):
    item = db.get(RoutePlan, id)
    if not item or item.data.get('deleted'):
        raise HTTPException(404, 'Planejamento não encontrado')
    execution = db.scalar(select(RouteExecution).where(RouteExecution.plan_id == id))
    return download(db, item.data, f'planejamento-{id}', execution)
