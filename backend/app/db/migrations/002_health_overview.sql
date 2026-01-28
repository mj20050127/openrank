CREATE SCHEMA IF NOT EXISTS openrank;

CREATE TABLE IF NOT EXISTS openrank.health_overview_daily (
    id SERIAL PRIMARY KEY,
    repo_full_name TEXT NOT NULL,
    dt DATE NOT NULL,

    score_health DOUBLE PRECISION,
    score_vitality DOUBLE PRECISION,
    score_responsiveness DOUBLE PRECISION,
    score_resilience DOUBLE PRECISION,
    score_governance DOUBLE PRECISION,
    score_security DOUBLE PRECISION,

    score_vitality_influence DOUBLE PRECISION,
    score_vitality_momentum DOUBLE PRECISION,
    score_vitality_community DOUBLE PRECISION,
    score_vitality_growth DOUBLE PRECISION,

    score_resp_first DOUBLE PRECISION,
    score_resp_close DOUBLE PRECISION,
    score_resp_backlog DOUBLE PRECISION,

    score_res_bf DOUBLE PRECISION,
    score_res_diversity DOUBLE PRECISION,
    score_res_retention DOUBLE PRECISION,

    score_gov_files DOUBLE PRECISION,
    score_gov_process DOUBLE PRECISION,
    score_gov_transparency DOUBLE PRECISION,

    score_sec_base DOUBLE PRECISION,
    score_sec_critical DOUBLE PRECISION,
    score_sec_bonus DOUBLE PRECISION,

    metric_openrank DOUBLE PRECISION,
    metric_activity DOUBLE PRECISION,
    metric_participants DOUBLE PRECISION,
    metric_new_contributors DOUBLE PRECISION,
    metric_activity_3m DOUBLE PRECISION,
    metric_activity_prev_3m DOUBLE PRECISION,
    metric_activity_growth DOUBLE PRECISION,
    metric_active_months_12m DOUBLE PRECISION,

    metric_issue_response_time_h DOUBLE PRECISION,
    metric_issue_resolution_duration_h DOUBLE PRECISION,
    metric_issue_age_h DOUBLE PRECISION,
    metric_issues_new DOUBLE PRECISION,
    metric_pr_response_time_h DOUBLE PRECISION,
    metric_pr_resolution_duration_h DOUBLE PRECISION,
    metric_pr_age_h DOUBLE PRECISION,
    metric_prs_new DOUBLE PRECISION,

    metric_bus_factor DOUBLE PRECISION,
    metric_hhi DOUBLE PRECISION,
    metric_top1_share DOUBLE PRECISION,
    metric_inactive_contributors DOUBLE PRECISION,
    metric_retention_rate DOUBLE PRECISION,

    metric_governance_files JSONB,
    metric_github_health_percentage DOUBLE PRECISION,

    metric_scorecard_score DOUBLE PRECISION,
    metric_scorecard_checks JSONB,
    metric_security_defaulted BOOLEAN DEFAULT FALSE,

    raw_payloads JSONB,
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_health_overview_dt UNIQUE (repo_full_name, dt)
);

CREATE INDEX IF NOT EXISTS idx_health_overview_repo ON openrank.health_overview_daily (repo_full_name);
CREATE INDEX IF NOT EXISTS idx_health_overview_dt ON openrank.health_overview_daily (dt);

CREATE OR REPLACE VIEW openrank.health_overview_latest AS
SELECT DISTINCT ON (repo_full_name)
    *
FROM openrank.health_overview_daily
ORDER BY repo_full_name, dt DESC;
