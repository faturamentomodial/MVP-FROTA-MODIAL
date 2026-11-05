from fastapi import APIRouter

from app.api import auth, checklists, dashboard, drivers, occurrences, trips, users, vehicles, tracking


api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(drivers.router)
api_router.include_router(vehicles.router)
api_router.include_router(trips.router)
api_router.include_router(checklists.router)
api_router.include_router(occurrences.router)
api_router.include_router(dashboard.router)

api_router.include_router(tracking.router)

from app.api import route_plans
api_router.include_router(route_plans.router)

from app.api import tasks
api_router.include_router(tasks.router)

from app.api import pickups
api_router.include_router(pickups.router)

from app.api import route_templates
api_router.include_router(route_templates.router)
