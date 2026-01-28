# DataEase Datasets

本目录存放 DataEase 数据集 SQL（基于 `metric_points` 等基础表）。

## 数据集列表

- `kpi_cards.sql`: KPI 卡片（累计 attention / activity / openrank、活跃 repos 数）。
- `trend_metric.sql`: 趋势折线图（按天汇总，可用于 attention/activity/openrank）。
- `top10_attention.sql`: Top10 榜单（按 attention 排序）。
- `top10_growth.sql`: Top10 榜单（按 attention 增长率排序）。

> 说明：SQL 里使用 DataEase 变量 `${repo}` / `${metric}`，请在数据集参数中配置为多选或单选。
