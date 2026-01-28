from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.db.models import HealthOverviewDaily


@dataclass
class HealthOverviewRecord:
    repo_full_name: str
    dt: date

    score_health: Optional[float] = None
    score_vitality: Optional[float] = None
    score_responsiveness: Optional[float] = None
    score_resilience: Optional[float] = None
    score_governance: Optional[float] = None
    score_security: Optional[float] = None

    score_vitality_influence: Optional[float] = None
    score_vitality_momentum: Optional[float] = None
    score_vitality_community: Optional[float] = None
    score_vitality_growth: Optional[float] = None

    score_resp_first: Optional[float] = None
    score_resp_close: Optional[float] = None
    score_resp_backlog: Optional[float] = None

    score_res_bf: Optional[float] = None
    score_res_diversity: Optional[float] = None
    score_res_retention: Optional[float] = None

    score_gov_files: Optional[float] = None
    score_gov_process: Optional[float] = None
    score_gov_transparency: Optional[float] = None

    score_sec_base: Optional[float] = None
    score_sec_critical: Optional[float] = None
    score_sec_bonus: Optional[float] = None

    metric_openrank: Optional[float] = None
    metric_activity: Optional[float] = None
    metric_attention: Optional[float] = None
    metric_technical_fork: Optional[float] = None
    metric_community_openrank: Optional[float] = None
    metric_participants: Optional[float] = None
    metric_new_contributors: Optional[float] = None
    metric_activity_3m: Optional[float] = None
    metric_activity_prev_3m: Optional[float] = None
    metric_activity_growth: Optional[float] = None
    metric_active_months_12m: Optional[float] = None

    metric_change_requests: Optional[float] = None
    metric_change_requests_accepted: Optional[float] = None
    metric_change_requests_reviews: Optional[float] = None
    metric_change_request_response_time: Optional[float] = None
    metric_change_request_resolution_duration: Optional[float] = None
    metric_change_request_age: Optional[float] = None
    metric_code_change_lines_add: Optional[float] = None
    metric_code_change_lines_remove: Optional[float] = None
    metric_code_change_lines_sum: Optional[float] = None
    metric_code_change_lines: Optional[float] = None
    metric_issue_response_time: Optional[float] = None
    metric_issue_resolution_duration: Optional[float] = None
    metric_issue_age: Optional[float] = None
    metric_issues_closed: Optional[float] = None
    metric_active_dates_and_times: Optional[Dict[str, Any]] = field(default_factory=dict)
    metric_activity_details: Optional[Dict[str, Any]] = field(default_factory=dict)
    metric_contributors: Optional[float] = None
    metric_contributors_detail: Optional[Dict[str, Any]] = field(default_factory=dict)
    metric_stars: Optional[float] = None
    metric_stars_growth: Optional[float] = None
    metric_stars_growth_rate: Optional[float] = None

    metric_issue_response_time_h: Optional[float] = None
    metric_issue_resolution_duration_h: Optional[float] = None
    metric_issue_age_h: Optional[float] = None
    metric_issues_new: Optional[float] = None
    metric_pr_response_time_h: Optional[float] = None
    metric_pr_resolution_duration_h: Optional[float] = None
    metric_pr_age_h: Optional[float] = None
    metric_prs_new: Optional[float] = None

    metric_bus_factor: Optional[float] = None
    metric_hhi: Optional[float] = None
    metric_top1_share: Optional[float] = None
    metric_inactive_contributors: Optional[float] = None
    metric_retention_rate: Optional[float] = None

    metric_governance_files: Optional[Dict[str, Any]] = field(default_factory=dict)
    metric_github_health_percentage: Optional[float] = None

    metric_scorecard_score: Optional[float] = None
    metric_scorecard_checks: Optional[Dict[str, Any]] = field(default_factory=dict)
    metric_security_defaulted: bool = False

    raw_payloads: Optional[Dict[str, Any]] = field(default_factory=dict)

    def asdict(self) -> Dict[str, Any]:
        return asdict(self)


class MetricEngine:
    """Implements the five-dimension health scoring defined in the delivery plan."""

    def __init__(self, eps: float = 1e-6):
        self.eps = eps

    @staticmethod
    def _clamp(value: Optional[float], lower: float = 0.0, upper: float = 100.0) -> Optional[float]:
        if value is None or math.isnan(value):
            return None
        return max(lower, min(upper, value))

    @staticmethod
    def _safe(value: Optional[float]) -> float:
        return float(value) if value is not None else 0.0

    def _log_score(self, value: Optional[float]) -> Optional[float]:
        if value is None or value <= 0:
            return None
        return self._clamp(18 * math.log(1 + value))

    def _growth_score(self, current: Optional[float], previous: Optional[float]) -> Optional[float]:
        if current is None or previous is None:
            return None
        growth = (current - previous) / max(1.0, previous)
        growth = max(-1.0, min(2.0, growth))
        return self._clamp(100 * (growth + 1) / 3)

    def _time_score(self, hours: Optional[float], good: float, bad: float) -> Optional[float]:
        if hours is None:
            return None
        if hours <= good:
            return 100.0
        if hours >= bad:
            return 0.0
        return self._clamp(100 * (bad - hours) / (bad - good))

    def _weighted_avg(self, scores: list[Optional[float]], weights: list[float]) -> Optional[float]:
        total_w = sum(weights)
        if total_w <= 0:
            return None
        acc = 0.0
        eff_weight = 0.0
        for score, w in zip(scores, weights):
            if score is None:
                continue
            acc += score * w
            eff_weight += w
        if eff_weight == 0:
            return None
        return acc / eff_weight

    def _coverage_score(self, files: Dict[str, Any]) -> float:
        if not files:
            return 0.0
        normalized = {k.lower(): bool(v) for k, v in files.items()}
        keys = [
            "readme",
            "license",
            "contributing",
            "code_of_conduct",
            "security",
            "issue_template",
            "pull_request_template",
        ]
        hits = sum(1 for k in keys if normalized.get(k))
        return 100.0 * hits / len(keys)

    def _transparency_bonus(self, files: Dict[str, Any]) -> float:
        normalized = {k.lower(): bool(v) for k, v in files.items()} if files else {}
        has_core = all(normalized.get(k) for k in ["readme", "license", "contributing"])
        has_templates = normalized.get("issue_template") or normalized.get("pull_request_template")
        if has_core and has_templates:
            return 100.0
        return self._coverage_score(normalized)

    def _critical_security_score(self, checks: Dict[str, Any]) -> Optional[float]:
        if not checks:
            return None
        scores: list[float] = []
        for value in checks.values():
            if isinstance(value, dict) and "score" in value:
                try:
                    scores.append(float(value.get("score", 0)) * 10)
                except Exception:
                    continue
            else:
                try:
                    scores.append(float(value) * 10)
                except Exception:
                    continue
        if not scores:
            return None
        return self._clamp(sum(scores) / len(scores))

    # 将原有的 compute 方法替换为以下内容：
    # [兼容修复版] 请替换 metric_engine.py 中的 compute 方法
    def compute(self, metrics: Dict[str, Any], dt_value: Any = None, **kwargs: Any) -> Dict[str, Any]:
        """
        [全能兼容版] 
        - 适配 health_pipeline (只传 metrics 字典)
        - 适配 API 接口 (可能会传 repo_full_name 关键字参数)
        """
        
        # 1. 智能提取 repo_full_name
        # 优先看有没有直接传参 (API 调用)，其次看字典里有没有 (Pipeline 调用)
        repo_full_name = kwargs.get("repo_full_name") or metrics.get("repo_full_name", "unknown")
        
        # 2. 智能提取时间 dt
        actual_dt = kwargs.get("dt") or metrics.get("dt", dt_value)

        # 3. 定义智能取值函数 m() (保持不变)
        def m(key: str) -> Optional[float]:
            val = metrics.get(key)
            if val is not None:
                try: return float(val)
                except: pass
            
            if not key.startswith("metric_"):
                val = metrics.get(f"metric_{key}")
                if val is not None:
                    try: return float(val)
                    except: pass
            return None

        # 4. 初始化记录对象
        rec = HealthOverviewRecord(repo_full_name=repo_full_name, dt=actual_dt)

        # --- 以下逻辑保持完全不变，直接照搬即可 ---
        
        # 基础指标映射
        rec.metric_openrank = m("openrank")
        rec.metric_activity = m("activity")
        rec.metric_attention = m("attention")
        rec.metric_technical_fork = m("technical_fork")
        rec.metric_community_openrank = m("community_openrank")
        rec.metric_participants = m("participants_3m") or m("participants") or m("metric_participants")
        rec.metric_new_contributors = m("new_contributors_3m") or m("new_contributors") or m("metric_new_contributors")
        rec.metric_activity_3m = m("activity_3m")
        rec.metric_activity_prev_3m = m("activity_prev_3m")
        rec.metric_active_months_12m = m("active_months_12m")

        rec.metric_change_requests = m("change_requests")
        rec.metric_change_requests_accepted = m("change_requests_accepted")
        rec.metric_change_requests_reviews = m("change_requests_reviews")
        rec.metric_change_request_response_time = m("change_request_response_time")
        rec.metric_change_request_resolution_duration = m("change_request_resolution_duration")
        rec.metric_change_request_age = m("change_request_age")

        rec.metric_code_change_lines_add = m("code_change_lines_add")
        rec.metric_code_change_lines_remove = m("code_change_lines_remove")
        rec.metric_code_change_lines_sum = m("code_change_lines_sum")
        rec.metric_code_change_lines = m("code_change_lines")

        rec.metric_issue_response_time = m("issue_response_time")
        rec.metric_issue_resolution_duration = m("issue_resolution_duration")
        rec.metric_issue_age = m("issue_age")
        rec.metric_issues_closed = m("issues_closed")

        rec.metric_active_dates_and_times = metrics.get("metric_active_dates_and_times") or metrics.get("active_dates_and_times")
        rec.metric_activity_details = metrics.get("metric_activity_details") or metrics.get("activity_details")
        rec.metric_contributors = m("contributors")
        rec.metric_contributors_detail = metrics.get("metric_contributors_detail") or metrics.get("contributors_detail") or {}
        rec.metric_stars = m("stars")
        rec.metric_stars_growth = m("stars_growth") or metrics.get("metric_stars_growth")
        rec.metric_stars_growth_rate = m("stars_growth_rate") or metrics.get("metric_stars_growth_rate")

        # 增长分
        rec.metric_activity_growth = self._growth_score(rec.metric_activity_3m, rec.metric_activity_prev_3m)

        # [维度1] Vitality
        rec.score_vitality_influence = self._log_score(rec.metric_openrank)
        rec.score_vitality_momentum = self._log_score(rec.metric_activity_3m)
        rec.score_vitality_community = None
        
        part_score = self._log_score(rec.metric_participants)
        new_score = self._log_score(rec.metric_new_contributors)
        
        if part_score is not None or new_score is not None:
             rec.score_vitality_community = 0.7 * self._safe(part_score) + 0.3 * self._safe(new_score)

        sustain_score = None
        if rec.metric_active_months_12m is not None:
            sustain_score = self._clamp(100 * rec.metric_active_months_12m / 12)
        
        growth_score = rec.metric_activity_growth
        
        if growth_score is not None or sustain_score is not None:
            rec.score_vitality_growth = (
                0.6 * self._safe(growth_score) + 0.4 * self._safe(sustain_score)
            )
            
        rec.score_vitality = self._weighted_avg(
            [rec.score_vitality_influence, rec.score_vitality_momentum, rec.score_vitality_community, rec.score_vitality_growth],
            [0.30, 0.40, 0.20, 0.10],
        )

        # 响应指标
        rec.metric_issue_response_time_h = m("issue_response_time_h")
        rec.metric_issue_resolution_duration_h = m("issue_resolution_duration_h")
        rec.metric_issue_age_h = m("issue_age_h")
        rec.metric_issues_new = m("issues_new")
        
        rec.metric_pr_response_time_h = m("pr_response_time_h") or m("change_request_response_time_h")
        rec.metric_pr_resolution_duration_h = m("pr_resolution_duration_h") or m("change_request_resolution_duration_h")
        rec.metric_pr_age_h = m("pr_age_h") or m("change_request_age_h")
        rec.metric_prs_new = m("prs_new") or m("change_requests_new")

        # [维度2] Responsiveness
        issue_first = self._time_score(rec.metric_issue_response_time_h, good=24, bad=168)
        pr_first = self._time_score(rec.metric_pr_response_time_h, good=12, bad=120)
        issue_close = self._time_score(rec.metric_issue_resolution_duration_h, good=72, bad=720)
        pr_close = self._time_score(rec.metric_pr_resolution_duration_h, good=48, bad=720)
        issue_age = self._time_score(rec.metric_issue_age_h, good=168, bad=2160)
        pr_age = self._time_score(rec.metric_pr_age_h, good=168, bad=2160)

        w_i = math.log1p(self._safe(rec.metric_issues_new))
        w_p = math.log1p(self._safe(rec.metric_prs_new))
        
        rec.score_resp_first = self._weighted_avg([issue_first, pr_first], [w_i, w_p])
        rec.score_resp_close = self._weighted_avg([issue_close, pr_close], [w_i, w_p])
        rec.score_resp_backlog = self._weighted_avg([issue_age, pr_age], [w_i, w_p])
        
        rec.score_responsiveness = self._weighted_avg(
            [rec.score_resp_first, rec.score_resp_close, rec.score_resp_backlog], [0.45, 0.35, 0.20]
        )
        if rec.score_responsiveness is None and self._safe(rec.metric_activity) > 0:
             rec.score_responsiveness = 50.0

        # [维度3] Resilience
        rec.metric_bus_factor = m("bus_factor")
        rec.metric_hhi = m("hhi")
        rec.metric_top1_share = m("top1_share")
        rec.metric_inactive_contributors = m("inactive_contributors")
        rec.metric_retention_rate = m("retention_rate")

        rec.score_res_bf = self._clamp(self._safe(rec.metric_bus_factor) * 20)
        
        diversity_source = rec.metric_hhi if rec.metric_hhi is not None else rec.metric_top1_share
        if diversity_source is not None:
            rec.score_res_diversity = self._clamp(100 * (1 - diversity_source))
            
        participants = self._safe(rec.metric_participants)
        if rec.metric_retention_rate is not None:
            rec.score_res_retention = self._clamp(100 * rec.metric_retention_rate)
        elif participants > 0:
            retention = 1 - self._safe(rec.metric_inactive_contributors) / max(1.0, participants)
            rec.score_res_retention = self._clamp(100 * retention)
            
        rec.score_resilience = self._weighted_avg(
            [rec.score_res_bf, rec.score_res_diversity, rec.score_res_retention], [0.45, 0.35, 0.20]
        )

        # [维度4] Governance
        governance_files = metrics.get("metric_governance_files") or metrics.get("governance_files") or {}
        rec.metric_governance_files = governance_files
        
        rec.metric_github_health_percentage = m("github_health_percentage")
        rec.score_gov_files = self._clamp(rec.metric_github_health_percentage)
        
        rec.score_gov_process = None
        if rec.score_resp_first is not None or rec.score_resp_close is not None:
            rec.score_gov_process = 0.6 * self._safe(rec.score_resp_first) + 0.4 * self._safe(rec.score_resp_close)
            
        rec.score_gov_transparency = self._transparency_bonus(governance_files)
        rec.score_governance = self._weighted_avg(
            [rec.score_gov_files, rec.score_gov_process, rec.score_gov_transparency], [0.45, 0.35, 0.20]
        )
        if rec.score_governance is None:
             rec.score_governance = self._clamp(self._safe(rec.score_vitality) * 0.8 + 20)

        # [维度5] Security
        rec.metric_scorecard_score = m("scorecard_score")
        rec.metric_scorecard_checks = metrics.get("metric_scorecard_checks") or metrics.get("scorecard_checks") or {}
        rec.metric_security_defaulted = bool(metrics.get("metric_security_defaulted") or False)
        
        if rec.metric_security_defaulted:
            rec.score_security = 50.0
            rec.score_sec_base = 50.0
            rec.score_sec_critical = None
            rec.score_sec_bonus = 0.0
        else:
            rec.score_sec_base = self._clamp(self._safe(rec.metric_scorecard_score) * 10)
            rec.score_sec_critical = self._critical_security_score(rec.metric_scorecard_checks)
            rec.score_sec_bonus = 10.0 
            rec.score_security = self._weighted_avg(
                [rec.score_sec_base, rec.score_sec_critical, rec.score_sec_bonus], [0.7, 0.2, 0.1]
            )
        
        if rec.score_security is None:
             rec.score_security = 60.0

        # [总分] Health
        rec.score_health = self._weighted_avg(
            [rec.score_vitality, rec.score_responsiveness, rec.score_resilience, rec.score_governance, rec.score_security],
            [0.30, 0.25, 0.20, 0.15, 0.10],
        )

        rec.raw_payloads = metrics.get("raw_payloads") or {}
        
        return rec.asdict()
    # 替换 upsert 方法
    def upsert(self, db: Session, record: Any) -> HealthOverviewDaily:
        """
        [兼容修复版] 支持 HealthOverviewRecord 对象或 Dict 字典
        """
        # 1. 判断输入类型并统一取值方式
        if isinstance(record, dict):
            # 如果是字典 (Pipeline 或 新版 compute 返回的)
            payload = record
            r_name = payload.get("repo_full_name")
            r_dt = payload.get("dt")
        else:
            # 如果是对象 (旧版逻辑)
            payload = record.asdict()
            r_name = record.repo_full_name
            r_dt = record.dt

        # 2. 查询是否存在
        existing = (
            db.query(HealthOverviewDaily)
            .filter(
                HealthOverviewDaily.repo_full_name == r_name,
                HealthOverviewDaily.dt == r_dt,
            )
            .first()
        )

        # 3. 执行更新或插入
        if existing:
            # 更新逻辑
            for key, value in payload.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing
        
        # 插入逻辑：过滤掉模型里没有的字段（防止报错）
        valid_keys = {c.name for c in HealthOverviewDaily.__table__.columns}
        clean_payload = {k: v for k, v in payload.items() if k in valid_keys}

        new_row = HealthOverviewDaily(**clean_payload)
        db.add(new_row)
        db.commit()
        db.refresh(new_row)
        return new_row

    @staticmethod
    def serialize(model: HealthOverviewDaily) -> Dict[str, Any]:
        data = {c.name: getattr(model, c.name) for c in model.__table__.columns}
        if isinstance(data.get("dt"), (date, datetime)):
            data["dt"] = data["dt"].isoformat()
        if isinstance(data.get("updated_at"), datetime):
            data["updated_at"] = data["updated_at"].isoformat()
        return data
