"""LLM client for MaxKB integration."""

import json
import time
from typing import Dict, List, Optional, Any
from app.core.config import settings


class LLMClient:
    """LLM client for generating reports using MaxKB."""

    def __init__(self):
        """Initialize LLM client."""
        self.maxkb_api_key = getattr(settings, "MAXKB_API_KEY", "")
        self.maxkb_app_id = getattr(settings, "MAXKB_APP_ID", "")
        self.maxkb_endpoint = getattr(settings, "MAXKB_ENDPOINT", "http://localhost:8080")
        self.timeout = 60  # seconds

    def generate_report(self, module: str, facts: Dict[str, Any], prompt_template: str) -> Dict[str, Any]:
        """Generate report using MaxKB based on facts.

        Args:
            module: Report module (health, newcomer, trend)
            facts: Facts about the repository
            prompt_template: Prompt template for the LLM

        Returns:
            Generated report in JSON format
        """
        try:
            # Build the prompt
            prompt = self._build_prompt(module, facts, prompt_template)
            
            # Call MaxKB (placeholder implementation)
            # In a real implementation, this would call the MaxKB API
            response = self._call_maxkb(prompt)
            
            # Parse and validate the response
            report_json = self._parse_response(response)
            
            return report_json
        except Exception as e:
            # Return error response
            return {
                "error": str(e),
                "warnings": ["Failed to generate report using MaxKB, using fallback"],
                "summary_bullets": [],
                "sections": [],
                "actions": [],
                "monitor": []
            }

    def _build_prompt(self, module: str, facts: Dict[str, Any], prompt_template: str) -> str:
        """Build prompt for LLM.

        Args:
            module: Report module
            facts: Facts about the repository
            prompt_template: Prompt template

        Returns:
            Built prompt
        """
        # Load system prompt
        system_prompt = self._load_system_prompt()
        
        # Format the facts as JSON
        facts_json = json.dumps(facts, indent=2, ensure_ascii=False)
        
        # Build the full prompt
        full_prompt = f"{system_prompt}\n\n{prompt_template}\n\nFACTS:\n{facts_json}\n\nINSTRUCTIONS:\nPlease analyze the facts above and generate a structured report in JSON format. "
        full_prompt += "Make sure all numerical values in the report are directly from the facts. "
        full_prompt += "Do not extrapolate or invent any numbers. "
        full_prompt += "If data is insufficient, clearly state this in the warnings section."
        
        return full_prompt

    def _call_maxkb(self, prompt: str) -> str:
        """Call MaxKB API.

        Args:
            prompt: Prompt for the LLM

        Returns:
            Response from MaxKB
        """
        # This is a placeholder implementation
        # In a real implementation, this would make an HTTP request to MaxKB
        print(f"Calling MaxKB with prompt (truncated): {prompt[:500]}...")
        
        # Simulate API call delay
        time.sleep(2)
        
        # Return different mock responses based on the module in the prompt
        if "module=\"health\"" in prompt or "health_facts_json" in prompt:
            # Health module response
            mock_response = {
                "module": "health",
                "repo_full_name": "microsoft/vscode",
                "time_window_days": 30,
                "used_dt": "2026-01-09",
                "summary_bullets": [
                    "综合健康分良好，OpenRank持续上升",
                    "响应性维度有待提升，首响时间较长",
                    "安全维度表现稳定，无重大风险"
                ],
                "sections": [
                    {
                        "title": "Executive Summary",
                        "content_md": "仓库整体健康状况良好，综合健康分为85分。活跃度和安全性表现突出，但响应性需要改进。",
                        "evidence": [
                            {"key": "score_health", "value": 85, "dt": "2026-01-09"},
                            {"key": "metric_openrank", "value": 838.72, "dt": "2026-01-09"}
                        ]
                    },
                    {
                        "title": "五维解读",
                        "content_md": "活跃度：表现优秀，OpenRank持续上升，新贡献者数量稳定。\n响应性：需要改进，首响时间较长，建议优化工作流。\n韧性：风险指标处于合理范围，Bus Factor为5。\n治理：表现良好，scorecard得分7.4。\n安全：表现稳定，无重大漏洞。",
                        "evidence": [
                            {"key": "score_vitality", "value": 90, "dt": "2026-01-09"},
                            {"key": "score_responsiveness", "value": 70, "dt": "2026-01-09"},
                            {"key": "score_resilience", "value": 80, "dt": "2026-01-09"},
                            {"key": "score_governance", "value": 85, "dt": "2026-01-09"},
                            {"key": "score_security", "value": 88, "dt": "2026-01-09"}
                        ]
                    }
                ],
                "actions": [
                    {"title": "优化响应时间", "priority": "P1", "steps": ["设置SLA", "改进工作流"], "metrics_to_watch": ["metric_issue_response_time_h"]},
                    {"title": "提升治理水平", "priority": "P2", "steps": ["完善文档", "加强代码审查"], "metrics_to_watch": ["metric_scorecard_score"]}
                ],
                "monitor": ["metric_openrank", "metric_issue_response_time_h", "metric_bus_factor", "metric_scorecard_score"],
                "warnings": [],
                "data_gaps": []
            }
        elif "module=\"newcomer\"" in prompt or "newcomer_facts_json" in prompt:
            # Newcomer module response
            mock_response = {
                "module": "newcomer",
                "repo_full_name": "microsoft/vscode",
                "time_window_days": None,
                "used_dt": "2026-01-09",
                "summary_bullets": [
                    "推荐仓库：microsoft/vscode，匹配度高",
                    "新手就绪度良好，有丰富的good first issue",
                    "贡献路径清晰，适合前端开发者"
                ],
                "sections": [
                    {
                        "title": "推荐仓库 Top1",
                        "content_md": "推荐仓库：microsoft/vscode\n匹配度：85%\n新手就绪度：80%\n难度：Medium\n趋势：上升",
                        "evidence": [
                            {"key": "fit_score", "value": 85, "dt": "2026-01-09"},
                            {"key": "readiness_score", "value": 80, "dt": "2026-01-09"},
                            {"key": "trend_delta", "value": 5, "dt": "2026-01-09"}
                        ]
                    },
                    {
                        "title": "推荐理由",
                        "content_md": "1. 领域匹配：前端开发领域，与JavaScript技术栈高度相关\n2. 活跃度高：OpenRank持续上升，社区活跃\n3. 新手友好：有丰富的good first issue，文档完善",
                        "evidence": [
                            {"key": "reasons", "value": ["领域匹配", "技术栈相关"], "dt": "2026-01-09"}
                        ]
                    }
                ],
                "actions": [
                    {"title": "领取新手任务", "priority": "P0", "steps": ["浏览good first issue", "选择感兴趣的任务"], "metrics_to_watch": []},
                    {"title": "搭建开发环境", "priority": "P0", "steps": ["克隆仓库", "安装依赖", "配置IDE"], "metrics_to_watch": []},
                    {"title": "运行测试", "priority": "P1", "steps": ["运行单元测试", "确保构建通过"], "metrics_to_watch": []},
                    {"title": "提交PR", "priority": "P1", "steps": ["创建分支", "提交代码", "发起PR"], "metrics_to_watch": []},
                    {"title": "沟通review", "priority": "P2", "steps": ["回应评论", "更新代码", "等待合并"], "metrics_to_watch": []}
                ],
                "monitor": ["metric_activity", "metric_new_contributors"],
                "warnings": ["使用通用模板，非仓库特定"],
                "data_gaps": []
            }
        elif "module=\"trend\"" in prompt or "trend_facts_json" in prompt:
            # Trend module response
            mock_response = {
                "module": "trend",
                "repo_full_name": "microsoft/vscode",
                "time_window_days": 180,
                "used_dt": "2026-01-09",
                "summary_bullets": [
                    "活跃度趋势上升，OpenRank持续增长",
                    "响应性趋势稳定，但仍有改进空间",
                    "风险指标处于合理范围，无明显异常"
                ],
                "sections": [
                    {
                        "title": "Identify",
                        "content_md": "时间窗内总体趋势向好，活跃度和响应性都有提升。三个关键变化点：1) OpenRank持续上升，2) 响应时间略有下降，3) 风险指标稳定。",
                        "evidence": [
                            {"key": "trends.activity.last_value", "value": 90, "dt": "2026-01-09"},
                            {"key": "trends.activity.delta_pct", "value": 10, "dt": "2026-01-09"},
                            {"key": "trends.first_response.last_value", "value": 12, "dt": "2026-01-09"}
                        ]
                    },
                    {
                        "title": "Diagnosis",
                        "content_md": "活跃度上升可能与社区参与度增加有关，响应时间下降可能与issue数量增加有关。",
                        "evidence": []
                    },
                    {
                        "title": "Need Data?",
                        "content_md": "缺少更详细的issue分类数据，建议补采集。",
                        "evidence": []
                    },
                    {
                        "title": "Improvements",
                        "content_md": "1. 优化响应流程，减少首响时间\n2. 加强社区管理，提高参与度\n3. 完善风险监控体系",
                        "evidence": []
                    },
                    {
                        "title": "Monitor",
                        "content_md": "建议长期监控：OpenRank、响应时间、Bus Factor、Top1 Share、新贡献者数量。",
                        "evidence": []
                    }
                ],
                "actions": [
                    {"title": "优化响应流程", "priority": "P1", "steps": ["设置SLA", "改进工作流"], "metrics_to_watch": ["metric_issue_response_time_h"]},
                    {"title": "加强社区管理", "priority": "P2", "steps": ["组织社区活动", "完善贡献指南"], "metrics_to_watch": ["metric_new_contributors"]}
                ],
                "monitor": ["metric_openrank", "metric_issue_response_time_h", "metric_bus_factor", "metric_top1_share", "metric_new_contributors"],
                "warnings": [],
                "data_gaps": ["缺少详细的issue分类数据"]
            }
        else:
            # Default response
            mock_response = {
                "summary_bullets": [
                    "仓库活跃度较高，OpenRank持续上升",
                    "响应时间较长，需要改进",
                    "风险指标处于合理范围"
                ],
                "sections": [
                    {
                        "title": "Identify",
                        "content_md": "仓库整体健康状况良好，但响应性有待提升",
                        "evidence": [
                            {"key": "metric_openrank", "value": 838.72, "dt": "2026-01-09"}
                        ]
                    }
                ],
                "actions": [
                    {"title": "优化响应时间", "steps": ["设置SLA", "改进工作流"], "priority": "P1"}
                ],
                "monitor": ["metric_issue_response_time_h", "metric_activity"],
                "warnings": []
            }
        
        return json.dumps(mock_response, ensure_ascii=False)

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse response from MaxKB.

        Args:
            response: Response from MaxKB

        Returns:
            Parsed response
        """
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # If response is not valid JSON, return error
            return {
                "error": "Invalid JSON response from MaxKB",
                "summary_bullets": [],
                "sections": [],
                "actions": [],
                "monitor": [],
                "warnings": ["Failed to parse MaxKB response"]
            }

    def _load_system_prompt(self) -> str:
        """Load system prompt from file.

        Returns:
            System prompt
        """
        try:
            with open("app/services/ai_service/templates/system_prompt.txt", "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            # Return default system prompt
            return """You are an expert in open source project analysis. Your task is to generate structured reports based on the provided facts.

Rules:
1. Only use data from the provided facts. Do not invent or extrapolate any numbers.
2. Output must be in valid JSON format according to the specified schema.
3. If data is insufficient, clearly state this in the warnings section.
4. Focus on providing actionable insights based on the facts.
5. Be concise and professional in your analysis."""


# Singleton instance
llm_client = LLMClient()