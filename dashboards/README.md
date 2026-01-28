# DataEase Dashboards

- datasets/: 数据集 SQL（metric_points/snapshots/alerts 等）
- screenshots/: 看板截图（README/PPT 用）

## 看板：OpenRank 大屏

### 1) 新建看板
- 名称：`OpenRank 大屏`
- 数据源：连接到 `metric_points`（PostgreSQL）
- 过滤器：
  - `repo`（多选，默认全选）
  - `metric`（单选：attention/activity/openrank，默认 attention）

### 2) 数据集
在 DataEase 中导入以下 SQL（见 `dashboards/datasets/`）：
- `kpi_cards.sql`：KPI 卡片（累计 attention / activity / openrank、活跃 repos 数）
- `trend_metric.sql`：趋势折线图（按天汇总）
- `top10_attention.sql`：Top10 attention
- `top10_growth.sql`：Top10 attention 增长率

### 3) 组件布局（建议）
```
┌──────────────────────────────────────────────────────────────┐
│ 顶部 KPI：累计 attention | 活跃 repos | 累计 activity | 累计 openrank │
├──────────────────────────────────────────────────────────────┤
│ 趋势折线图（metric=attention/activity/openrank，可切换）          │
├───────────────────────────────┬──────────────────────────────┤
│ Top10 attention                │ Top10 attention 增长率          │
└───────────────────────────────┴──────────────────────────────┘
```

### 4) 主题风格建议
- 背景：深色（#0B1021）或浅色（#F7F9FC）
- 主色：#4C7DFF（折线和强调）
- 字体：思源黑体/苹方，标题 18-20px，指标 28-36px
- KPI 卡片：圆角 8px，阴影或细描边，数据加粗

### 5) 参数绑定提示
- `repo`：多选参数，SQL 内使用 `repo IN (${repo})`
- `metric`：单选参数，SQL 内使用 `metric = ${metric}`

> 建议在 DataEase 中将 `repo` 参数设置为“可为空/全选”，方便查看全量趋势。
