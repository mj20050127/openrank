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
    __table_args__ = (
        UniqueConstraint("repo", "metric", "dt", name="uq_metric_points_repo_metric_dt"),
        Index("ix_metric_points_repo_dt", "repo", "dt"),
    )
    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, index=True)
    metric = Column(Text, nullable=False, index=True)
    dt = Column(Date, nullable=False, index=True)
    value = Column(Float)
    source = Column(Text, default="opendigger")
    updated_at = Column(TIMESTAMP, server_default=func.now())


class RepositoryDataStatus(Base):
    __tablename__ = "repository_data_status"
    __table_args__ = ({"schema": "openrank"},)

    repo = Column(Text, primary_key=True)
    scope = Column(Text, nullable=False, default="user", index=True)
    enabled = Column(Boolean, nullable=False, default=True)
    opendigger_supported = Column(Boolean)
    sync_status = Column(Text, nullable=False, default="pending", index=True)
    first_month = Column(Date)
    latest_month = Column(Date)
    metric_count = Column(Integer, nullable=False, default=0)
    month_count = Column(Integer, nullable=False, default=0)
    coverage_ratio = Column(Float)
    last_full_sync_at = Column(TIMESTAMP(timezone=True))
    last_monthly_sync_at = Column(TIMESTAMP(timezone=True))
    last_error = Column(Text)
    metadata_json = Column(JSONType)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RepositoryMetricStatus(Base):
    __tablename__ = "repository_metric_status"
    __table_args__ = (
        UniqueConstraint("repo", "metric", name="uq_repository_metric_status"),
        Index("ix_repository_metric_status_repo", "repo"),
        {"schema": "openrank"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False)
    metric = Column(Text, nullable=False)
    filename = Column(Text, nullable=False)
    source_status = Column(Text, nullable=False, default="pending")
    first_month = Column(Date)
    latest_month = Column(Date)
    source_key_count = Column(Integer, nullable=False, default=0)
    database_key_count = Column(Integer, nullable=False, default=0)
    missing_keys = Column(JSONType)
    extra_keys = Column(JSONType)
    source_digest = Column(Text)
    last_error = Column(Text)
    last_synced_at = Column(TIMESTAMP(timezone=True))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        Index("ix_ingestion_jobs_repo_created", "repo", "created_at"),
        {"schema": "openrank"},
    )

    id = Column(Text, primary_key=True)
    repo = Column(Text, nullable=False, index=True)
    job_type = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="queued", index=True)
    stage = Column(Text, nullable=False, default="queued")
    progress = Column(Float, nullable=False, default=0.0)
    current_metric = Column(Text)
    requested_by = Column(Text, nullable=False, default="user")
    attempts = Column(Integer, nullable=False, default=0)
    result_json = Column(JSONType)
    error = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(TIMESTAMP(timezone=True))
    finished_at = Column(TIMESTAMP(timezone=True))
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class CurrentRepoAssessment(Base):
    __tablename__ = "current_repo_assessments"
    __table_args__ = ({"schema": "openrank"},)

    repo = Column(Text, primary_key=True)
    score_version = Column(Text, nullable=False, default="current-v1")
    window_days = Column(Integer, nullable=False, default=90)
    score_vitality = Column(Float)
    score_responsiveness = Column(Float)
    score_resilience = Column(Float)
    score_governance = Column(Float)
    score_security = Column(Float)
    score_comprehensive = Column(Float)
    completeness = Column(Float, nullable=False, default=0.0)
    confidence = Column(Float, nullable=False, default=0.0)
    evidence_json = Column(JSONType)
    risks_json = Column(JSONType)
    source_times_json = Column(JSONType)
    source_status_json = Column(JSONType)
    observed_at = Column(TIMESTAMP(timezone=True), nullable=False)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=False)
    last_attempt_at = Column(TIMESTAMP(timezone=True))
    last_error = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class RepoMonthlyAudit(Base):
    __tablename__ = "repo_monthly_audits"
    __table_args__ = (
        UniqueConstraint("repo", "metric_month", name="uq_repo_monthly_audit"),
        Index("ix_repo_monthly_audit_month", "metric_month"),
        {"schema": "openrank"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, index=True)
    metric_month = Column(Date, nullable=False)
    governance_score = Column(Float)
    security_score = Column(Float)
    completeness = Column(Float, nullable=False, default=0.0)
    governance_evidence = Column(JSONType)
    security_evidence = Column(JSONType)
    status = Column(Text, nullable=False, default="complete")
    source = Column(Text, nullable=False, default="github_scorecard")
    observed_at = Column(TIMESTAMP(timezone=True), nullable=False)
    collected_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    error = Column(Text)


class RepoMonthlyAssessment(Base):
    __tablename__ = "repo_monthly_assessments"
    __table_args__ = (
        UniqueConstraint("repo", "metric_month", "score_version", name="uq_repo_monthly_assessment"),
        Index("ix_repo_monthly_assessment_month_version", "metric_month", "score_version"),
        {"schema": "openrank"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False, index=True)
    metric_month = Column(Date, nullable=False)
    score_version = Column(Text, nullable=False)
    score_vitality = Column(Float)
    score_responsiveness = Column(Float)
    score_resilience = Column(Float)
    score_community = Column(Float)
    score_governance = Column(Float)
    score_security = Column(Float)
    score_comprehensive = Column(Float)
    community_completeness = Column(Float, nullable=False, default=0.0)
    comprehensive_completeness = Column(Float, nullable=False, default=0.0)
    evidence_json = Column(JSONType)
    source_updated_at = Column(TIMESTAMP(timezone=True))
    computed_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

class RepoDailySnapshot(Base):
    __tablename__ = "repo_daily_snapshots"
    __table_args__ = (
        UniqueConstraint("repo", "observed_date", name="uq_repo_daily_snapshot_date"),
        Index("ix_repo_daily_snapshot_repo_date", "repo", "observed_date"),
        {"schema": "openrank"},
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    repo = Column(Text, nullable=False)
    observed_date = Column(Date, nullable=False)
    stars = Column(BigInteger)
    forks = Column(BigInteger)
    open_issues = Column(Integer)
    open_pull_requests = Column(Integer)
    pushed_at = Column(TIMESTAMP(timezone=True))
    status = Column(Text, nullable=False, default="ok")
    error = Column(Text)
    source = Column(Text, nullable=False, default="github_rest")
    source_updated_at = Column(TIMESTAMP(timezone=True))
    fetched_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

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
