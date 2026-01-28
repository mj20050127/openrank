"""Trend facts extractor from health_overview_daily."""

from typing import Dict, Any, List, Optional, Tuple
from datetime import date, timedelta
import statistics
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.db.models import HealthOverviewDaily


class TrendFactsExtractor:
    """Extract trend facts from database."""

    def __init__(self, db: Session):
        """Initialize with database session.

        Args:
            db: Database session
        """
        self.db = db

    def extract_facts(self, repo_full_name: str, time_window_days: int = 180, metrics: List[str] = None) -> Dict[str, Any]:
        """Extract trend facts for a repository.

        Args:
            repo_full_name: Repository full name (owner/repo)
            time_window_days: Time window in days
            metrics: List of metrics to analyze

        Returns:
            Facts about the repository's trends
        """
        if metrics is None:
            metrics = ["activity", "first_response", "bus_factor", "scorecard"]

        facts = {
            "repo_full_name": repo_full_name,
            "time_window_days": time_window_days,
            "metrics": metrics,
            "used_dt": None,
            "trends": {},
            "anomalies": [],
            "data_quality": {
                "available_days": 0,
                "missing_fields": [],
                "warnings": []
            }
        }

        # Get historical data
        historical_data = self._get_historical_data(repo_full_name, time_window_days)
        
        if historical_data:
            facts["used_dt"] = historical_data[-1].dt.isoformat()
            facts["data_quality"]["available_days"] = len(historical_data)
            
            # Analyze each metric
            for metric in metrics:
                metric_data = self._analyze_metric(historical_data, metric)
                if metric_data:
                    facts["trends"][metric] = metric_data
                    
                    # Check for anomalies
                    anomalies = self._detect_anomalies(metric_data["values"])
                    if anomalies:
                        for anomaly in anomalies:
                            facts["anomalies"].append({
                                "metric": metric,
                                "date": metric_data["dates"][anomaly["index"]],
                                "value": anomaly["value"],
                                "type": anomaly["type"]
                            })
            
            # Check data quality
            if len(historical_data) < 14:
                facts["data_quality"]["warnings"].append("Insufficient data points for reliable trend analysis")
            
            if not facts["trends"]:
                facts["data_quality"]["warnings"].append("No valid trend data available for the specified metrics")
        else:
            facts["data_quality"]["warnings"].append(f"No historical data found for repository: {repo_full_name}")

        return facts

    def _get_historical_data(self, repo_full_name: str, time_window_days: int) -> List[HealthOverviewDaily]:
        """Get historical health data for a repository.

        Args:
            repo_full_name: Repository full name
            time_window_days: Time window in days

        Returns:
            List of historical health data
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=time_window_days)
        
        return self.db.query(HealthOverviewDaily).filter(
            HealthOverviewDaily.repo_full_name == repo_full_name,
            HealthOverviewDaily.dt >= start_date,
            HealthOverviewDaily.dt <= end_date
        ).order_by(HealthOverviewDaily.dt).all()

    def _analyze_metric(self, historical_data: List[HealthOverviewDaily], metric: str) -> Optional[Dict[str, Any]]:
        """Analyze a specific metric from historical data.

        Args:
            historical_data: Historical health data
            metric: Metric to analyze

        Returns:
            Metric analysis results
        """
        # Map metric names to database fields
        metric_map = {
            "activity": "metric_activity",
            "first_response": "metric_issue_response_time_h",
            "bus_factor": "metric_bus_factor",
            "scorecard": "metric_scorecard_score",
            "pr_response": "metric_pr_response_time_h",
            "issue_age": "metric_issue_age_h",
            "pr_age": "metric_pr_age_h",
            "hhi": "metric_hhi",
            "top1_share": "metric_top1_share",
            "retention_rate": "metric_retention_rate"
        }

        if metric not in metric_map:
            return None

        field_name = metric_map[metric]
        values = []
        dates = []

        for data in historical_data:
            value = getattr(data, field_name)
            if value is not None:
                values.append(value)
                dates.append(data.dt.isoformat())

        if not values:
            return None

        # Calculate metrics
        last_value = values[-1]
        first_value = values[0]
        delta = last_value - first_value
        delta_pct = (delta / first_value * 100) if first_value != 0 else 0

        # Calculate moving average
        if len(values) >= 7:
            moving_avg = self._calculate_moving_average(values, window=7)
        else:
            moving_avg = None

        # Determine trend direction
        trend_direction = self._determine_trend_direction(values)

        # Calculate volatility
        volatility = self._calculate_volatility(values)

        return {
            "values": values,
            "dates": dates,
            "last_value": last_value,
            "first_value": first_value,
            "delta": delta,
            "delta_pct": delta_pct,
            "moving_avg": moving_avg,
            "trend_direction": trend_direction,
            "volatility": volatility
        }

    def _calculate_moving_average(self, values: List[float], window: int = 7) -> List[float]:
        """Calculate moving average of values.

        Args:
            values: List of values
            window: Window size

        Returns:
            List of moving average values
        """
        moving_avg = []
        for i in range(len(values)):
            if i < window - 1:
                moving_avg.append(None)
            else:
                window_values = values[i-window+1:i+1]
                moving_avg.append(sum(window_values) / window)
        return moving_avg

    def _determine_trend_direction(self, values: List[float]) -> str:
        """Determine trend direction of values.

        Args:
            values: List of values

        Returns:
            Trend direction (up, down, flat)
        """
        if len(values) < 3:
            return "flat"

        # Use simple linear regression to determine trend
        n = len(values)
        sum_x = sum(range(n))
        sum_y = sum(values)
        sum_xy = sum(i * y for i, y in enumerate(values))
        sum_x2 = sum(i * i for i in range(n))

        # Calculate slope
        if n * sum_x2 - sum_x * sum_x == 0:
            return "flat"

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)

        # Determine trend direction based on slope
        if abs(slope) < 0.01 * abs(sum_y) / n:
            return "flat"
        elif slope > 0:
            return "up"
        else:
            return "down"

    def _calculate_volatility(self, values: List[float]) -> float:
        """Calculate volatility of values.

        Args:
            values: List of values

        Returns:
            Volatility (standard deviation)
        """
        if len(values) < 2:
            return 0.0
        return statistics.stdev(values)

    def _detect_anomalies(self, values: List[float], threshold: float = 2.0) -> List[Dict[str, Any]]:
        """Detect anomalies in values using 3-sigma rule.

        Args:
            values: List of values
            threshold: Sigma threshold for anomaly detection

        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        if len(values) < 5:
            return anomalies

        mean = statistics.mean(values)
        std_dev = statistics.stdev(values)
        
        if std_dev == 0:
            return anomalies

        for i, value in enumerate(values):
            z_score = abs(value - mean) / std_dev
            if z_score > threshold:
                anomalies.append({
                    "index": i,
                    "value": value,
                    "type": "outlier",
                    "z_score": z_score
                })

        return anomalies


# Helper function to create extractor
def create_trend_facts_extractor(db: Session) -> TrendFactsExtractor:
    """Create a trend facts extractor.

    Args:
        db: Database session

    Returns:
        Trend facts extractor
    """
    return TrendFactsExtractor(db)
