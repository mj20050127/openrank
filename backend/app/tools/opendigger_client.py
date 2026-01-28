from __future__ import annotations
import datetime as dt
from dataclasses import dataclass
from typing import Any, List
import httpx
from app.core.config import settings

@dataclass(frozen=True)
class MetricRecord:
    date: dt.date
    value: float

def _parse_dt(key: str) -> dt.date:
    """解析日期键，支持 YYYY-MM 和 YYYY-MM-DD"""
    key = key.strip()
    if len(key) == 7:
        y, m = key.split("-")
        return dt.date(int(y), int(m), 1)
    if len(key) == 10:
        y, m, d = key.split("-")
        return dt.date(int(y), int(m), int(d))
    raise ValueError(f"Unsupported date key: {key}")

def normalize_metric_json(payload: Any) -> List[MetricRecord]:
    """
    全能解析器：完全对齐 etl.py 的逻辑
    兼容 Flat(扁平)、Avg/Sum嵌套、以及 List(列表)转数值。
    """
    out: List[MetricRecord] = []
    target_dict = {}

    # 1. 智能定位数据源 (对齐 etl.py 的逻辑)
    if isinstance(payload, dict):
        if "avg" in payload and isinstance(payload["avg"], dict):
            target_dict = payload["avg"]
        elif "sum" in payload and isinstance(payload["sum"], dict):
            target_dict = payload["sum"]
        else:
            # 默认为扁平结构 (如 OpenRank, Activity)
            target_dict = payload
    else:
        return []

    # 2. 遍历解析
    for k, v in target_dict.items():
        try:
            # 过滤掉非日期的 Key (如 "meta", "levels" 等)
            # etl.py 使用 len(key) 判断，这里用 "-" 更宽容一点，效果一样
            if "-" not in str(k):
                continue

            date_obj = _parse_dt(str(k))
            val = 0.0

            # --- 核心修复：处理列表类型 (对齐 etl.py) ---
            # 某些指标(如 new_contributors)返回的是 list，需要取长度
            if isinstance(v, list):
                val = float(len(v))
            elif isinstance(v, (int, float)):
                val = float(v)
            else:
                continue # 其他类型无法转换，跳过

            out.append(MetricRecord(date_obj, val))
        except Exception:
            # 遇到无法解析的行（如格式错误的日期），跳过该行
            pass
    
    # 按日期排序，保证时序正确
    out.sort(key=lambda r: r.date)
    return out

class OpenDiggerClient:
    def __init__(self, timeout: float = 20.0):
        self.base_url = settings.OPENDIGGER_BASE_URL
        self.platform = settings.OPENDIGGER_PLATFORM
        self.timeout = timeout

    def metric_url(self, owner: str, repo: str, metric_file: str) -> str:
        return f"{self.base_url}/{self.platform}/{owner}/{repo}/{metric_file}"

    def fetch_metric(self, owner: str, repo: str, metric_file: str) -> List[MetricRecord]:
        url = self.metric_url(owner, repo, metric_file)
        # 保持 verify=False 应对 SSL 问题
        with httpx.Client(timeout=self.timeout, follow_redirects=True, verify=False) as c:
            r = c.get(url)
            r.raise_for_status()
            return normalize_metric_json(r.json())