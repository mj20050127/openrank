"""Markdown renderer for report JSON."""

from typing import Dict, Any, Optional
import json


class MarkdownRenderer:
    """Render report JSON to Markdown format."""

    def render(self, report_json: Dict[str, Any]) -> str:
        """Render report JSON to Markdown.

        Args:
            report_json: Report JSON to render

        Returns:
            Rendered Markdown
        """
        markdown_parts = []

        # Add title based on module
        module = report_json.get("module", "report")
        title = self._get_report_title(module)
        markdown_parts.append(f"# {title}")
        markdown_parts.append("")

        # Add repository info if available
        if "repo" in report_json and report_json["repo"]:
            markdown_parts.append(f"## Repository")
            markdown_parts.append(f"- Repository: {report_json['repo']}")
            if "time_window_days" in report_json:
                markdown_parts.append(f"- Time Window: {report_json['time_window_days']} days")
            if "used_dt" in report_json and report_json["used_dt"]:
                markdown_parts.append(f"- Data Date: {report_json['used_dt']}")
            markdown_parts.append("")

        # Add summary bullets
        if "summary_bullets" in report_json and report_json["summary_bullets"]:
            markdown_parts.append("## Executive Summary")
            for bullet in report_json["summary_bullets"]:
                markdown_parts.append(f"- {bullet}")
            markdown_parts.append("")

        # Add sections
        if "sections" in report_json and report_json["sections"]:
            for section in report_json["sections"]:
                if "title" in section:
                    markdown_parts.append(f"## {section['title']}")
                if "content_md" in section and section["content_md"]:
                    markdown_parts.append(section["content_md"])
                if "evidence" in section and section["evidence"]:
                    markdown_parts.append("### Evidence")
                    for evidence in section["evidence"]:
                        formatted_value = self._format_value(evidence["value"])
                        markdown_parts.append(f"- {evidence['key']}: {formatted_value} (as of {evidence['dt']})")
                markdown_parts.append("")

        # Add actions
        if "actions" in report_json and report_json["actions"]:
            markdown_parts.append("## Action Recommendations")
            for action in report_json["actions"]:
                if "title" in action:
                    priority = action.get("priority", "P1")
                    markdown_parts.append(f"### [{priority}] {action['title']}")
                if "steps" in action and action["steps"]:
                    for i, step in enumerate(action["steps"], 1):
                        markdown_parts.append(f"{i}. {step}")
                markdown_parts.append("")

        # Add monitor metrics
        if "monitor" in report_json and report_json["monitor"]:
            markdown_parts.append("## Metrics to Monitor")
            for metric in report_json["monitor"]:
                markdown_parts.append(f"- {metric}")
            markdown_parts.append("")

        # Add warnings
        if "warnings" in report_json and report_json["warnings"]:
            markdown_parts.append("## Data Quality Warnings")
            for warning in report_json["warnings"]:
                markdown_parts.append(f"- {warning}")
            markdown_parts.append("")

        # Add error if present
        if "error" in report_json and report_json["error"]:
            markdown_parts.append("## Error")
            markdown_parts.append(f"- {report_json['error']}")
            markdown_parts.append("")

        # Join all parts and return
        return "\n".join(markdown_parts)

    def _get_report_title(self, module: str) -> str:
        """Get report title based on module.

        Args:
            module: Report module

        Returns:
            Report title
        """
        title_map = {
            "health": "Health Report",
            "newcomer": "Newcomer Report",
            "trend": "Trend Monitor Report"
        }
        return title_map.get(module, "Open Source Project Report")

    def _format_value(self, value: Any) -> str:
        """Format value for display.

        Args:
            value: Value to format

        Returns:
            Formatted value
        """
        if value is None:
            return "--"
        
        if isinstance(value, float):
            # Format based on value magnitude
            if abs(value) >= 100:
                return f"{value:.0f}"
            elif abs(value) >= 10:
                return f"{value:.1f}"
            elif abs(value) >= 0.1:
                return f"{value:.2f}"
            else:
                return f"{value:.3f}"
        
        return str(value)


class HealthReportRenderer(MarkdownRenderer):
    """Render health report JSON to Markdown."""

    def render(self, report_json: Dict[str, Any]) -> str:
        """Render health report JSON to Markdown.

        Args:
            report_json: Health report JSON to render

        Returns:
            Rendered Markdown
        """
        markdown_parts = []

        # Add title
        markdown_parts.append("# Health Report")
        markdown_parts.append("")

        # Add repository info
        if "repo" in report_json and report_json["repo"]:
            markdown_parts.append(f"## Repository")
            markdown_parts.append(f"- Repository: {report_json['repo']}")
            if "time_window_days" in report_json:
                markdown_parts.append(f"- Time Window: {report_json['time_window_days']} days")
            if "used_dt" in report_json and report_json["used_dt"]:
                markdown_parts.append(f"- Data Date: {report_json['used_dt']}")
            markdown_parts.append("")

        # Add health score
        if "score_health" in report_json and report_json["score_health"] is not None:
            score = self._format_value(report_json["score_health"])
            markdown_parts.append(f"## Health Score")
            markdown_parts.append(f"- Overall Score: {score}")
            markdown_parts.append("")

        # Add summary bullets
        if "summary_bullets" in report_json and report_json["summary_bullets"]:
            markdown_parts.append("## Executive Summary")
            for bullet in report_json["summary_bullets"]:
                markdown_parts.append(f"- {bullet}")
            markdown_parts.append("")

        # Add sections
        if "sections" in report_json and report_json["sections"]:
            for section in report_json["sections"]:
                if "title" in section:
                    markdown_parts.append(f"## {section['title']}")
                if "content_md" in section and section["content_md"]:
                    markdown_parts.append(section["content_md"])
                if "evidence" in section and section["evidence"]:
                    markdown_parts.append("### Evidence")
                    for evidence in section["evidence"]:
                        formatted_value = self._format_value(evidence["value"])
                        markdown_parts.append(f"- {evidence['key']}: {formatted_value} (as of {evidence['dt']})")
                markdown_parts.append("")

        # Add actions
        if "actions" in report_json and report_json["actions"]:
            markdown_parts.append("## Action Recommendations")
            for action in report_json["actions"]:
                if "title" in action:
                    priority = action.get("priority", "P1")
                    markdown_parts.append(f"### [{priority}] {action['title']}")
                if "steps" in action and action["steps"]:
                    for i, step in enumerate(action["steps"], 1):
                        markdown_parts.append(f"{i}. {step}")
                markdown_parts.append("")

        # Add monitor metrics
        if "monitor" in report_json and report_json["monitor"]:
            markdown_parts.append("## Metrics to Monitor")
            for metric in report_json["monitor"]:
                markdown_parts.append(f"- {metric}")
            markdown_parts.append("")

        # Add warnings
        if "warnings" in report_json and report_json["warnings"]:
            markdown_parts.append("## Data Quality Warnings")
            for warning in report_json["warnings"]:
                markdown_parts.append(f"- {warning}")
            markdown_parts.append("")

        return "\n".join(markdown_parts)


class NewcomerReportRenderer(MarkdownRenderer):
    """Render newcomer report JSON to Markdown."""

    def render(self, report_json: Dict[str, Any]) -> str:
        """Render newcomer report JSON to Markdown.

        Args:
            report_json: Newcomer report JSON to render

        Returns:
            Rendered Markdown
        """
        markdown_parts = []

        # Add title
        markdown_parts.append("# Newcomer Report")
        markdown_parts.append("")

        # Add input info
        if "input" in report_json:
            markdown_parts.append("## Input Criteria")
            for key, value in report_json["input"].items():
                if value:
                    markdown_parts.append(f"- {key.replace('_', ' ').title()}: {value}")
            markdown_parts.append("")

        # Add top repositories
        if "top_repos" in report_json and report_json["top_repos"]:
            markdown_parts.append("## Recommended Repositories")
            for i, repo in enumerate(report_json["top_repos"], 1):
                markdown_parts.append(f"### {i}. {repo.get('repo_full_name', 'Unknown')}")
                if "fit_score" in repo:
                    markdown_parts.append(f"- Fit Score: {self._format_value(repo['fit_score'])}%")
                if "readiness_score" in repo:
                    markdown_parts.append(f"- Readiness Score: {self._format_value(repo['readiness_score'])}%")
                if "difficulty" in repo:
                    markdown_parts.append(f"- Difficulty: {repo['difficulty']}")
                if "trend_delta" in repo:
                    trend = self._format_value(repo["trend_delta"])
                    markdown_parts.append(f"- 30-day Trend: {trend}%")
                if "reasons" in repo and repo["reasons"]:
                    markdown_parts.append(f"- Reasons: {', '.join(repo['reasons'])}")
                markdown_parts.append("")

        # Add summary bullets
        if "summary_bullets" in report_json and report_json["summary_bullets"]:
            markdown_parts.append("## Executive Summary")
            for bullet in report_json["summary_bullets"]:
                markdown_parts.append(f"- {bullet}")
            markdown_parts.append("")

        # Add sections
        if "sections" in report_json and report_json["sections"]:
            for section in report_json["sections"]:
                if "title" in section:
                    markdown_parts.append(f"## {section['title']}")
                if "content_md" in section and section["content_md"]:
                    markdown_parts.append(section["content_md"])
                if "evidence" in section and section["evidence"]:
                    markdown_parts.append("### Evidence")
                    for evidence in section["evidence"]:
                        formatted_value = self._format_value(evidence["value"])
                        markdown_parts.append(f"- {evidence['key']}: {formatted_value} (as of {evidence['dt']})")
                markdown_parts.append("")

        # Add actions
        if "actions" in report_json and report_json["actions"]:
            markdown_parts.append("## Action Recommendations")
            for action in report_json["actions"]:
                if "title" in action:
                    priority = action.get("priority", "P1")
                    markdown_parts.append(f"### [{priority}] {action['title']}")
                if "steps" in action and action["steps"]:
                    for i, step in enumerate(action["steps"], 1):
                        markdown_parts.append(f"{i}. {step}")
                markdown_parts.append("")

        # Add warnings
        if "warnings" in report_json and report_json["warnings"]:
            markdown_parts.append("## Data Quality Warnings")
            for warning in report_json["warnings"]:
                markdown_parts.append(f"- {warning}")
            markdown_parts.append("")

        return "\n".join(markdown_parts)


class TrendReportRenderer(MarkdownRenderer):
    """Render trend report JSON to Markdown."""

    def render(self, report_json: Dict[str, Any]) -> str:
        """Render trend report JSON to Markdown.

        Args:
            report_json: Trend report JSON to render

        Returns:
            Rendered Markdown
        """
        markdown_parts = []

        # Add title
        markdown_parts.append("# Trend Monitor Report")
        markdown_parts.append("")

        # Add repository info
        if "repo" in report_json and report_json["repo"]:
            markdown_parts.append(f"## Repository")
            markdown_parts.append(f"- Repository: {report_json['repo']}")
            if "time_window_days" in report_json:
                markdown_parts.append(f"- Time Window: {report_json['time_window_days']} days")
            if "used_dt" in report_json and report_json["used_dt"]:
                markdown_parts.append(f"- Data Date: {report_json['used_dt']}")
            markdown_parts.append("")

        # Add trends
        if "trends" in report_json and report_json["trends"]:
            markdown_parts.append("## Trend Analysis")
            for metric, trend_data in report_json["trends"].items():
                markdown_parts.append(f"### {metric.replace('_', ' ').title()}")
                if "last_value" in trend_data:
                    markdown_parts.append(f"- Current Value: {self._format_value(trend_data['last_value'])}")
                if "delta" in trend_data:
                    delta = self._format_value(trend_data["delta"])
                    delta_pct = self._format_value(trend_data.get("delta_pct", 0))
                    markdown_parts.append(f"- Change: {delta} ({delta_pct}%)")
                if "trend_direction" in trend_data:
                    markdown_parts.append(f"- Trend Direction: {trend_data['trend_direction']}")
                if "volatility" in trend_data:
                    volatility = self._format_value(trend_data["volatility"])
                    markdown_parts.append(f"- Volatility: {volatility}")
                markdown_parts.append("")

        # Add anomalies
        if "anomalies" in report_json and report_json["anomalies"]:
            markdown_parts.append("## Detected Anomalies")
            for anomaly in report_json["anomalies"]:
                metric = anomaly.get("metric", "Unknown")
                date = anomaly.get("date", "Unknown")
                value = self._format_value(anomaly.get("value", 0))
                markdown_parts.append(f"- {metric} on {date}: {value} ({anomaly.get('type', 'anomaly')})")
            markdown_parts.append("")

        # Add summary bullets
        if "summary_bullets" in report_json and report_json["summary_bullets"]:
            markdown_parts.append("## Executive Summary")
            for bullet in report_json["summary_bullets"]:
                markdown_parts.append(f"- {bullet}")
            markdown_parts.append("")

        # Add sections
        if "sections" in report_json and report_json["sections"]:
            for section in report_json["sections"]:
                if "title" in section:
                    markdown_parts.append(f"## {section['title']}")
                if "content_md" in section and section["content_md"]:
                    markdown_parts.append(section["content_md"])
                if "evidence" in section and section["evidence"]:
                    markdown_parts.append("### Evidence")
                    for evidence in section["evidence"]:
                        formatted_value = self._format_value(evidence["value"])
                        markdown_parts.append(f"- {evidence['key']}: {formatted_value} (as of {evidence['dt']})")
                markdown_parts.append("")

        # Add actions
        if "actions" in report_json and report_json["actions"]:
            markdown_parts.append("## Action Recommendations")
            for action in report_json["actions"]:
                if "title" in action:
                    priority = action.get("priority", "P1")
                    markdown_parts.append(f"### [{priority}] {action['title']}")
                if "steps" in action and action["steps"]:
                    for i, step in enumerate(action["steps"], 1):
                        markdown_parts.append(f"{i}. {step}")
                markdown_parts.append("")

        # Add monitor metrics
        if "monitor" in report_json and report_json["monitor"]:
            markdown_parts.append("## Metrics to Monitor")
            for metric in report_json["monitor"]:
                markdown_parts.append(f"- {metric}")
            markdown_parts.append("")

        # Add warnings
        if "warnings" in report_json and report_json["warnings"]:
            markdown_parts.append("## Data Quality Warnings")
            for warning in report_json["warnings"]:
                markdown_parts.append(f"- {warning}")
            markdown_parts.append("")

        return "\n".join(markdown_parts)


# Helper function to create renderer based on module
def create_markdown_renderer(module: str) -> MarkdownRenderer:
    """Create a markdown renderer based on the report module.

    Args:
        module: Report module

    Returns:
        Markdown renderer
    """
    renderer_map = {
        "health": HealthReportRenderer(),
        "newcomer": NewcomerReportRenderer(),
        "trend": TrendReportRenderer()
    }
    return renderer_map.get(module, MarkdownRenderer())
