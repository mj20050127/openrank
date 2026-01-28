"""Intent Router (placeholder)
根据 query 识别 scenario + task。
"""


def route(query: str) -> dict:
    lowered = query.lower()
    if any(key in lowered for key in ["forecast", "预测"]):
        task = "forecast"
    elif any(key in lowered for key in ["alert", "预警", "告警"]):
        task = "monitor"
    elif any(key in lowered for key in ["report", "报告"]):
        task = "report"
    else:
        task = "health"

    if any(key in lowered for key in ["ospo", "portfolio", "组合"]):
        scenario = "ospo_portfolio"
    elif any(key in lowered for key in ["newcomer", "新人"]):
        scenario = "newcomer_guide"
    elif any(key in lowered for key in ["governance", "治理", "ecosystem"]):
        scenario = "ecosystem_governance"
    else:
        scenario = "maintainer_assistant"

    return {"scenario": scenario, "task": task}
