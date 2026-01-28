from __future__ import annotations
import argparse
import json
import urllib.request
from pathlib import Path
from typing import Iterable, Iterator, Any, Dict
from datetime import datetime

from app.db.init_db import init_db
from app.db.base import SessionLocal
from app.db.models import MetricPoint
import re
from sqlalchemy import text
# 导入 registry 里的配置
from app.registry import METRIC_FILES, ensure_supported

# 模拟浏览器 UA
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def _parse_metrics(value: str) -> list[str]:
    # 升级点 1: 支持 'all' 关键字
    if value.lower() == "all":
        return list(METRIC_FILES.keys())
    return [item.strip() for item in value.split(",") if item.strip()]

def fetch_raw_json(owner: str, repo: str, filename: str) -> Dict | None:
    """
    升级点 2: 强壮的下载器
    使用 urllib 直接下载，遇到 404 自动捕获异常，不会让程序崩溃。
    """
    url = f"https://oss.open-digger.cn/github/{owner}/{repo}/{filename}"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"   ⚠️  [404] 该仓库没有此指标: {filename} (已跳过)")
        else:
            print(f"   ❌ [HTTP Error] 下载失败 {filename}: {e.code}")
        return None
    except Exception as e:
        print(f"   ❌ [Error] 网络或其他错误 {filename}: {e}")
        return None

def parse_opendigger_data(raw_data: Dict) -> Dict[str, float]:
    """
    升级点 3: 智能解析器
    处理 OpenDigger 各种奇葩的返回格式 (列表、字典、嵌套avg)
    """
    result = {}
    
    # 自动识别数据是在根目录，还是在 'avg'/'sum' 里面
    target_dict = raw_data
    if "avg" in raw_data and isinstance(raw_data["avg"], dict):
        target_dict = raw_data["avg"]
    elif "sum" in raw_data and isinstance(raw_data["sum"], dict):
        target_dict = raw_data["sum"]
        
    for key, val in target_dict.items():
        # 过滤掉非日期 key (比如 "2023", "meta" 等)
        # 有效的日期格式通常是 "YYYY-MM" (长度7, 中间是横杠)
        if len(key) != 7 or key[4] != '-': 
            continue
            
        numeric_val = 0.0
        # 数据清洗：转成 float
        if isinstance(val, (int, float)):
            numeric_val = float(val)
        elif isinstance(val, list):
            numeric_val = float(len(val)) # 列表转长度
            
        # 补全日期为 YYYY-MM-01
        full_date = f"{key}-01"
        result[full_date] = numeric_val
        
    return result

def fetch_metrics(repo: str, metrics: Iterable[str]) -> dict[str, int]:
    owner, name = repo.split("/", 1)
    counts: dict[str, int] = {}
    
    with SessionLocal() as db:
        # detect if legacy (metric,value) columns exist
        col_check = db.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name='metric_points' AND column_name IN ('metric','value');")
        ).fetchall()
        has_metric_value = len(col_check) > 0

        for metric in metrics:
            metric_file = METRIC_FILES.get(metric)
            if not metric_file: continue

            # 1. 安全下载 (遇到 404 会返回 None，不会崩)
            raw_data = fetch_raw_json(owner, name, metric_file)
            if not raw_data: 
                continue

            # 2. 智能解析
            parsed_data = parse_opendigger_data(raw_data)
            if not parsed_data: 
                continue

            counts[metric] = 0

            # 3. 入库：兼容两种 schema
            for date_str, value in parsed_data.items():
                dt_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

                if has_metric_value:
                    row = (
                        db.query(MetricPoint)
                        .filter(
                            MetricPoint.repo == repo,
                            MetricPoint.metric == metric,
                            MetricPoint.dt == dt_obj,
                        )
                        .first()
                    )
                    if row:
                        row.value = value
                    else:
                        db.add(
                            MetricPoint(
                                repo=repo,
                                metric=metric,
                                dt=dt_obj,
                                value=value,
                            )
                        )
                else:
                    # write into metric_<safe> column; create column if necessary
                    safe = _sanitize_identifier(metric)
                    col = f"metric_{safe}"
                    db.execute(text(f"ALTER TABLE metric_points ADD COLUMN IF NOT EXISTS {col} double precision;"))

                    # try update
                    upd = db.execute(
                        text(f"UPDATE metric_points SET {col} = :value WHERE repo = :repo AND dt = :dt"),
                        {"value": value, "repo": repo, "dt": dt_obj},
                    )
                    if upd.rowcount == 0:
                        # insert a minimal row
                        ins_cols = "repo, dt, " + col
                        ins_sql = text(f"INSERT INTO metric_points ({ins_cols}) VALUES (:repo, :dt, :value)")
                        db.execute(ins_sql, {"repo": repo, "dt": dt_obj, "value": value})

                counts[metric] += 1
        db.commit()
    return counts


def _sanitize_identifier(name: str) -> str:
    # keep letters, numbers and underscore
    return re.sub(r"[^0-9a-zA-Z_]", "_", name)


# 修改 backend/scripts/etl.py 中的 sync_repo_table 函数

def sync_repo_table(repo: str, metrics: Iterable[str]) -> None:
    sanitized = _sanitize_identifier(repo.replace('/', '_'))
    table_name = f"repo_{sanitized}"

    # 1) 定义我们要同步的所有列：原始指标 + 核心维度得分
    # 原始指标列名
    metric_cols = [f"metric_{_sanitize_identifier(m)}" for m in metrics]
    
    # 核心得分列名 (对应 health_overview_daily 中的字段)
    score_cols = [
        "score_health", "score_vitality", "score_responsiveness", 
        "score_resilience", "score_governance", "score_security"
    ]
    
    # 合并所有目标列
    all_target_cols = metric_cols + score_cols

    with SessionLocal() as db:
        # 2) 确保表存在
        db.execute(text(f"CREATE TABLE IF NOT EXISTS public.{table_name} (dt date PRIMARY KEY, repo_full_name text);"))

        # 3) 确保所有列（指标列 + 得分列）都在表中存在
        for col in all_target_cols:
            db.execute(text(f"ALTER TABLE public.{table_name} ADD COLUMN IF NOT EXISTS {col} double precision;"))

        # 4) 构建复杂的同步 SQL
        # 我们通过 LEFT JOIN 把 metric_points 的聚合数据和 health_overview_daily 的得分数据合并
        cols_csv = ", ".join(all_target_cols)
        
        # 指标部分从 metric_points 聚合 (MAX)，得分部分从 health_overview_daily 直接取
        select_metrics = ", ".join([f"max(mp.metric_{_sanitize_identifier(m)})" for m in metrics])
        select_scores = ", ".join([f"max(ho.{s})" for s in score_cols])
        
        update_csv = ", ".join([f"{col} = EXCLUDED.{col}" for col in all_target_cols])

        insert_sql = f"""
        INSERT INTO public.{table_name} (dt, repo_full_name, {cols_csv})
        SELECT 
            mp.dt, 
            :repo_full_name,
            {select_metrics}{', ' if select_metrics and select_scores else ''}{select_scores}
        FROM metric_points mp
        LEFT JOIN health_overview_daily ho 
            ON mp.repo = ho.repo_full_name AND mp.dt = ho.dt
        WHERE mp.repo = :repo
        GROUP BY mp.dt, ho.repo_full_name
        ON CONFLICT (dt) DO UPDATE SET {update_csv}, repo_full_name = EXCLUDED.repo_full_name;
        """

        db.execute(text(insert_sql), {"repo": repo, "repo_full_name": repo})
        db.commit()
        print(f"   ✅ synced per-repo table public.{table_name} (including health scores)")


def backfill_health_overview(repo: str, metrics: Iterable[str], limit_months: int | None = None) -> int:
    """Upsert health_overview_daily for given repo using data in metric_points.

    Supports both schemas of metric_points:
    - legacy: rows with columns (repo, metric, dt, value)
    - wide:   rows with columns repo, dt, metric_<name>
    """
    with SessionLocal() as db:
        # detect schema
        col_check = db.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name='metric_points' AND column_name IN ('metric','value');")
        ).fetchall()
        has_metric_value = len(col_check) > 0

        # get distinct dates for repo
        dates = db.execute(
            text("SELECT DISTINCT dt FROM metric_points WHERE repo = :repo ORDER BY dt"), {"repo": repo}
        ).fetchall()
        dts = [row[0] for row in dates]
        if limit_months is not None:
            dts = dts[-int(limit_months):]

        from app.services.metric_engine import MetricEngine
        engine = MetricEngine()
        upserts = 0

        for dt_value in dts:
            metrics_dict: Dict[str, Any] = {}
            if has_metric_value:
                # collect metric/value rows
                rows = db.query(MetricPoint).filter(
                    MetricPoint.repo == repo, MetricPoint.dt == dt_value
                ).all()
                metrics_dict = {r.metric: r.value for r in rows}
            else:
                # read a single wide row and map columns back to metric keys
                row = db.execute(
                    text("SELECT * FROM metric_points WHERE repo = :repo AND dt = :dt LIMIT 1"),
                    {"repo": repo, "dt": dt_value},
                ).mappings().first()
                if row:
                    for m in metrics:
                        safe = _sanitize_identifier(m)
                        col = f"metric_{safe}"
                        if col in row and row[col] is not None:
                            metrics_dict[m] = float(row[col])

            if not metrics_dict:
                continue

            record = engine.compute(
                repo_full_name=repo,
                dt_value=dt_value,
                metrics=metrics_dict,
                governance_files={},
                scorecard_checks={},
            )
            engine.upsert(db, record)
            upserts += 1

        print(f"   ✅ backfilled health_overview_daily for {repo} ({upserts} snapshots)")
        return upserts
        
def _iter_repos(repos_file: Path) -> Iterator[str]:
    seen: set[str] = set()
    if not repos_file.exists(): return
    with repos_file.open("r", encoding="utf-8") as handle:
        for line in handle:
            repo = line.strip()
            if not repo or repo.startswith("#") or repo in seen: continue
            seen.add(repo)
            yield repo

def _load_resume_marker(state_file: Path | None, resume: bool) -> str | None:
    if not resume or state_file is None or not state_file.exists(): return None
    return state_file.read_text(encoding="utf-8").strip() or None

def _store_resume_marker(state_file: Path | None, repo: str) -> None:
    if state_file is None: return
    state_file.write_text(repo, encoding="utf-8")

def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--repo", help="owner/repo")
    group.add_argument("--repos-file", type=Path)
    parser.add_argument("--metrics", default="openrank,activity,attention", help="comma-separated metrics or 'all'")
    parser.add_argument(
        "--backfill-ho",
        action="store_true",
        help="(deprecated) backfill health_overview_daily; now enabled by default",
    )
    parser.add_argument(
        "--no-backfill-ho",
        action="store_true",
        help="disable automatic backfill of health_overview_daily",
    )
    parser.add_argument("--limit-months", type=int, default=None, help="limit months per repo for backfill")
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    init_db()

    # 解析 metrics (处理 'all')
    metrics = _parse_metrics(args.metrics)
    
    # 此时 metrics 已经是完整的列表了，可以直接确保支持
    ensure_supported(metrics)

    auto_backfill = not args.no_backfill_ho  # default: on

    if args.repo:
        print(f"🚀 正在处理 {args.repo} (共 {len(metrics)} 个指标)...")
        counts = fetch_metrics(args.repo, metrics)
        print(f"✅ 完成: {counts}")
        if auto_backfill or args.backfill_ho:
            try:
                backfill_health_overview(args.repo, metrics, limit_months=args.limit_months)
            except Exception as e:
                print(f"   ⚠️ 回填 health_overview_daily 失败: {e}")
        try:
            sync_repo_table(args.repo, metrics)
        except Exception as e:
            print(f"   ⚠️ 同步 per-repo 表失败: {e}")
        return

    repos_file: Path = args.repos_file
    resume_marker = _load_resume_marker(args.state_file, args.resume)
    skipping = resume_marker is not None
    
    for repo in _iter_repos(repos_file):
        if skipping:
            if repo == resume_marker: skipping = False
            continue
        print(f"🚀 正在处理 {repo}...")
        counts = fetch_metrics(repo, metrics)
        _store_resume_marker(args.state_file, repo)
        print(f"   -> {counts}")
        if auto_backfill or args.backfill_ho:
            try:
                backfill_health_overview(repo, metrics, limit_months=args.limit_months)
            except Exception as e:
                print(f"   ⚠️ 回填 health_overview_daily 失败: {e}")
        try:
            sync_repo_table(repo, metrics)
        except Exception as e:
            print(f"   ⚠️ 同步 per-repo 表失败: {e}")

if __name__ == "__main__":
    main()