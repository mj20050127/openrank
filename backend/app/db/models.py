from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    Text,
    Date,
    Float,
    Boolean,
    TIMESTAMP,
    func,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.db.base import Base

JSONType = JSON().with_variant(JSONB, "postgresql")


class HealthOverviewDaily(Base):
    __tablename__ = "health_overview_daily"
    __table_args__ = (
        UniqueConstraint("repo_full_name", "dt", name="uq_health_overview_dt"),
        {"schema": "openrank"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo_full_name = Column(Text, nullable=False, index=True)
    dt = Column(Date, nullable=False, index=True)

    score_health = Column(Float)
    score_vitality = Column(Float)
    score_responsiveness = Column(Float)
    score_resilience = Column(Float)
    score_governance = Column(Float)
    score_security = Column(Float)

    score_vitality_influence = Column(Float)
    score_vitality_momentum = Column(Float)
    score_vitality_community = Column(Float)
    score_vitality_growth = Column(Float)

    score_resp_first = Column(Float)
    score_resp_close = Column(Float)
    score_resp_backlog = Column(Float)

    score_res_bf = Column(Float)
    score_res_diversity = Column(Float)
    score_res_retention = Column(Float)

    score_gov_files = Column(Float)
    score_gov_process = Column(Float)
    score_gov_transparency = Column(Float)

    score_sec_base = Column(Float)
    score_sec_critical = Column(Float)
    score_sec_bonus = Column(Float)

    metric_openrank = Column(Float)
    metric_activity = Column(Float)
    metric_attention = Column(Float)
    metric_technical_fork = Column(Float)
    metric_community_openrank = Column(Float)
    metric_participants = Column(Float)
    metric_new_contributors = Column(Float)
    metric_activity_3m = Column(Float)
    metric_activity_prev_3m = Column(Float)
    metric_activity_growth = Column(Float)
    metric_active_months_12m = Column(Float)

    metric_change_requests = Column(Float)
    metric_change_requests_accepted = Column(Float)
    metric_change_requests_reviews = Column(Float)
    metric_change_request_response_time = Column(Float)
    metric_change_request_resolution_duration = Column(Float)
    metric_change_request_age = Column(Float)
    metric_code_change_lines_add = Column(Float)
    metric_code_change_lines_remove = Column(Float)
    metric_code_change_lines_sum = Column(Float)
    metric_code_change_lines = Column(Float)
    metric_issue_response_time = Column(Float)
    metric_issue_resolution_duration = Column(Float)
    metric_issue_age = Column(Float)
    metric_issues_closed = Column(Float)
    metric_active_dates_and_times = Column(JSONType)
    metric_activity_details = Column(JSONType)
    metric_contributors = Column(Float)
    metric_contributors_detail = Column(JSONType)
    metric_stars = Column(Float)

    metric_issue_response_time_h = Column(Float)
    metric_issue_resolution_duration_h = Column(Float)
    metric_issue_age_h = Column(Float)
    metric_issues_new = Column(Float)
    metric_pr_response_time_h = Column(Float)
    metric_pr_resolution_duration_h = Column(Float)
    metric_pr_age_h = Column(Float)
    metric_prs_new = Column(Float)

    metric_bus_factor = Column(Float)
    metric_hhi = Column(Float)
    metric_top1_share = Column(Float)
    metric_inactive_contributors = Column(Float)
    metric_retention_rate = Column(Float)

    metric_governance_files = Column(JSONType)
    metric_github_health_percentage = Column(Float)

    metric_scorecard_score = Column(Float)
    metric_scorecard_checks = Column(JSONType)
    metric_security_defaulted = Column(Boolean, default=False)

    raw_payloads = Column(JSONType)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

class MetricPoint(Base):
    __tablename__ = "metric_points"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, index=True)
    metric = Column(Text, nullable=False, index=True)
    dt = Column(Date, nullable=False, index=True)
    value = Column(Float)
    source = Column(Text, default="opendigger")
    updated_at = Column(TIMESTAMP, server_default=func.now())

class RepoSnapshot(Base):
    __tablename__ = "repo_snapshots"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, index=True)
    window_days = Column(Integer, nullable=False)
    snapshot_json = Column(JSONType, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, index=True)
    mode = Column(Text, nullable=False)
    query = Column(Text, nullable=False)
    payload_json = Column(JSONType, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

class WatchList(Base):
    __tablename__ = "watchlist"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, unique=True, index=True)
    rules_json = Column(JSONType, nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, index=True)
    metric = Column(Text, nullable=False, index=True)
    level = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    evidence_json = Column(JSONType)
    created_at = Column(TIMESTAMP, server_default=func.now())

from app.models import RepoCatalog, RepoDoc, RepoIssue


class DataEaseBinding(Base):
    __tablename__ = "dataease_bindings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, unique=True, index=True)
    data_source_id = Column(Text, nullable=False)
    dataset_ids = Column(JSONType, nullable=False)
    screen_id = Column(Text, nullable=False)
    embed_url = Column(Text, nullable=False)
    raw_json = Column(JSONType)
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
