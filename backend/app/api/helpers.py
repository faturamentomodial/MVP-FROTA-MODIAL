from app.models import Driver, Occurrence, Trip


def driver_dict(driver: Driver) -> dict:
    return {
        "id": driver.id,
        "nome": driver.nome,
        "cpf": driver.cpf,
        "telefone": driver.telefone,
        "user_id": driver.user_id,
        "ativo": driver.ativo,
        "created_at": driver.created_at,
        "updated_at": driver.updated_at,
        "email": driver.user.email if driver.user else None,
    }


def trip_dict(trip: Trip) -> dict:
    return {
        "delivery_revision": trip.delivery_revision,
        "id": trip.id,
        "driver_id": trip.driver_id,
        "vehicle_id": trip.vehicle_id,
        "data_saida": trip.data_saida,
        "km_inicial": trip.km_inicial,
        "data_retorno": trip.data_retorno,
        "km_final": trip.km_final,
        "km_percorrido": trip.km_percorrido,
        "status": trip.status,
        "observacao": trip.observacao,
        "created_at": trip.created_at,
        "updated_at": trip.updated_at,
        "driver_name": trip.driver.nome if trip.driver else None,
        "vehicle_plate": trip.vehicle.placa if trip.vehicle else None,
        "checklist_id": trip.checklist.id if trip.checklist else None,
        "occurrence_count": len(trip.occurrences) if trip.occurrences is not None else 0,
        "notas": trip.invoices,
        "total_volumes": sum(invoice.volumes for invoice in trip.invoices),
    }


def occurrence_dict(item: Occurrence) -> dict:
    return {
        "invoice_id": item.invoice_id,
        "id": item.id,
        "trip_id": item.trip_id,
        "driver_id": item.driver_id,
        "vehicle_id": item.vehicle_id,
        "tipo": item.tipo,
        "descricao": item.descricao,
        "data_hora": item.data_hora,
        "local": item.local,
        "status": item.status,
        "observacao_gestor": item.observacao_gestor,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
        "driver_name": item.driver.nome if item.driver else None,
        "vehicle_plate": item.vehicle.placa if item.vehicle else None,
    }
