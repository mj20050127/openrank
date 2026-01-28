# -*- coding: utf-8 -*-
"""
health_pipeline.py (IoTDB Version)
------------------
Phase 1 + 2: 多日期抓取 + 窗口聚合 + IoTDB 时序写入

设计目标：
1) 抓取 OpenDigger 全量历史数据
2) 内存中计算滑动窗口 (3m/12m) 和 集中度 (HHI)
3) 将清洗后的时序数据写入 IoTDB，用于趋势分析和 AI 预测

存储结构 (DeviceID):
  root.openrank.github.{owner_safe}.{repo_safe}
  例如: root.openrank.github.X_lab2017.open_digger

依赖：
  pip install httpx apache-iotdb
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

# --- 核心变更：引入 IoTDB 依赖 ---
from iotdb.Session import Session
from iotdb.utils.IoTDBConstants import TSDataType

_MONTH_KEY_RE = re.compile(r"^\d{4}-\d{2}$")


def _env(name: str, default: str) -> str:
    v = os.getenv(name)
    return v if v not in (None, "") else default


def _parse_month_like(s: str) -> date:
    s = s.strip()
    if len(s) == 7 and _MONTH_KEY_RE.match(s):
        y, m = s.split("-")
        return date(int(y), int(m), 1)
    if len(s) == 10:
        d = datetime.strptime(s, "%Y-%m-%d").date()
        return date(d.year, d.month, 1)
    raise ValueError(f"Invalid date: {s}")


def _month_to_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _add_months(d: date, months: int) -> date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    return date(y, m, 1)


def _month_range(start: date, end: date) -> List[date]:
    if start > end:
        return []
    cur = date(start.year, start.month, 1)
    end = date(end.year, end.month, 1)
    out = []
    while cur <= end:
        out.append(cur)
        cur = _add_months(cur, 1)
    return out


def _extract_month_keys(ts: Dict[str, Any]) -> List[str]:
    keys = [k for k in ts.keys() if isinstance(k, str) and _MONTH_KEY_RE.match(k)]
    keys.sort()
    return keys


def _as_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


def _duration_to_hours(v: Any) -> Optional[float]:
    if v is None:
        return None
    x = _as_float(v, default=float("nan"))
    if x != x:
        return None
    unit = _env("OPENDIGGER_DURATION_UNIT", "hour").lower()
    if unit == "day":
        return x * 24.0
    return x


def _rolling_sum(series: Dict[date, float], months: List[date], idx: int, win: int) -> float:
    s = 0.0
    j0 = max(0, idx - win + 1)
    for j in range(j0, idx + 1):
        s += series.get(months[j], 0.0)
    return s


def _active_months(series: Dict[date, float], months: List[date], idx: int, win: int, threshold: float = 0.0) -> int:
    cnt = 0
    j0 = max(0, idx - win + 1)
    for j in range(j0, idx + 1):
        if series.get(months[j], 0.0) > threshold:
            cnt += 1
    return cnt


def _compute_hhi_and_top1_from_detail(detail_obj: Any) -> Tuple[Optional[float], Optional[float]]:
    values: List[float] = []
    if isinstance(detail_obj, dict):
        for v in detail_obj.values():
            values.append(_as_float(v, 0.0))
    elif isinstance(detail_obj, list):
        for item in detail_obj:
            if isinstance(item, dict):
                for key in ("value", "activity", "count"):
                    if key in item:
                        values.append(_as_float(item.get(key), 0.0))
                        break
            else:
                values.append(_as_float(item, 0.0))
    else:
        return (None, None)

    values = [v for v in values if v > 0]
    if not values:
        return (None, None)

    total = sum(values)
    if total <= 0:
        return (None, None)

    shares = [v / total for v in values]
    hhi = sum(s * s for s in shares)
    top1 = max(shares)
    return (float(hhi), float(top1))


@dataclass
class OpenDiggerStaticClient:
    base_url: str = _env("OPENDIGGER_BASE_URL", "https://oss.open-digger.cn").rstrip("/")
    platform: str = _env("OPENDIGGER_PLATFORM", "github").strip()

    async def fetch_metric(self, owner: str, repo: str, metric: str, client: httpx.AsyncClient) -> Dict[str, Any]:
        url = f"{self.base_url}/{self.platform}/{owner}/{repo}/{metric}.json"
        if not metric.endswith(".json"):
            url = f"{self.base_url}/{self.platform}/{owner}/{repo}/{metric}.json"

        for attempt in range(3):
            try:
                r = await client.get(url, headers={"accept": "application/json"})
                if r.status_code == 404:
                    return {}
                r.raise_for_status()
                data = r.json()
                return data if isinstance(data, dict) else {}
            except Exception:
                await asyncio.sleep(0.4 * (attempt + 1))
        return {}


class HealthPipeline:
    def __init__(
        self,
        iotdb_host: str = "127.0.0.1",
        iotdb_port: str = "6667",
        iotdb_user: str = "root",
        iotdb_password: str = "root",
        opendigger: Optional[OpenDiggerStaticClient] = None,
        metric_engine: Optional[Any] = None,
        storage_group_prefix: str = "root.openrank",
    ) -> None:
        """
        初始化：连接 IoTDB
        """
        self.od = opendigger or OpenDiggerStaticClient()
        self.sg_prefix = storage_group_prefix

        # 加载 MetricEngine
        if metric_engine is None:
            print("🔍 [DEBUG] 正在尝试加载 MetricEngine...")
            try:
                from app.services.metric_engine import MetricEngine
                self.engine = MetricEngine()
                print("✅ [DEBUG] MetricEngine 加载成功！")
            except Exception as e:
                # 这里的修改非常重要：打印具体的错误信息！
                print(f"❌ [DEBUG] MetricEngine 加载失败！原因: {e}")
                import traceback
                traceback.print_exc()
                self.engine = None
        else:
            self.engine = metric_engine

        # --- 连接 IoTDB ---
        print(f"🔌 Connecting to IoTDB ({iotdb_host}:{iotdb_port})...")
        try:
            self.session = Session(iotdb_host, iotdb_port, iotdb_user, iotdb_password)
            self.session.open(False)
            print("✅ IoTDB Connected.")
        except Exception as e:
            print(f"❌ IoTDB Connection Failed: {e}")
            raise e

    def close(self):
        if self.session.is_open():
            self.session.close()

    def _sanitize_iotdb_path(self, repo_full_name: str) -> str:
        """
        IoTDB 路径转换：
        X-lab2017/open-digger -> root.openrank.github.X_lab2017.open_digger
        """
        parts = repo_full_name.split("/")
        safe_parts = []
        for p in parts:
            # 替换特殊字符为下划线
            safe = p.replace("-", "_").replace(".", "_")
            safe_parts.append(safe)
        
        suffix = ".".join(safe_parts)
        return f"{self.sg_prefix}.github.{suffix}"

    def _rows_to_iotdb(self, rows: List[Dict[str, Any]]) -> int:
        """
        [修复版] 写入 IoTDB，自动跳过非数值字段 (如 dict/list)
        """
        if not rows:
            return 0
        
        repo_name = rows[0]["repo_full_name"]
        device_id = self._sanitize_iotdb_path(repo_name)
        
        count = 0
        for row in rows:
            dt = row["dt"]
            # 1. 时间戳转换：Date -> Unix Timestamp (ms)
            ts = int(datetime(dt.year, dt.month, dt.day).timestamp() * 1000)
            
            measurements = []
            types = []
            values = []
            
            # 2. 字段筛选
            for k, v in row.items():
                # 只处理 metric_ / score_ 开头的字段
                if (k.startswith("metric_") or k.startswith("score_")) and v is not None:
                    
                    # 🚨 关键修改：如果值是字典或列表，直接跳过，不写入 IoTDB
                    if isinstance(v, (dict, list)):
                        continue
                    
                    # 尝试转为 float，转不了的（比如字符串）也跳过
                    try:
                        float_val = float(v)
                        # IoTDB 路径不能含特殊字符
                        safe_measure = k
                        
                        measurements.append(safe_measure)
                        types.append(TSDataType.FLOAT)
                        values.append(float_val)
                    except (ValueError, TypeError):
                        continue
            
            # 3. 执行单行写入
            if measurements:
                try:
                    self.session.insert_record(device_id, ts, measurements, types, values)
                    count += 1
                except Exception as e:
                    print(f"⚠️ Write failed for {device_id} at {dt}: {e}")
        
        return count

    async def refresh_repos(
        self,
        repos: List[str],
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        主流程：拉取 -> 计算 -> 写入 IoTDB
        """
        result: Dict[str, Any] = {"repos": {}, "inserted": 0}
        
        # 使用 httpx 进行异步网络请求 (IO密集)
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
            total_rows = 0
            for repo_full in repos:
                owner, repo = repo_full.split("/", 1)
                
                # 1. 构建数据行 (复用原逻辑)
                rows = await self._build_rows_for_repo(owner, repo, client, date_from, date_to)
                
                # 2. 写入 IoTDB (同步 SDK 操作)
                # 注意：IoTDB 写入极快，这里简单的同步调用通常不会阻塞太久
                n = self._rows_to_iotdb(rows)
                
                total_rows += n
                result["repos"][repo_full] = {
                    "rows": n, 
                    "device_id": self._sanitize_iotdb_path(repo_full)
                }
            
            result["inserted"] = total_rows
        return result

    async def _build_rows_for_repo(
        self,
        owner: str,
        repo: str,
        client: httpx.AsyncClient,
        date_from: Optional[str],
        date_to: Optional[str],
    ) -> List[Dict[str, Any]]:
        """
        [业务逻辑保持不变] 从 OpenDigger 拉取并聚合数据
        """
        metrics = [
            "community_openrank",
            "activity",
            "participants",
            "issues_new",
            "issue_response_time",
            "issue_resolution_duration",
            "issue_age",
            "change_requests",
            "change_request_response_time",
            "change_request_resolution_duration",
            "change_request_age",
            "bus_factor",
            "inactive_contributors",
            "activity_details",
            "contributors_detail",
            "new_contributors_detail",
        ]

        fetched = await self._fetch_all(owner, repo, metrics, client)
        months = self._resolve_months(fetched.get("activity", {}), date_from, date_to)
        if not months:
            return []

        series_openrank = self._build_series(fetched.get("community_openrank", {}), months)
        series_activity = self._build_series(fetched.get("activity", {}), months)
        series_participants = self._build_series(fetched.get("participants", {}), months)
        series_issues_new = self._build_series(fetched.get("issues_new", {}), months)
        series_prs_new = self._build_series(fetched.get("change_requests", {}), months)
        series_bus_factor = self._build_series(fetched.get("bus_factor", {}), months)
        series_inactive = self._build_series(fetched.get("inactive_contributors", {}), months)

        s_issue_resp = self._build_duration_series_hours(fetched.get("issue_response_time", {}), months)
        s_issue_close = self._build_duration_series_hours(fetched.get("issue_resolution_duration", {}), months)
        s_issue_age = self._build_duration_series_hours(fetched.get("issue_age", {}), months)
        s_pr_resp = self._build_duration_series_hours(fetched.get("change_request_response_time", {}), months)
        s_pr_close = self._build_duration_series_hours(fetched.get("change_request_resolution_duration", {}), months)
        s_pr_age = self._build_duration_series_hours(fetched.get("change_request_age", {}), months)

        rows: List[Dict[str, Any]] = []
        detail_activity = fetched.get("activity_details", {}) or {}
        detail_contrib = fetched.get("contributors_detail", {}) or {}
        detail_new_contrib = fetched.get("new_contributors_detail", {}) or {}

        for idx, dt in enumerate(months):
            mk = _month_to_key(dt)

            activity_3m = _rolling_sum(series_activity, months, idx, 3)
            participants_3m = _rolling_sum(series_participants, months, idx, 3)
            new_contrib_3m = self._rolling_new_contributors_3m(detail_new_contrib, months, idx)
            activity_prev_3m = _rolling_sum(series_activity, months, idx - 3, 3) if idx >= 3 else 0.0
            active_months_12m = _active_months(series_activity, months, idx, 12)

            hhi, top1_share = self._month_concentration(mk, detail_activity)
            if hhi is None and top1_share is None:
                hhi, top1_share = self._month_concentration(mk, detail_contrib)

            participants = series_participants.get(dt, 0.0)
            inactive = series_inactive.get(dt, 0.0)
            retention_rate = None
            if participants > 0:
                retention_rate = max(0.0, min(1.0, 1.0 - inactive / participants))

            metrics_row: Dict[str, Any] = {
                "repo_full_name": f"{owner}/{repo}",
                "dt": dt,
                "metric_openrank": series_openrank.get(dt, 0.0),
                "metric_activity": series_activity.get(dt, 0.0),
                "metric_participants": participants,
                "metric_issues_new": series_issues_new.get(dt, 0.0),
                "metric_prs_new": series_prs_new.get(dt, 0.0),
                "metric_issue_response_time_h": s_issue_resp.get(dt),
                "metric_issue_resolution_duration_h": s_issue_close.get(dt),
                "metric_issue_age_h": s_issue_age.get(dt),
                "metric_pr_response_time_h": s_pr_resp.get(dt),
                "metric_pr_resolution_duration_h": s_pr_close.get(dt),
                "metric_pr_age_h": s_pr_age.get(dt),
                "metric_bus_factor": series_bus_factor.get(dt, 0.0),
                "metric_hhi": hhi,
                "metric_top1_share": top1_share,
                "metric_inactive_contributors": inactive,
                "metric_retention_rate": retention_rate,
                "metric_activity_3m": activity_3m,
                "metric_activity_prev_3m": activity_prev_3m,
                "metric_participants_3m": participants_3m,
                "metric_new_contributors_3m": new_contrib_3m,
                "metric_active_months_12m": active_months_12m,
            }

            if self.engine is not None:
                scores = self._compute_scores_safe(metrics_row)
                metrics_row.update(scores)

            rows.append(metrics_row)

        return rows

    async def _fetch_all(self, owner: str, repo: str, metric_names: List[str], client: httpx.AsyncClient) -> Dict[str, Dict[str, Any]]:
        tasks = [self.od.fetch_metric(owner, repo, m, client) for m in metric_names]
        res = await asyncio.gather(*tasks, return_exceptions=True)
        out: Dict[str, Dict[str, Any]] = {}
        for m, r in zip(metric_names, res):
            if isinstance(r, Exception):
                out[m] = {}
            else:
                out[m] = r if isinstance(r, dict) else {}
        return out

    def _resolve_months(self, activity_ts: Dict[str, Any], date_from: Optional[str], date_to: Optional[str]) -> List[date]:
        if date_from and date_to:
            return _month_range(_parse_month_like(date_from), _parse_month_like(date_to))
        keys = _extract_month_keys(activity_ts or {})
        if not keys:
            return []
        return _month_range(_parse_month_like(keys[0]), _parse_month_like(keys[-1]))

    def _build_series(self, ts: Dict[str, Any], months: List[date]) -> Dict[date, float]:
        out = {}
        for dt in months:
            out[dt] = _as_float(ts.get(_month_to_key(dt)), 0.0)
        return out

    def _build_duration_series_hours(self, ts: Dict[str, Any], months: List[date]) -> Dict[date, Optional[float]]:
        out = {}
        for dt in months:
            out[dt] = _duration_to_hours(ts.get(_month_to_key(dt)))
        return out

    def _month_concentration(self, month_key: str, detail_ts: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        if not isinstance(detail_ts, dict):
            return (None, None)
        return _compute_hhi_and_top1_from_detail(detail_ts.get(month_key))

    def _rolling_new_contributors_3m(self, new_contrib_detail_ts: Dict[str, Any], months: List[date], idx: int) -> float:
        s = 0.0
        j0 = max(0, idx - 3 + 1)
        for j in range(j0, idx + 1):
            mk = _month_to_key(months[j])
            obj = new_contrib_detail_ts.get(mk)
            if isinstance(obj, dict):
                s += float(len(obj.keys()))
            elif isinstance(obj, list):
                s += float(len(obj))
        return s

    def _compute_scores_safe(self, metrics_row: Dict[str, Any]) -> Dict[str, Any]:
        """
        [标准版] 调用 MetricEngine 计算分数
        前提：MetricEngine.compute 已修复为接收 (metrics, dt_value)
        """
        # 1. 如果引擎没加载成功，直接返回空
        if self.engine is None:
            return {}
        
        # 2. 尝试调用
        try:
            # 你的 MetricEngine 已经修复为可以只传一个字典参数
            # 它会自动处理内部的 dt 和 key 兼容逻辑
            result = self.engine.compute(metrics_row)
            
            # 确保返回的是字典
            return result if isinstance(result, dict) else {}
            
        except Exception as e:
            # 只有真的出错才打印，平时保持安静
            print(f"❌ [算分异常] {e}")
            # 调试阶段可以把下面这行解开
            # import traceback; traceback.print_exc()
            return {}

# ==========================================
# 命令行启动入口
# ==========================================
if __name__ == "__main__":
    import argparse
    import asyncio

    async def main_cli():
        parser = argparse.ArgumentParser(description="Health Pipeline (IoTDB): 历史数据清洗")
        parser.add_argument("--repo", required=True, help="仓库名, e.g. X-lab2017/open-digger")
        parser.add_argument("--host", default="127.0.0.1", help="IoTDB Host")
        parser.add_argument("--port", default="6667", help="IoTDB Port")
        parser.add_argument("--start", help="Start YYYY-MM")
        parser.add_argument("--end", help="End YYYY-MM")

        args = parser.parse_args()

        pipeline = None
        try:
            pipeline = HealthPipeline(iotdb_host=args.host, iotdb_port=args.port)
            print(f"🚀 开始处理: {args.repo} ...")

            res = await pipeline.refresh_repos(
                [args.repo],
                date_from=args.start,
                date_to=args.end
            )

            print("✅ 处理完成！")
            print(json.dumps(res, indent=2, ensure_ascii=False))
            
            # 显示 IoTDB Device ID，方便你去查询
            if args.repo in res["repos"]:
                device_id = res["repos"][args.repo]["device_id"]
                print(f"\n💡 IoTDB Device ID: {device_id}")
                print(f"   查询语句示例: SELECT score_health FROM {device_id}")

        except Exception as e:
            print(f"❌ 运行失败: {e}")
        finally:
            if pipeline:
                pipeline.close()

    asyncio.run(main_cli())