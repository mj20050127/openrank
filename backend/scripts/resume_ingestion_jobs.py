from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.init_db import init_db
from app.services.monthly_ingestion import resume_pending_jobs

if __name__ == "__main__":
    init_db()
    print({"resumed": resume_pending_jobs(limit=1000)})