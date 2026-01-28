from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.db.models import MetricPoint


def parse_range_days(range_value: str) -> int:
    if not range_value:
        raise ValueError("range is required")
    if range_value.endswith("d") and range_value[:-1].isdigit():
        days = int(range_value[:-1])
        if days <= 0:
            raise ValueError("range must be positive")
        return days
    raise ValueError("range must be like '30d'")


def get_batch_trend(repos: list[str], metric: str, range_value: str, db: Session) -> dict:
    days = parse_range_days(range_value)
    end_dt = date.today()
    start_dt = end_dt - timedelta(days=days - 1)
    rows = (
        db.query(MetricPoint)
        .filter(
            MetricPoint.repo.in_(repos),
            MetricPoint.metric == metric,
            MetricPoint.dt >= start_dt,
            MetricPoint.dt <= end_dt,
        )
        .order_by(MetricPoint.repo.asc(), MetricPoint.dt.asc())
        .all()
    )
    series_map: dict[str, list[dict]] = {repo: [] for repo in repos}
    for row in rows:
        series_map.setdefault(row.repo, []).append({"dt": row.dt.isoformat(), "value": row.value})
    series = [{"repo": repo, "points": series_map.get(repo, [])} for repo in repos]
    return {
        "metric": metric,
        "range": {"start": start_dt.isoformat(), "end": end_dt.isoformat(), "days": days},
        "series": series,
    }
