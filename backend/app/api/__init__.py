"""API endpoints for the application."""

from fastapi import APIRouter
from app.api import (
    agent,
    ai,
    api,
    chat,
    dataease,
    forecast,
    graph,
    health,
    health_overview,
    iot_api,
    metrics,
    monitor,
    newcomer,
    portfolio,
    risk_viability,
    trends
)


router = APIRouter()

# Include all routers
router.include_router(agent.router)
router.include_router(ai.router)
router.include_router(api.api_router)
router.include_router(chat.router)
router.include_router(dataease.router)
router.include_router(forecast.router)
router.include_router(graph.router)
router.include_router(health.router)
router.include_router(health_overview.router)
router.include_router(iot_api.router)
router.include_router(metrics.router)
router.include_router(monitor.router)
router.include_router(newcomer.router)
router.include_router(portfolio.router)
router.include_router(risk_viability.router)
router.include_router(trends.router)
