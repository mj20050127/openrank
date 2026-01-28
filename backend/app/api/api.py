from fastapi import APIRouter
from app.api import (
    health, 
    metrics, 
    dataease, 
    chat, 
    forecast,  # 预测模块
    monitor,   # 监控模块
    portfolio, # 项目组合模块
    iot_api,   # 你刚创建的 IoTDB 适配器
    newcomer,
    trends,    # 趋势分析模块
)

api_router = APIRouter()

# 基础与核心分析
api_router.include_router(health.router)
api_router.include_router(metrics.router)

# DataEase 适配与 IoTDB 导出
api_router.include_router(dataease.router)
api_router.include_router(iot_api.router, prefix="/iotdb", tags=["IoTDB"])

# AI Agent 交互
api_router.include_router(chat.router)

# 扩展功能（Predict & Monitor 模式）
api_router.include_router(forecast.router)
api_router.include_router(monitor.router)
api_router.include_router(portfolio.router)
api_router.include_router(newcomer.router)
api_router.include_router(trends.router)