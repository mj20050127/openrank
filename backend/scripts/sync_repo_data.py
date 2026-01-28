"""Seed repo_catalog, repo_issues, repo_docs from GitHub for curated repos."""
import sys
from datetime import datetime
from typing import List, Optional, Tuple

from app.db.base import SessionLocal
from app.db.init_db import init_db
from app.db import models
from app.tools.github_client import GitHubClient

REPOS: List[Tuple[str, str]] = [
    # Web前端
    ("facebook/react", "frontend"),
    ("vuejs/core", "frontend"),
    ("angular/angular", "frontend"),
    ("sveltejs/svelte", "frontend"),
    ("solidjs/solid", "frontend"),
    ("preactjs/preact", "frontend"),
    ("vercel/next.js", "frontend"),
    ("nuxt/nuxt", "frontend"),
    ("vitejs/vite", "frontend"),
    ("webpack/webpack", "frontend"),
    ("rollup/rollup", "frontend"),
    ("babel/babel", "frontend"),
    ("eslint/eslint", "frontend"),
    ("prettier/prettier", "frontend"),
    ("tailwindlabs/tailwindcss", "frontend"),
    ("postcss/postcss", "frontend"),
    ("storybookjs/storybook", "frontend"),
    ("reduxjs/redux", "frontend"),
    ("react-hook-form/react-hook-form", "frontend"),
    ("pmndrs/zustand", "frontend"),
    ("TanStack/query", "frontend"),
    ("chakra-ui/chakra-ui", "frontend"),
    ("mui/material-ui", "frontend"),
    ("ant-design/ant-design", "frontend"),
    ("chartjs/Chart.js", "frontend"),
    # 后端/企业应用
    ("odoo/odoo", "backend"),
    ("django/django", "backend"),
    ("fastapi/fastapi", "backend"),
    ("pallets/flask", "backend"),
    ("spring-projects/spring-boot", "backend"),
    ("nestjs/nest", "backend"),
    ("laravel/laravel", "backend"),
    ("rails/rails", "backend"),
    ("expressjs/express", "backend"),
    ("dotnet/aspnetcore", "backend"),
    ("gin-gonic/gin", "backend"),
    ("gofiber/fiber", "backend"),
    ("strapi/strapi", "backend"),
    ("directus/directus", "backend"),
    ("supabase/supabase", "backend"),
    ("hasura/graphql-engine", "backend"),
    ("apollographql/apollo-server", "backend"),
    ("grpc/grpc", "backend"),
    ("prisma/prisma", "backend"),
    ("sequelize/sequelize", "backend"),
    ("knex/knex", "backend"),
    ("wordpress/wordpress-develop", "backend"),
    ("drupal/drupal", "backend"),
    ("parse-community/parse-server", "backend"),
    ("appwrite/appwrite", "backend"),
    # 移动开发
    ("flutter/flutter", "mobile"),
    ("facebook/react-native", "mobile"),
    ("ionic-team/ionic-framework", "mobile"),
    ("expo/expo", "mobile"),
    ("kotlin/kotlin", "mobile"),
    ("android/architecture-samples", "mobile"),
    ("android/nowinandroid", "mobile"),
    ("google/iosched", "mobile"),
    ("realm/realm-swift", "mobile"),
    ("Alamofire/Alamofire", "mobile"),
    ("ReactiveX/RxJava", "mobile"),
    ("RxSwiftCommunity/RxSwift", "mobile"),
    ("square/retrofit", "mobile"),
    ("square/okhttp", "mobile"),
    ("airbnb/lottie-android", "mobile"),
    ("airbnb/lottie-ios", "mobile"),
    ("facebook/flipper", "mobile"),
    ("firebase/firebase-android-sdk", "mobile"),
    ("firebase/firebase-ios-sdk", "mobile"),
    ("fastlane/fastlane", "mobile"),
    # 云原生/基础设施
    ("kubernetes/kubernetes", "cloud"),
    ("kubernetes/minikube", "cloud"),
    ("kubernetes/ingress-nginx", "cloud"),
    ("helm/helm", "cloud"),
    ("argoproj/argo-cd", "cloud"),
    ("fluxcd/flux2", "cloud"),
    ("istio/istio", "cloud"),
    ("linkerd/linkerd2", "cloud"),
    ("prometheus/prometheus", "cloud"),
    ("grafana/grafana", "cloud"),
    ("envoyproxy/envoy", "cloud"),
    ("docker/moby", "cloud"),
    ("containerd/containerd", "cloud"),
    ("cri-o/cri-o", "cloud"),
    ("etcd-io/etcd", "cloud"),
    ("hashicorp/terraform", "cloud"),
    ("hashicorp/consul", "cloud"),
    ("open-telemetry/opentelemetry-collector", "cloud"),
    ("jaegertracing/jaeger", "cloud"),
    ("cilium/cilium", "cloud"),
    ("traefik/traefik", "cloud"),
    ("nginx/nginx", "cloud"),
    ("apache/kafka", "cloud"),
    ("rabbitmq/rabbitmq-server", "cloud"),
    ("ansible/ansible", "cloud"),
    # AI/深度学习
    ("pytorch/pytorch", "ai"),
    ("tensorflow/tensorflow", "ai"),
    ("keras-team/keras", "ai"),
    ("huggingface/transformers", "ai"),
    ("huggingface/diffusers", "ai"),
    ("Lightning-AI/pytorch-lightning", "ai"),
    ("openai/whisper", "ai"),
    ("ultralytics/ultralytics", "ai"),
    ("scikit-learn/scikit-learn", "ai"),
    ("numpy/numpy", "ai"),
    ("pandas-dev/pandas", "ai"),
    ("apache/spark", "ai"),
    ("ray-project/ray", "ai"),
    ("dmlc/xgboost", "ai"),
    ("catboost/catboost", "ai"),
    ("facebookresearch/fairseq", "ai"),
    ("google-research/bert", "ai"),
    ("open-mmlab/mmdetection", "ai"),
    ("open-mmlab/mmsegmentation", "ai"),
    ("open-mmlab/mmpretrain", "ai"),
    ("jax-ml/jax", "ai"),
    ("ggerganov/llama.cpp", "ai"),
    ("NVIDIA/Megatron-LM", "ai"),
    ("NVIDIA/apex", "ai"),
    ("deepmind/alphafold", "ai"),
    # 安全/合规
    ("ossf/scorecard", "security"),
    ("aquasecurity/trivy", "security"),
    ("anchore/grype", "security"),
    ("anchore/syft", "security"),
    ("sigstore/sigstore", "security"),
    ("sigstore/cosign", "security"),
    ("in-toto/in-toto", "security"),
    ("open-policy-agent/opa", "security"),
    ("kyverno/kyverno", "security"),
    ("falcosecurity/falco", "security"),
    ("wazuh/wazuh", "security"),
    ("osquery/osquery", "security"),
    ("zeek/zeek", "security"),
    ("OISF/suricata", "security"),
    ("owasp-modsecurity/ModSecurity", "security"),
    ("OWASP/ASVS", "security"),
    ("OWASP/owasp-mastg", "security"),
    ("mitre/caldera", "security"),
    ("Netflix/security_monkey", "security"),
    ("google/osv.dev", "security"),
    # 开源生态分析
    ("X-lab2017/open-digger", "oss-analytics"),
    ("ossinsight/ossinsight", "oss-analytics"),
    ("cncf/devstats", "oss-analytics"),
    ("chaoss/augur", "oss-analytics"),
    ("chaoss/grimoirelab", "oss-analytics"),
    ("chaoss/grimoirelab-perceval", "oss-analytics"),
    ("chaoss/grimoirelab-sirmordred", "oss-analytics"),
    ("chaoss/grimoirelab-kidash", "oss-analytics"),
    ("chaoss/grimoirelab-sortinghat", "oss-analytics"),
    ("chaoss/grimoirelab-elk", "oss-analytics"),
    ("bitergia/perceval", "oss-analytics"),
    ("bitergia/kibiter", "oss-analytics"),
    ("gource/gource", "oss-analytics"),
    ("dspinellis/gitstats", "oss-analytics"),
    ("ossf/criticality_score", "oss-analytics"),
    # 文档
    ("facebook/docusaurus", "docs"),
    ("mkdocs/mkdocs", "docs"),
    ("sphinx-doc/sphinx", "docs"),
    ("vuejs/vuepress", "docs"),
    ("docsifyjs/docsify", "docs"),
    ("jekyll/jekyll", "docs"),
    ("gohugoio/hugo", "docs"),
    ("asciidoctor/asciidoctor", "docs"),
    ("rust-lang/mdBook", "docs"),
    ("mermaid-js/mermaid", "docs"),
    ("plantuml/plantuml", "docs"),
    ("redocly/redoc", "docs"),
    ("swagger-api/swagger-ui", "docs"),
    ("OpenAPITools/openapi-generator", "docs"),
    ("github/docs", "docs"),
    # 翻译
    ("weblate/weblate", "i18n"),
    ("mozilla/pontoon", "i18n"),
    ("crowdin/crowdin-cli", "i18n"),
    ("i18next/i18next", "i18n"),
    ("i18next/react-i18next", "i18n"),
    ("i18next/next-i18next", "i18n"),
    ("i18next/i18next-http-backend", "i18n"),
    ("i18next/i18next-browser-languagedetector", "i18n"),
    ("formatjs/formatjs", "i18n"),
    ("lingui/js-lingui", "i18n"),
    ("vuejs/vue-i18n", "i18n"),
    ("intlify/vue-i18n-next", "i18n"),
    ("airbnb/polyglot.js", "i18n"),
    ("globalizejs/globalize", "i18n"),
    ("messageformat/messageformat", "i18n"),
    ("projectfluent/fluent", "i18n"),
    ("projectfluent/fluent.js", "i18n"),
    ("translate/translate", "i18n"),
    ("autotools-mirror/gettext", "i18n"),
    ("python-babel/babel", "i18n"),
    ("ngx-translate/core", "i18n"),
    ("ngx-translate/http-loader", "i18n"),
    ("localizely/flutter-intl", "i18n"),
    ("kubernetes/website", "i18n"),
    ("vuejs/docs", "i18n"),
    ("reactjs/react.dev", "i18n"),
    ("nodejs/i18n", "i18n"),
    ("flutter/website", "i18n"),
    ("golang/website", "i18n"),
    ("kazupon/vue-i18n", "i18n"),
]


def parse_ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def infer_category(labels: List[str]) -> Optional[str]:
    lower = [l.lower() for l in labels]
    if any("good first issue" in l for l in lower):
        return "good_first_issue"
    if any("help wanted" in l for l in lower):
        return "help_wanted"
    if any("doc" in l for l in lower):
        return "docs"
    if any("translation" in l or "i18n" in l for l in lower):
        return "translation"
    return None


def infer_difficulty(labels: List[str]) -> Optional[str]:
    lower = [l.lower() for l in labels]
    if any("easy" in l or "beginner" in l for l in lower):
        return "Easy"
    if any("medium" in l or "intermediate" in l for l in lower):
        return "Medium"
    if any("hard" in l or "advanced" in l for l in lower):
        return "Hard"
    return None


def upsert_repo_catalog(session, gh: GitHubClient, repo_full_name: str, seed_domain: str) -> None:
    repo_data = gh.get_repo(repo_full_name) or {}
    license_info = repo_data.get("license") or {}
    license_id = license_info.get("spdx_id") or license_info.get("key")

    record = models.RepoCatalog(
        repo_full_name=repo_full_name,
        description=repo_data.get("description"),
        homepage=repo_data.get("homepage"),
        primary_language=repo_data.get("language"),
        topics=repo_data.get("topics"),
        default_branch=repo_data.get("default_branch"),
        license=license_id,
        stars=repo_data.get("stargazers_count"),
        forks=repo_data.get("forks_count"),
        open_issues_count=repo_data.get("open_issues_count"),
        pushed_at=parse_ts(repo_data.get("pushed_at")),
        domains=None,
        stacks=None,
        tags=None,
        seed_domain=seed_domain,
        fetched_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    session.merge(record)


def upsert_repo_issues(session, gh: GitHubClient, repo_full_name: str) -> None:
    issues = gh.list_repo_issues(repo_full_name, per_page=20)
    now = datetime.utcnow()
    for issue in issues:
        github_issue_id = issue.get("id")
        number = issue.get("number")
        if not github_issue_id or not number:
            continue
        labels_raw = issue.get("labels") or []
        labels = [l.get("name") for l in labels_raw if isinstance(l, dict) and l.get("name")]
        rec = models.RepoIssue(
            repo_full_name=repo_full_name,
            github_issue_id=github_issue_id,
            number=number,
            url=issue.get("html_url"),
            title=issue.get("title"),
            body=issue.get("body"),
            state=issue.get("state"),
            is_pull_request=bool(issue.get("pull_request")),
            labels=labels,
            author_login=(issue.get("user") or {}).get("login"),
            author_association=issue.get("author_association"),
            comments=issue.get("comments"),
            created_at=parse_ts(issue.get("created_at")),
            updated_at=parse_ts(issue.get("updated_at")),
            category=infer_category(labels),
            difficulty=infer_difficulty(labels),
            fetched_at=now,
            raw=issue,
        )
        session.merge(rec)


def upsert_repo_docs(session, gh: GitHubClient, repo_full_name: str) -> None:
    content = gh.get_readme(repo_full_name)
    if not content:
        return
    now = datetime.utcnow()
    rec = models.RepoDoc(
        repo_full_name=repo_full_name,
        path="README.md",
        sha=None,
        content=content,
        extracted=None,
        fetched_at=now,
        updated_at=now,
    )
    session.merge(rec)


def main() -> int:
    print("Initializing database and seeding curated repos...")
    init_db()
    gh = GitHubClient()
    session = SessionLocal()
    try:
        for repo_full_name, seed_domain in REPOS:
            print(f"[repo] {repo_full_name} ({seed_domain})")
            upsert_repo_catalog(session, gh, repo_full_name, seed_domain)
            upsert_repo_issues(session, gh, repo_full_name)
            upsert_repo_docs(session, gh, repo_full_name)
        session.commit()
        print("Done.")
        return 0
    except Exception as exc:
        session.rollback()
        print(f"Error: {exc}")
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
