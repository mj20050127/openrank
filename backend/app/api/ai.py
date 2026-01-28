"""AI service API endpoints."""

from fastapi import APIRouter
from app.services.ai_service.report_router import router as ai_report_router


router = APIRouter(prefix="/ai", tags=["ai"])

# Include AI report routes
router.include_router(ai_report_router, prefix="/report")

# Root endpoint for AI service
@router.get("/", status_code=200)
def ai_service_root():
    """AI service root endpoint.

    Returns:
        AI service status
    """
    return {
        "message": "AI Service API",
        "endpoints": {
            "health_report": "/ai/report/health",
            "newcomer_report": "/ai/report/newcomer",
            "trend_report": "/ai/report/trend",
            "cache_stats": "/ai/report/cache-stats",
            "clear_cache": "/ai/report/clear-cache"
        }
    }
