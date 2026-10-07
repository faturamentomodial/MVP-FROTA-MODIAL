from fastapi import APIRouter

from app.api import auth, checklists, dashboard, drivers, occurrences, trips, users, vehicles


api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(drivers.router)
api_router.include_router(vehicles.router)
api_router.include_router(trips.router)
api_router.include_router(checklists.router)
api_router.include_router(occurrences.router)
api_router.include_router(dashboard.router)
