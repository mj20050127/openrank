"""Evidence checker for validating report data against facts."""

from typing import Dict, Any, List, Optional
from app.services.ai_service.validators.schema import ReportJSON, Evidence


class EvidenceChecker:
    """Check that all evidence in a report comes from facts."""

    def __init__(self, facts: Dict[str, Any]):
        """Initialize with facts.

        Args:
            facts: Facts about the repository
        """
        self.facts = facts
        self.evidence_map = self._build_evidence_map()

    def _build_evidence_map(self) -> Dict[str, Dict[str, float]]:
        """Build a map of evidence from facts for quick lookup.

        Returns:
            Map of metric keys to their values by date
        """
        evidence_map = {}

        # Extract metrics from different sections of facts
        if "metrics" in self.facts:
            # Check if metrics is a dictionary
            if isinstance(self.facts["metrics"], dict):
                for metric_group, metrics in self.facts["metrics"].items():
                    if isinstance(metrics, dict):
                        for metric_name, metric_value in metrics.items():
                            if metric_value is not None:
                                key = f"{metric_group}_{metric_name}"
                                if key not in evidence_map:
                                    evidence_map[key] = {}
                                evidence_map[key][self.facts.get("used_dt", "")] = metric_value

        # Extract dimension scores
        if "dimensions" in self.facts:
            for dim_name, dim_data in self.facts["dimensions"].items():
                if dim_data.get("score") is not None:
                    key = f"{dim_name}_score"
                    if key not in evidence_map:
                        evidence_map[key] = {}
                    evidence_map[key][self.facts.get("used_dt", "")] = dim_data["score"]

                # Extract subscores
                if "subscores" in dim_data:
                    for subscore_name, subscore_value in dim_data["subscores"].items():
                        if subscore_value is not None:
                            key = f"{dim_name}_{subscore_name}"
                            if key not in evidence_map:
                                evidence_map[key] = {}
                            evidence_map[key][self.facts.get("used_dt", "")] = subscore_value

        # Extract health score
        if "score_health" in self.facts and self.facts["score_health"] is not None:
            key = "score_health"
            if key not in evidence_map:
                evidence_map[key] = {}
            evidence_map[key][self.facts.get("used_dt", "")] = self.facts["score_health"]

        return evidence_map

    def validate_report(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that all evidence in the report comes from facts.

        Args:
            report: Report to validate

        Returns:
            Validation result with errors and warnings
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }

        # Check sections
        if "sections" in report:
            for section in report["sections"]:
                if "evidence" in section:
                    for evidence in section["evidence"]:
                        error = self._validate_evidence(evidence)
                        if error:
                            validation_result["valid"] = False
                            validation_result["errors"].append(error)

        # Check other fields that might contain numerical values
        # This is a placeholder for additional validation

        return validation_result

    def _validate_evidence(self, evidence: Dict[str, Any]) -> Optional[str]:
        """Validate a single evidence item.

        Args:
            evidence: Evidence to validate

        Returns:
            Error message if validation fails, None otherwise
        """
        key = evidence.get("key")
        value = evidence.get("value")
        dt = evidence.get("dt")

        if not key:
            return "Evidence missing key"
        if value is None:
            return f"Evidence for {key} missing value"
        if not dt:
            return f"Evidence for {key} missing date"

        # Check if key exists in evidence map
        if key not in self.evidence_map:
            return f"Metric {key} not found in facts"

        # Check if date exists for this key
        if dt not in self.evidence_map[key]:
            return f"Value for metric {key} not found on date {dt}"

        # Check if value matches
        if abs(self.evidence_map[key][dt] - value) > 0.001:
            return f"Value for metric {key} on date {dt} does not match facts. Expected {self.evidence_map[key][dt]}, got {value}"

        return None


# Helper function to create checker
def create_evidence_checker(facts: Dict[str, Any]) -> EvidenceChecker:
    """Create an evidence checker.

    Args:
        facts: Facts about the repository

    Returns:
        Evidence checker
    """
    return EvidenceChecker(facts)
