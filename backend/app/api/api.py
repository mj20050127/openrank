from fastapi import APIRouter
from app.api import (
    health, 
    metrics, 
    newcomer,
    trends,    # 趋势分析模块
    repositories,
    monthly_health,
    current_health,
    monthly_history,
)

api_router = APIRouter()

# 基础与核心分析
api_router.include_router(health.router)
api_router.include_router(metrics.router)

# Extension routes
api_router.include_router(newcomer.router)
api_router.include_router(trends.router)
api_router.include_router(repositories.router)
api_router.include_router(monthly_health.router)
api_router.include_router(current_health.router)
api_router.include_router(monthly_history.router)