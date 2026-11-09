from copy import deepcopy
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, update, delete
from sqlalchemy.orm import Session
from app.api.dependencies import require_admin, require_operations
from app.core.database import get_db
from app.models import Vehicle, Driver
from app.models.route_plans import RoutePlan, RoutePlanVersion
from app.schemas.route_plans import PlanInput, CalculateInput, RevisionInput
from app.services import route_planning as provider
from app.services import sankhya
from app.services.audit import audit
from pydantic import BaseModel, Field, ConfigDict


class LocationConfirmation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    address: str = Field(min_length=5, max_length=500)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)

router = APIRouter(prefix='/route-plans', tags=['Planejamento de rotas'], dependencies=[Depends(require_operations)])
WARNING = 'OSRM driving não considera altura, peso, eixos ou restrições legais de caminhões. Revisão humana obrigatória antes da operação.'


def load(db, plan_id):
    plan = db.get(RoutePlan, plan_id)
    if not plan or plan.data.get('deleted', False):
        raise HTTPException(404, 'Planejamento não encontrado')
    return plan


def output(plan):
    return {'id': plan.id, 'revision': plan.revision, 'status': plan.status, **plan.data}


def validate_vehicle(db, data):
    if data.driver_id is not None:
        driver = db.get(Driver, data.driver_id)
        if not driver or not driver.ativo or not driver.user.ativo:
            raise HTTPException(422, 'Selecione um motorista ativo')
    if data.vehicle_id is not None:
        vehicle = db.get(Vehicle, data.vehicle_id)
        if not vehicle or not vehicle.ativo:
            raise HTTPException(422, 'Selecione um veículo ativo')


def save(db, plan, revision, data, user, status='RASCUNHO'):
    from app.services.route_scheduling import is_execution_plan
    if is_execution_plan(db, plan.id):
        raise HTTPException(409, 'Use a programação semanal para alterar esta execução')
    result = db.execute(update(RoutePlan).where(RoutePlan.id == plan.id, RoutePlan.revision == revision, RoutePlan.status == 'RASCUNHO').values(revision=revision+1, data=data, status=status), execution_options={'synchronize_session': False})
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'Planejamento alterado por outro usuário ou já confirmado. Recarregue antes de editar.')
    db.add(RoutePlanVersion(plan_id=plan.id, revision=revision+1, data={'status': status, **deepcopy(data)}, created_by=user.id))
    db.commit()
    db.refresh(plan)
    return output(plan)


@router.get('')
def list_plans(db: Session = Depends(get_db), limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
    from app.models.route_templates import RouteExecution
    return [output(p) for p in db.scalars(select(RoutePlan).where(~RoutePlan.id.in_(select(RouteExecution.plan_id)), RoutePlan.data['deleted'].as_boolean().is_not(True)).order_by(RoutePlan.id.desc()).offset(offset).limit(limit))]


@router.get('/providers', dependencies=[Depends(require_admin)])
def providers():
    return {'geocoder': provider.settings.routes_geocoder_provider, 'router': 'osrm', 'truck_restrictions_supported': False, 'warning': WARNING, 'max_invoices': 10, 'return_to_origin': True}


@router.get('/geocode')
def geocode(address: str = Query(min_length=5, max_length=500), db: Session = Depends(get_db)):
    from app.services.geocoding_cache import geocode as cached_geocode
    return cached_geocode(db, address)


@router.get('/invoice-lookup', dependencies=[Depends(require_admin)])
def invoice_lookup(number: str = Query(pattern=r"^[0-9]{1,18}$")):
    return {'invoices': sankhya.lookup_invoice(number)}


@router.post('/geocode/confirm', dependencies=[Depends(require_admin)])
def confirm_location(payload: LocationConfirmation, db: Session = Depends(get_db), user=Depends(require_admin)):
    from app.services.geocoding_cache import confirm
    result = confirm(db, payload.address, payload.latitude, payload.longitude, user.id)
    audit(db, user, 'CONFIRMAR_LOCALIZACAO', 'GEOCODING', None,
          {'address': payload.address, 'latitude': payload.latitude, 'longitude': payload.longitude})
    db.commit()
    return result


@router.post('', status_code=201, dependencies=[Depends(require_admin)])
def create(payload: PlanInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    validate_vehicle(db, payload)
    data = payload.model_dump(exclude={'revision'})
    data.update(stops=[], result=None)
    plan = RoutePlan(data=data, created_by=user.id)
    db.add(plan)
    db.flush()
    db.add(RoutePlanVersion(plan_id=plan.id, revision=0, data={'status': 'RASCUNHO', **data}, created_by=user.id))
    db.commit()
    return output(plan)


@router.get('/{plan_id}')
def detail(plan_id: int, db: Session = Depends(get_db)):
    return output(load(db, plan_id))


@router.get('/{plan_id}/versions', dependencies=[Depends(require_admin)])
def versions(plan_id: int, db: Session = Depends(get_db)):
    load(db, plan_id)
    return [{'revision': v.revision, 'data': v.data} for v in db.scalars(select(RoutePlanVersion).where(RoutePlanVersion.plan_id == plan_id).order_by(RoutePlanVersion.revision))]


@router.delete('/{plan_id}', status_code=204, dependencies=[Depends(require_admin)])
def delete_plan(plan_id: int, revision: int = Query(..., ge=0), db: Session = Depends(get_db), user=Depends(require_admin)):
    from app.services.route_scheduling import is_execution_plan
    plan = load(db, plan_id)
    if is_execution_plan(db, plan_id):
        raise HTTPException(409, 'Use a programação semanal para cancelar esta execução')
    trip_id = plan.data.get('trip_id')
    trip_matches = RoutePlan.data['trip_id'].as_integer() == trip_id if trip_id else RoutePlan.data['trip_id'].as_integer().is_(None)
    claimed = db.execute(update(RoutePlan).where(RoutePlan.id == plan_id, RoutePlan.revision == revision, trip_matches)
                         .values(revision=revision+1, data={**plan.data, 'deleted': True}), execution_options={'synchronize_session': False})
    if claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, 'Planejamento alterado. Recarregue antes de excluir')
    audit(db, user, 'EXCLUIR', 'ROUTE_PLAN', plan_id, {'name': plan.data.get('name'), 'trip_id': plan.data.get('trip_id')})
    if not plan.data.get('trip_id'):
        db.execute(delete(RoutePlanVersion).where(RoutePlanVersion.plan_id == plan_id))
        db.execute(delete(RoutePlan).where(RoutePlan.id == plan_id))
    db.commit()
    return Response(status_code=204)


@router.put('/{plan_id}', dependencies=[Depends(require_admin)])
def edit(plan_id: int, payload: PlanInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    validate_vehicle(db, payload)
    data = payload.model_dump(exclude={'revision'})
    data.update(stops=[], result=None)
    return save(db, load(db, plan_id), payload.revision, data, user)


def points_and_stops(plan):
    data = plan.data
    if not data.get('origin') or not data.get('invoices') or not data.get('vehicle_id'):
        raise HTTPException(422, 'Informe origem, veículo e pelo menos uma nota')
    stops = []
    for note in data['invoices']:
        point = note['destination']
        key = (point['latitude'], point['longitude'])
        existing = next((s for s in stops if (s['latitude'], s['longitude']) == key), None)
        if existing:
            existing['invoices'].append(note['number'])
        else:
            stops.append({**point, 'invoices': [note['number']]})
    return [data['origin']] + stops, stops


@router.post('/{plan_id}/matrix', dependencies=[Depends(require_admin)])
def matrix(plan_id: int, db: Session = Depends(get_db)):
    points, stops = points_and_stops(load(db, plan_id))
    return {'stops': stops, 'provider': 'osrm', **provider.matrix(points)}


@router.post('/{plan_id}/calculate', dependencies=[Depends(require_admin)])
def calculate(plan_id: int, payload: CalculateInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    plan = load(db, plan_id)
    if plan.revision != payload.revision or plan.status != 'RASCUNHO':
        raise HTTPException(409, 'Recarregue o planejamento antes de calcular')
    points, stops = points_and_stops(plan)
    data = deepcopy(plan.data)
    matrix = provider.matrix(points)
    order = provider.optimal_order(matrix['durations' if data['objective'] == 'duration' else 'distances']) if payload.optimize else list(range(1, len(points)))
    result = provider.geometry([points[0]] + [points[i] for i in order] + [points[0]])
    data['stops'] = [stops[i-1] for i in order]
    notes = {n['number']: n for n in data['invoices']}
    data['invoices'] = [notes[number] for stop in data['stops'] for number in stop['invoices']]
    data['result'] = {**result, 'matrix': {'durations': matrix['durations'], 'distances': matrix['distances']}, 'matrix_points': points, 'provider': 'osrm', 'truck_restrictions_supported': False, 'warning': WARNING if data['profile'] == 'truck' else None, 'algorithm': 'held-karp' if payload.optimize else 'manual', 'objective': data['objective'], 'return_to_origin': True}
    return save(db, plan, payload.revision, data, user)


@router.post('/{plan_id}/confirm', dependencies=[Depends(require_admin)])
def confirm(plan_id: int, payload: RevisionInput, db: Session = Depends(get_db), user=Depends(require_admin)):
    plan = load(db, plan_id)
    validate_vehicle(db, PlanInput.model_validate({k: v for k, v in plan.data.items() if k in PlanInput.model_fields}))
    if not plan.data.get('result'):
        raise HTTPException(422, 'Calcule o percurso antes de confirmar')
    return save(db, plan, payload.revision, plan.data, user, 'CONFIRMADO')
