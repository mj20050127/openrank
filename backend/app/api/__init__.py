"""API endpoints for the application."""

from fastapi import APIRouter
from app.api import (
    api,
    graph,
    health,
    health_overview,
    metrics,
    newcomer,
    trends
)


router = APIRouter()

# Include all routers
router.include_router(api.api_router)
router.include_router(graph.router)
router.include_router(health.router)
router.include_router(health_overview.router)
router.include_router(metrics.router)
router.include_router(newcomer.router)
router.include_router(trends.router)
