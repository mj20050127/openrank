"""Newcomer facts extractor from repo_catalog, repo_issues, and repo_docs."""

from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from app.db.models import HealthOverviewDaily
from app.models import RepoCatalog, RepoDoc, RepoIssue


class NewcomerFactsExtractor:
    """Extract newcomer facts from database."""

    def __init__(self, db: Session):
        """Initialize with database session.

        Args:
            db: Database session
        """
        self.db = db

    def extract_facts(self, domain: str, stack: str, time_per_week: str, keywords: str, top_n: int = 3) -> Dict[str, Any]:
        """Extract newcomer facts based on user input.

        Args:
            domain: Interest domain (e.g., frontend, backend, ai_ml)
            stack: Technology stack (e.g., javascript, python, go)
            time_per_week: Time available per week (e.g., 1-2h, 3-5h)
            keywords: Additional keywords for filtering
            top_n: Number of top repositories to return

        Returns:
            Facts about recommended repositories for newcomers
        """
        facts = {
            "input": {
                "domain": domain,
                "stack": stack,
                "time_per_week": time_per_week,
                "keywords": keywords
            },
            "top_repos": [],
            "data_quality": {
                "available_repos": 0,
                "missing_fields": [],
                "warnings": []
            }
        }

        # Get recommended repositories
        recommended_repos = self._get_recommended_repos(domain, stack, keywords, top_n)
        facts["top_repos"] = recommended_repos
        facts["data_quality"]["available_repos"] = len(recommended_repos)

        if not recommended_repos:
            facts["data_quality"]["warnings"].append("No recommended repositories found based on the provided criteria")

        return facts

    def _get_recommended_repos(self, domain: str, stack: str, keywords: str, top_n: int) -> List[Dict[str, Any]]:
        """Get recommended repositories for newcomers.

        Args:
            domain: Interest domain
            stack: Technology stack
            keywords: Additional keywords
            top_n: Number of top repositories to return

        Returns:
            List of recommended repositories with details
        """
        recommended_repos = []

        # Get repositories from catalog
        repos = self._search_repo_catalog(domain, stack, keywords, limit=top_n * 2)
        
        for repo in repos:
            # Calculate fit score based on domain and stack matching
            fit_score = 50  # Base score
            
            # Add score for domain match
            if domain and domain != "all":
                # Check if domain is in domains array
                if hasattr(repo, 'domains'):
                    repo_domains = repo.domains
                    # Handle different types of domains field
                    if isinstance(repo_domains, list) and domain in repo_domains:
                        fit_score += 30
                    elif isinstance(repo_domains, str) and domain in repo_domains:
                        fit_score += 30
                # Check seed_domain as fallback
                elif hasattr(repo, 'seed_domain') and repo.seed_domain == domain:
                    fit_score += 30
            
            # Add score for stack match
            if stack and stack != "all":
                # Check if stack is in stacks array
                if hasattr(repo, 'stacks'):
                    repo_stacks = repo.stacks
                    # Handle different types of stacks field
                    if isinstance(repo_stacks, list) and stack in repo_stacks:
                        fit_score += 20
                    elif isinstance(repo_stacks, str) and stack in repo_stacks:
                        fit_score += 20
            
            # Add score for keyword match
            if keywords:
                if hasattr(repo, 'repo_full_name') and keywords.lower() in repo.repo_full_name.lower():
                    fit_score += 10
                elif hasattr(repo, 'description') and repo.description and keywords.lower() in repo.description.lower():
                    fit_score += 5
            
            # Ensure score is within 0-100 range
            fit_score = min(100, max(0, fit_score))
            
            # Calculate readiness score based on health data
            readiness_score = 70  # Base score
            readiness_evidence = self._get_readiness_evidence(repo.repo_full_name)
            
            # Adjust readiness score based on evidence
            if readiness_evidence:
                # Check responsiveness
                if readiness_evidence.get('responsiveness', {}).get('issue_response_time_h'):
                    response_time = readiness_evidence['responsiveness']['issue_response_time_h']
                    if response_time < 24:
                        readiness_score += 15
                    elif response_time < 72:
                        readiness_score += 5
                    elif response_time > 168:
                        readiness_score -= 10
                
                # Check activity
                if readiness_evidence.get('activity', {}).get('openrank'):
                    openrank = readiness_evidence['activity']['openrank']
                    if openrank > 500:
                        readiness_score += 10
                    elif openrank > 100:
                        readiness_score += 5
            
            # Ensure score is within 0-100 range
            readiness_score = min(100, max(0, readiness_score))
            
            # Determine difficulty based on scores
            if fit_score >= 80 and readiness_score >= 80:
                difficulty = "Easy"
            elif fit_score >= 60 or readiness_score >= 60:
                difficulty = "Medium"
            else:
                difficulty = "Hard"
            
            # Calculate trend delta based on activity
            trend_delta = 0
            if readiness_evidence.get('activity', {}).get('activity_growth'):
                trend_delta = readiness_evidence['activity']['activity_growth']
            else:
                # Default trend based on fit score
                if fit_score >= 80:
                    trend_delta = 8
                elif fit_score >= 60:
                    trend_delta = 3
                else:
                    trend_delta = -2
            
            # Generate recommended reasons based on matching criteria
            reasons = []
            if domain and domain != "all":
                # Check if domain is in domains array
                domain_match = False
                if hasattr(repo, 'domains'):
                    repo_domains = repo.domains
                    if isinstance(repo_domains, list) and domain in repo_domains:
                        domain_match = True
                    elif isinstance(repo_domains, str) and domain in repo_domains:
                        domain_match = True
                elif hasattr(repo, 'seed_domain') and repo.seed_domain == domain:
                    domain_match = True
                
                if domain_match:
                    reasons.append("领域匹配度高")
            
            if stack and stack != "all":
                # Check if stack is in stacks array
                stack_match = False
                if hasattr(repo, 'stacks'):
                    repo_stacks = repo.stacks
                    if isinstance(repo_stacks, list) and stack in repo_stacks:
                        stack_match = True
                    elif isinstance(repo_stacks, str) and stack in repo_stacks:
                        stack_match = True
                
                if stack_match:
                    reasons.append("技术栈高度相关")
            if fit_score >= 80:
                reasons.append("整体匹配度优秀")
            if readiness_score >= 80:
                reasons.append("新手就绪度高")
            if difficulty == "Easy":
                reasons.append("难度较低，适合新手")
            if trend_delta > 5:
                reasons.append("社区活跃度上升趋势明显")
            
            # If no specific reasons, add general ones
            if not reasons:
                reasons = ["仓库活跃", "适合新手贡献"]
            
            repo_facts = {
                "repo_full_name": repo.repo_full_name,
                "fit_score": fit_score,
                "readiness_score": readiness_score,
                "difficulty": difficulty,
                "trend_delta": trend_delta,
                "reasons": reasons,
                "readiness_evidence": readiness_evidence,
                "tasks": [],
                "onboarding": {}
            }

            # Get tasks from repo_issues
            repo_facts["tasks"] = self._get_newcomer_tasks(repo.repo_full_name)
            
            # Get onboarding info from repo_docs
            repo_facts["onboarding"] = self._get_onboarding_info(repo.repo_full_name)
            
            recommended_repos.append(repo_facts)

            if len(recommended_repos) >= top_n:
                break

        # Sort by fit score in descending order
        recommended_repos.sort(key=lambda x: x['fit_score'], reverse=True)

        return recommended_repos

    def _search_repo_catalog(self, domain: str, stack: str, keywords: str, limit: int = 10):
        """Search repository catalog based on criteria (Fixed Version)."""
        from app.models import RepoCatalog
        from sqlalchemy import or_, cast, String, desc
        
        # 1. 基础查询
        query = self.db.query(RepoCatalog)

        # 2. 技术栈过滤 (Stack -> Primary Language OR Stacks Tag)
        # 逻辑：只要 语言 或 技术栈标签 中包含该关键字即可
        if stack and stack != "all":
            query = query.filter(
                or_(
                    RepoCatalog.primary_language.ilike(f"%{stack}%"),
                    cast(RepoCatalog.stacks, String).ilike(f"%{stack}%")
                )
            )

        # 3. 领域与关键词过滤 (Domain/Keywords -> Description OR Topics OR Domains)
        # 逻辑：把领域也当作一种关键词，去匹配描述、主题或领域标签
        search_terms = []
        if domain and domain != "all":
            search_terms.append(domain)
        if keywords:
            search_terms.append(keywords)
            
        if search_terms:
            conditions = []
            for term in search_terms:
                # 匹配描述
                conditions.append(RepoCatalog.description.ilike(f"%{term}%"))
                # 匹配 JSONB 类型的标签 (强转字符串后匹配，防止报错)
                conditions.append(cast(RepoCatalog.topics, String).ilike(f"%{term}%"))
                conditions.append(cast(RepoCatalog.domains, String).ilike(f"%{term}%"))
            
            # 满足任意一个条件即可
            query = query.filter(or_(*conditions))

        # 4. 排序：优先推荐 Star 数高的优质项目 (假设你有 stars 字段)
        if hasattr(RepoCatalog, 'stars'):
            query = query.order_by(desc(RepoCatalog.stars))
        
        # 执行查询
        results = query.limit(limit).all()
        
        # 5. [重要] 兜底逻辑：如果什么都没搜到，返回 Top 仓库，而不是空
        # 这样能避免页面一片空白，同时在控制台打印警告
        if not results:
            print(f"⚠️ Warning: No repos found for stack='{stack}', domain='{domain}'. Returning fallback top repos.")
            fallback_query = self.db.query(RepoCatalog)
            if hasattr(RepoCatalog, 'stars'):
                fallback_query = fallback_query.order_by(desc(RepoCatalog.stars))
            return fallback_query.limit(limit).all()
            
        return results

    def _get_readiness_evidence(self, repo_full_name: str) -> Dict[str, Any]:
        """Get readiness evidence for a repository.

        Args:
            repo_full_name: Repository full name

        Returns:
            Readiness evidence
        """
        evidence = {
            "responsiveness": {},
            "activity": {},
            "task_supply": {},
            "onboarding": {}
        }

        # Get latest health data for the repository
        latest_health = self.db.query(HealthOverviewDaily).filter(
            HealthOverviewDaily.repo_full_name == repo_full_name
        ).order_by(desc(HealthOverviewDaily.dt)).first()

        if latest_health:
            # Responsiveness metrics
            evidence["responsiveness"] = {
                "issue_response_time_h": latest_health.metric_issue_response_time_h,
                "pr_response_time_h": latest_health.metric_pr_response_time_h,
                "issue_age_h": latest_health.metric_issue_age_h,
                "pr_age_h": latest_health.metric_pr_age_h
            }

            # Activity metrics
            evidence["activity"] = {
                "activity_3m": latest_health.metric_activity_3m,
                "new_contributors": latest_health.metric_new_contributors,
                "activity_growth": latest_health.metric_activity_growth
            }

        # Get task supply from repo_issues
        evidence["task_supply"] = self._get_task_supply(repo_full_name)

        # Get onboarding info from repo_docs
        evidence["onboarding"] = self._get_onboarding_metrics(repo_full_name)

        return evidence

    def _get_task_supply(self, repo_full_name: str) -> Dict[str, Any]:
        """Get task supply metrics for a repository.

        Args:
            repo_full_name: Repository full name

        Returns:
            Task supply metrics
        """
        # This is a placeholder implementation
        # In a real implementation, this would query the repo_issues table
        return {
            "good_first_issues": 0,
            "help_wanted_issues": 0,
            "documentation_issues": 0,
            "bug_issues": 0
        }

    def _get_onboarding_metrics(self, repo_full_name: str) -> Dict[str, Any]:
        """Get onboarding metrics for a repository.

        Args:
            repo_full_name: Repository full name

        Returns:
            Onboarding metrics
        """
        # This is a placeholder implementation
        # In a real implementation, this would query the repo_docs table
        return {
            "has_readme": False,
            "has_contributing": False,
            "has_pr_template": False,
            "has_setup_guide": False
        }

    def _get_newcomer_tasks(self, repo_full_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get newcomer-friendly tasks for a repository.

        Args:
            repo_full_name: Repository full name
            limit: Maximum number of tasks to return

        Returns:
            List of newcomer-friendly tasks
        """
        # This is a placeholder implementation
        # In a real implementation, this would query the repo_issues table
        # and filter for newcomer-friendly issues
        return []

    def _get_onboarding_info(self, repo_full_name: str) -> Dict[str, Any]:
        """Get onboarding information for a repository.

        Args:
            repo_full_name: Repository full name

        Returns:
            Onboarding information
        """
        # This is a placeholder implementation
        # In a real implementation, this would query the repo_docs table
        return {
            "has_readme": False,
            "has_contributing": False,
            "has_pr_template": False,
            "setup_guide": None,
            "build_guide": None,
            "test_guide": None
        }


# Helper function to create extractor
def create_newcomer_facts_extractor(db: Session) -> NewcomerFactsExtractor:
    """Create a newcomer facts extractor.

    Args:
        db: Database session

    Returns:
        Newcomer facts extractor
    """
    return NewcomerFactsExtractor(db)
