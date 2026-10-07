from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.models import Checklist, ChecklistAnswer, ChecklistItem, Driver, Occurrence, Trip, User, Vehicle
from app.models.enums import AnswerStatus, ChecklistStatus, OccurrenceStatus, OccurrenceType, TripStatus, UserRole, VehicleStatus


ITEMS = [
    "Pneus", "Freios", "Faróis", "Lanternas", "Setas", "Retrovisores", "Para-brisa", "Limpadores",
    "Buzina", "Extintor", "Documentação", "Estrutura externa", "Carroceria/Baú", "Portas/fechaduras",
    "Equipamentos obrigatórios",
]


def seed() -> None:
    if settings.environment.lower() == "production":
        raise RuntimeError("Seed de desenvolvimento não pode ser executado em produção")
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)):
            print("Banco já possui dados; seed ignorado.")
            return
        admin = User(nome="Gestor Modial", email="admin.frota@modial.com.br", senha_hash=get_password_hash("Admin@123"), role=UserRole.ADMIN)
        db.add(admin)
        drivers = []
        for index, name in enumerate(("João Silva", "Marcos Lima", "Carlos Souza"), start=1):
            user = User(nome=name, email=f"motorista{index}@modial.com.br", senha_hash=get_password_hash("Motorista@123"), role=UserRole.MOTORISTA)
            driver = Driver(nome=name, cpf=f"1234567890{index}", telefone=f"1199999000{index}", user=user)
            drivers.append(driver)
            db.add(driver)
        vehicles = [
            Vehicle(placa="ABC1D23", marca="Volkswagen", modelo="Delivery 11.180", tipo="Baú", km_atual=125420),
            Vehicle(placa="DEF4G56", marca="Mercedes-Benz", modelo="Accelo 1016", tipo="Baú", km_atual=89300),
            Vehicle(placa="GHI7J89", marca="Iveco", modelo="Daily 35-160", tipo="Furgão", km_atual=64110),
            Vehicle(placa="JKL0M12", marca="Renault", modelo="Master", tipo="Furgão", km_atual=97780, status=VehicleStatus.ATENCAO),
            Vehicle(placa="NOP3Q45", marca="Fiat", modelo="Fiorino", tipo="Utilitário", km_atual=45120),
        ]
        db.add_all(vehicles)
        items = [ChecklistItem(nome=name, ordem=index, obrigatorio=True) for index, name in enumerate(ITEMS, start=1)]
        db.add_all(items)
        db.flush()

        trip = Trip(
            driver_id=drivers[0].id,
            vehicle_id=vehicles[0].id,
            data_saida=datetime.now(UTC) - timedelta(days=1, hours=7),
            data_retorno=datetime.now(UTC) - timedelta(days=1),
            km_inicial=125100,
            km_final=125420,
            km_percorrido=320,
            status=TripStatus.FINALIZADA,
        )
        db.add(trip)
        db.flush()
        checklist = Checklist(trip_id=trip.id, driver_id=trip.driver_id, vehicle_id=trip.vehicle_id, status=ChecklistStatus.COM_PROBLEMAS)
        checklist.answers = [
            ChecklistAnswer(checklist_item_id=item.id, status=AnswerStatus.PROBLEMA if item.nome == "Pneus" else AnswerStatus.OK, observacao="Calibragem corrigida antes da saída" if item.nome == "Pneus" else None)
            for item in items
        ]
        occurrence = Occurrence(
            trip_id=trip.id,
            driver_id=trip.driver_id,
            vehicle_id=trip.vehicle_id,
            tipo=OccurrenceType.ATRASO,
            descricao="Trânsito intenso no trajeto",
            local="Guarulhos - SP",
            status=OccurrenceStatus.RESOLVIDA,
        )
        db.add_all([checklist, occurrence])
        db.commit()
        print("Seed criado. Admin: admin.frota@modial.com.br / Admin@123")


if __name__ == "__main__":
    seed()
