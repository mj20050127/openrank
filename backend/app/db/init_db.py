from sqlalchemy import text
from app.db.base import engine, Base
from app.db import models  # noqa: F401

def init_db():
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS openrank"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE OR REPLACE VIEW openrank.health_overview_latest AS
                SELECT DISTINCT ON (repo_full_name)
                    *
                FROM openrank.health_overview_daily
                ORDER BY repo_full_name, dt DESC;
                """
            )
        )
