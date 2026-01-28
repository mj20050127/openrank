"""Health facts extractor from health_overview_daily."""

from typing import Dict, Any, List, Optional
from datetime import date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.db.models import HealthOverviewDaily


class HealthFactsExtractor:
    """Extract health facts from database."""

    def __init__(self, db: Session):
        """Initialize with database session.

        Args:
            db: Database session
        """
        self.db = db

    def extract_facts(self, repo_full_name: str, time_window_days: int = 30) -> Dict[str, Any]:
        """Extract health facts for a repository.

        Args:
            repo_full_name: Repository full name (owner/repo)
            time_window_days: Time window in days

        Returns:
            Facts about the repository's health
        """
        facts = {
            "repo_full_name": repo_full_name,
            "time_window_days": time_window_days,
            "used_dt": None,
            "score_health": None,
            "dimensions": {},
            "metrics": {},
            "data_quality": {
                "available_days": 0,
                "missing_fields": [],
                "warnings": []
            }
        }

        # Get the latest health data
        latest_data = self._get_latest_health_data(repo_full_name)
        if latest_data:
            facts["used_dt"] = latest_data.dt.isoformat()
            facts["score_health"] = latest_data.score_health
            
            # Extract dimension scores
            facts["dimensions"] = {
                "vitality": {
                    "score": latest_data.score_vitality,
                    "subscores": {
                        "influence": latest_data.score_vitality_influence,
                        "momentum": latest_data.score_vitality_momentum,
                        "community": latest_data.score_vitality_community,
                        "growth": latest_data.score_vitality_growth
                    }
                },
                "responsiveness": {
                    "score": latest_data.score_responsiveness,
                    "subscores": {
                        "first": latest_data.score_resp_first,
                        "close": latest_data.score_resp_close,
                        "backlog": latest_data.score_resp_backlog
                    }
                },
                "resilience": {
                    "score": latest_data.score_resilience,
                    "subscores": {
                        "bus_factor": latest_data.score_res_bf,
                        "diversity": latest_data.score_res_diversity,
                        "retention": latest_data.score_res_retention
                    }
                },
                "governance": {
                    "score": latest_data.score_governance,
                    "subscores": {
                        "files": latest_data.score_gov_files,
                        "process": latest_data.score_gov_process,
                        "transparency": latest_data.score_gov_transparency
                    }
                },
                "security": {
                    "score": latest_data.score_security,
                    "subscores": {
                        "base": latest_data.score_sec_base,
                        "critical": latest_data.score_sec_critical,
                        "bonus": latest_data.score_sec_bonus
                    }
                }
            }
            
            # Extract key metrics
            facts["metrics"] = {
                "vitality": {
                    "activity": latest_data.metric_activity,
                    "activity_3m": latest_data.metric_activity_3m,
                    "activity_growth": latest_data.metric_activity_growth,
                    "openrank": latest_data.metric_openrank,
                    "new_contributors": latest_data.metric_new_contributors,
                    "attention": latest_data.metric_attention
                },
                "responsiveness": {
                    "issue_response_time_h": latest_data.metric_issue_response_time_h,
                    "pr_response_time_h": latest_data.metric_pr_response_time_h,
                    "issue_resolution_duration_h": latest_data.metric_issue_resolution_duration_h,
                    "pr_resolution_duration_h": latest_data.metric_pr_resolution_duration_h,
                    "issue_age_h": latest_data.metric_issue_age_h,
                    "pr_age_h": latest_data.metric_pr_age_h,
                    "issues_new": latest_data.metric_issues_new,
                    "prs_new": latest_data.metric_prs_new
                },
                "resilience": {
                    "bus_factor": latest_data.metric_bus_factor,
                    "hhi": latest_data.metric_hhi,
                    "top1_share": latest_data.metric_top1_share,
                    "inactive_contributors": latest_data.metric_inactive_contributors,
                    "retention_rate": latest_data.metric_retention_rate
                },
                "governance_security": {
                    "scorecard_score": latest_data.metric_scorecard_score,
                    "github_health_percentage": latest_data.metric_github_health_percentage,
                    "governance_files": latest_data.metric_governance_files,
                    "scorecard_checks": latest_data.metric_scorecard_checks
                }
            }
            
            # Check for missing fields
            self._check_missing_fields(facts)
        else:
            facts["data_quality"]["warnings"].append(f"No health data found for repository: {repo_full_name}")

        # Get historical data for trend analysis
        historical_data = self._get_historical_health_data(repo_full_name, time_window_days)
        if historical_data:
            facts["historical_data"] = []
            for data in historical_data:
                facts["historical_data"].append({
                    "dt": data.dt.isoformat(),
                    "score_health": data.score_health,
                    "score_vitality": data.score_vitality,
                    "score_responsiveness": data.score_responsiveness,
                    "score_resilience": data.score_resilience,
                    "score_governance": data.score_governance,
                    "score_security": data.score_security
                })
            facts["data_quality"]["available_days"] = len(historical_data)
        else:
            facts["data_quality"]["warnings"].append(f"No historical health data found for the specified time window")

        # Get peer comparison data (optional)
        peer_data = self._get_peer_comparison(repo_full_name)
        if peer_data:
            facts["peer_comparison"] = peer_data

        return facts

    def _get_latest_health_data(self, repo_full_name: str) -> Optional[HealthOverviewDaily]:
        """Get the latest health data for a repository.

        Args:
            repo_full_name: Repository full name

        Returns:
            Latest health data or None
        """
        return self.db.query(HealthOverviewDaily).filter(
            HealthOverviewDaily.repo_full_name == repo_full_name
        ).order_by(desc(HealthOverviewDaily.dt)).first()

    def _get_historical_health_data(self, repo_full_name: str, days: int) -> List[HealthOverviewDaily]:
        """Get historical health data for a repository.

        Args:
            repo_full_name: Repository full name
            days: Number of days to look back

        Returns:
            List of historical health data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        return self.db.query(HealthOverviewDaily).filter(
            HealthOverviewDaily.repo_full_name == repo_full_name,
            HealthOverviewDaily.dt >= start_date,
            HealthOverviewDaily.dt <= end_date
        ).order_by(HealthOverviewDaily.dt).all()

    def _get_peer_comparison(self, repo_full_name: str) -> Optional[Dict[str, Any]]:
        """Get peer comparison data for a repository.

        Args:
            repo_full_name: Repository full name

        Returns:
            Peer comparison data or None
        """
        # This is a placeholder implementation
        # In a real implementation, this would get data from similar repositories
        return None

    def _check_missing_fields(self, facts: Dict[str, Any]) -> None:
        """Check for missing fields in the facts.

        Args:
            facts: Facts to check
        """
        # Check dimension scores
        for dim_name, dim_data in facts["dimensions"].items():
            if dim_data["score"] is None:
                facts["data_quality"]["missing_fields"].append(f"{dim_name}_score")
            
            for subscore_name, subscore_value in dim_data["subscores"].items():
                if subscore_value is None:
                    facts["data_quality"]["missing_fields"].append(f"{dim_name}_{subscore_name}")
        
        # Check metric values
        for metric_group, metrics in facts["metrics"].items():
            for metric_name, metric_value in metrics.items():
                if metric_value is None:
                    facts["data_quality"]["missing_fields"].append(f"{metric_group}_{metric_name}")
        
        # Add warnings for significant missing data
        if len(facts["data_quality"]["missing_fields"]) > 10:
            facts["data_quality"]["warnings"].append("Significant amount of data missing, analysis may be limited")


# Helper function to create extractor
def create_health_facts_extractor(db: Session) -> HealthFactsExtractor:
    """Create a health facts extractor.

    Args:
        db: Database session

    Returns:
        Health facts extractor
    """
    return HealthFactsExtractor(db)
