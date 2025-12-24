from fastapi import FastAPI
from app.core.logging import setup_logging
from app.db.init_db import init_db
from fastapi.staticfiles import StaticFiles
from app.api.health import router as health_router
from app.api.chat import router as chat_router
from app.api.metrics import router as metrics_router
from app.api.forecast import router as forecast_router
from app.api.monitor import router as monitor_router
from app.api.dataease import router as dataease_router
from app.api.portfolio import router as portfolio_router
from app.api.graph import router as graph_router
from fastapi.middleware.cors import CORSMiddleware

setup_logging()
app = FastAPI(title="OpenSODA OSS Copilot")
app.add_middleware(
  CORSMiddleware,
  allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

@app.on_event("startup")
def _startup():
    init_db()

app.include_router(health_router)
app.include_router(chat_router)
app.include_router(metrics_router)
app.include_router(forecast_router)
app.include_router(monitor_router)
app.include_router(portfolio_router)
app.include_router(graph_router)
app.include_router(dataease_router)
