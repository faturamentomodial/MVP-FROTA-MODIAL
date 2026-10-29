from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import Checklist, Driver, Trip, TripInvoice, User, Vehicle
from app.models.route_plans import RoutePlan
from app.models.enums import TripStatus, VehicleStatus
from app.schemas import TripCreate, TripFinish
from app.services.audit import audit
from app.services.deliveries import claim_revision


ACTIVE_TRIP_STATUSES = (TripStatus.ABERTA, TripStatus.EM_ANDAMENTO)


def get_driver_for_user(db: Session, user: User) -> Driver:
    driver = db.scalar(select(Driver).where(Driver.user_id == user.id))
    if not driver:
        raise HTTPException(status_code=403, detail="Usuário não possui cadastro de motorista")
    return driver


def get_active_trip(db: Session, driver_id: int) -> Trip | None:
    return db.scalar(
        select(Trip)
        .where(Trip.driver_id == driver_id, Trip.status.in_(ACTIVE_TRIP_STATUSES))
        .options(joinedload(Trip.vehicle), joinedload(Trip.driver), joinedload(Trip.checklist), selectinload(Trip.invoices))
    )


def create_trip(db: Session, user: User, payload: TripCreate) -> Trip:
    driver = get_driver_for_user(db, user)
    if not driver.ativo or not driver.user.ativo:
        raise HTTPException(status_code=400, detail="Motorista inativo não pode iniciar saída")
    if get_active_trip(db, driver.id):
        raise HTTPException(status_code=409, detail="Motorista já possui uma viagem aberta")

    if payload.route_plan_id is None:
        raise HTTPException(403, "Inicie somente uma rota vinculada pelo gestor")

    plan = None
    if payload.route_plan_id is not None:
        plan = db.scalar(select(RoutePlan).where(RoutePlan.id == payload.route_plan_id).with_for_update())
        if not plan or plan.data.get('driver_id') != driver.id:
            raise HTTPException(403, 'Planejamento não pertence a este motorista')
        if plan.status != 'CONFIRMADO' or plan.data.get('trip_id'):
            raise HTTPException(409, 'Planejamento indisponível para iniciar saída')
        if plan.data.get('vehicle_id') != payload.vehicle_id:
            raise HTTPException(422, 'Utilize o veículo do planejamento')

    vehicle = db.scalar(select(Vehicle).where(Vehicle.id == payload.vehicle_id).with_for_update())
    if not vehicle:
        raise HTTPException(status_code=404, detail="Veículo não encontrado")
    if not vehicle.ativo or vehicle.status == VehicleStatus.INATIVO:
        raise HTTPException(status_code=400, detail="Veículo inativo não pode iniciar viagem")
    if vehicle.status != VehicleStatus.DISPONIVEL:
        raise HTTPException(status_code=409, detail="Veículo não está disponível")
    if payload.km_inicial < vehicle.km_atual:
        raise HTTPException(status_code=400, detail="KM inicial não pode ser menor que o KM atual do veículo")
    vehicle.status = VehicleStatus.EM_VIAGEM
    trip = Trip(driver_id=driver.id, vehicle_id=vehicle.id, km_inicial=payload.km_inicial)
    db.add(trip)
    try:
        db.flush()
        if plan:
            data = {**plan.data, 'trip_id': trip.id}
            claimed = db.execute(update(RoutePlan).where(
                RoutePlan.id == plan.id, RoutePlan.revision == plan.revision,
                RoutePlan.data['trip_id'].as_integer().is_(None),
            ).values(data=data), execution_options={'synchronize_session': False})
            if claimed.rowcount != 1:
                db.rollback()
                raise HTTPException(409, 'Planejamento já utilizado')
            trip.invoices = [TripInvoice(numero_nota=n['number'], volumes=n['volumes'], position=i)
                             for i, n in enumerate(plan.data['invoices'], start=1)]
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Motorista ou veículo já possui viagem aberta") from exc
    audit(db, user, "CRIAR", "TRIP", trip.id, {"vehicle_id": vehicle.id, "km_inicial": payload.km_inicial})
    db.commit()
    return load_trip(db, trip.id)


def load_trip(db: Session, trip_id: int) -> Trip:
    trip = db.scalar(
        select(Trip)
        .where(Trip.id == trip_id)
        .options(
            joinedload(Trip.driver),
            joinedload(Trip.vehicle),
            joinedload(Trip.checklist).selectinload(Checklist.answers),
            selectinload(Trip.occurrences),
            selectinload(Trip.invoices),
        )
    )
    if not trip:
        raise HTTPException(status_code=404, detail="Viagem não encontrada")
    return trip


def start_trip(db: Session, trip: Trip, user: User) -> Trip:
    if trip.status != TripStatus.ABERTA:
        raise HTTPException(status_code=400, detail="A viagem não está aguardando início")
    if not trip.checklist:
        raise HTTPException(status_code=400, detail="Não é possível iniciar sem checklist completo")
    if not trip.invoices:
        raise HTTPException(status_code=400, detail="Não é possível iniciar sem as notas e volumes da carga")
    claim_revision(db, trip, trip.delivery_revision)
    trip.status = TripStatus.EM_ANDAMENTO
    audit(db, user, "INICIAR", "TRIP", trip.id)
    db.commit()
    return load_trip(db, trip.id)


def finish_trip(db: Session, trip: Trip, payload: TripFinish, user: User) -> Trip:
    if trip.status != TripStatus.EM_ANDAMENTO:
        raise HTTPException(status_code=400, detail="Somente viagem em andamento pode ser finalizada")
    if payload.km_final < trip.km_inicial:
        raise HTTPException(status_code=400, detail="KM final não pode ser menor que KM inicial")
    if any(n.status.value in ("PENDENTE", "EM_ENTREGA") for n in trip.invoices):
        raise HTTPException(status_code=409, detail="Resolva todas as entregas antes de finalizar a viagem")
    claim_revision(db, trip, trip.delivery_revision)
    trip.km_final = payload.km_final
    trip.km_percorrido = payload.km_final - trip.km_inicial
    trip.data_retorno = datetime.now(UTC)
    trip.observacao = payload.observacao
    trip.status = TripStatus.FINALIZADA
    trip.vehicle.km_atual = payload.km_final
    trip.vehicle.status = VehicleStatus.DISPONIVEL if trip.vehicle.ativo else VehicleStatus.INATIVO
    audit(db, user, "FINALIZAR", "TRIP", trip.id, {"km_final": payload.km_final, "km_percorrido": trip.km_percorrido})
    db.commit()
    return load_trip(db, trip.id)
