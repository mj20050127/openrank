# Metric Dictionary

## 1. 适用范围与权威口径

本文档定义 OpenSage 治理看板使用的指标名称、单位、方向、来源和缺失值语义。

当前仓库的即时健康分以后端 `current-v1` 为唯一权威口径：

- 接口：`GET /health/current?repo={owner}/{repo}`
- 版本字段：`score_version = "current-v1"`
- 观察窗口：默认最近 90 天
- 分数范围：0–100 分，分数越高越好
- 当前排名：只使用 `current-v1` 的 `scores.comprehensive`
- 月度历史：用于趋势和指标下钻，不覆盖即时健康分

前端不得用月度指标重新计算或覆盖即时综合分；前端只负责展示后端返回的 `scores`、`completeness`、`confidence` 和证据。

## 2. 五维健康分

| API 维度 | 中文名 | 权重 | 主要含义 | 当前分来源 |
| --- | --- | ---: | --- | --- |
| `vitality` | 活跃度 | 30% | 最近活动、持续性和参与规模 | GitHub 最近 90 天证据 |
| `responsiveness` | 响应度 | 25% | Issue/PR 的处理流转和积压年龄 | GitHub 最近 90 天协作证据 |
| `resilience` | 韧性 | 20% | 贡献者分散度、Bus Factor 和持续参与 | GitHub 最近 90 天贡献者证据 |
| `governance` | 治理 | 15% | 协作流程与治理文件完整性 | GitHub 当前仓库结构和协作证据 |
| `security` | 安全 | 10% | Scorecard、安全政策和工作流检查 | OpenSSF Scorecard + GitHub |

综合分公式为：

```text
comprehensive =
    0.30 * vitality
  + 0.25 * responsiveness
  + 0.20 * resilience
  + 0.15 * governance
  + 0.10 * security
```

当证据不完整时，各维度只对可用子项重新加权；综合分只有在五个维度均可计算且总体完整度至少为 80% 时返回。

## 3. 即时评分的输入字段

### 3.1 仓库元数据 `evidence.metadata`

| 字段 | 类型 | 单位 | 方向 | 用途 |
| --- | --- | --- | --- | --- |
| `default_branch` | string | — | — | 确定默认分支 |
| `pushed_at` | datetime | UTC | 越新越好 | 计算 `push_age_days` |
| `updated_at` | datetime | UTC | — | 证据时间 |
| `stars` | integer | 个 | 描述性 | 仓库规模展示，不直接计入当前五维分 |
| `forks` | integer | 个 | 描述性 | 仓库规模展示，不直接计入当前五维分 |
| `archived` | boolean | — | 风险提示 | 仓库状态展示 |

### 3.2 活跃度 `evidence.activity` 与贡献者

| 字段 | 类型 | 单位 | 计算含义 |
| --- | --- | --- | --- |
| `commits_current` | integer | 次 | 当前 90 天提交数 |
| `commits_previous` | integer | 次 | 前一个 90 天提交数 |
| `active_weeks` | integer | 周 | 当前窗口有提交的周数 |
| `weeks_observed` | integer | 周 | 实际观测到的周数 |
| `active_contributors` | integer | 人 | 当前窗口有贡献的贡献者数 |
| `total_contributions` | integer | 次 | 当前窗口贡献总量 |
| `bus_factor` | integer/null | 人 | 覆盖 50% 贡献所需的最少贡献者数 |
| `top1_share` | number/null | 0–1 | 第一贡献者占全部贡献的比例 |

派生特征：

- `active_week_score = 100 * active_weeks / weeks_observed`
- `push_age_days = observed_at - pushed_at`，按天计
- 动能使用对数增长受限的 `_momentum(current, previous)`：前后窗口相等约为 50 分，改善趋近 100 分，恶化趋近 0 分
- 规模类指标使用 `_log_score(value, reference)`，避免极端大项目支配分数

活跃度子项权重为：提交动能 30%、活跃周 25%、推送新鲜度 20%、Issue/PR 总吞吐动能 15%、活跃贡献者 10%。

### 3.3 协作响应 `evidence.collaboration`

| 字段 | 类型 | 单位 | 计算含义 |
| --- | --- | --- | --- |
| `issues_opened` | integer | 项 | 当前窗口新增 Issue |
| `issues_opened_previous` | integer | 项 | 前一窗口新增 Issue |
| `issues_closed` | integer | 项 | 当前窗口关闭 Issue |
| `prs_opened` | integer | 项 | 当前窗口新增 PR |
| `prs_opened_previous` | integer | 项 | 前一窗口新增 PR |
| `prs_merged` | integer | 项 | 当前窗口合并 PR |
| `open_issue_median_age_days` | number/null | 天 | 当前未关闭 Issue 的中位年龄 |
| `open_pr_median_age_days` | number/null | 天 | 当前未关闭 PR 的中位年龄 |
| `open_issue_age_sample` | integer | 项 | Issue 年龄样本量 |
| `open_pr_age_sample` | integer | 项 | PR 年龄样本量 |

派生特征：

- `issue_flow_score = clamp(100 * issues_closed / issues_opened, 0, 100)`
- `pr_flow_score = clamp(100 * (prs_merged / prs_opened) / 0.8, 0, 100)`
- Issue 年龄评分以 180 天为风险上限；PR 年龄评分以 120 天为风险上限
- Issue 流转 30%、PR 流转 30%、Issue 年龄 20%、PR 年龄 20%

当分母为 0 时，只有存在正向产出才返回 100 分，否则该子项为空；该语义必须在建议中保留，不能把“没有新增任务”直接解释为“处理效率 100%”。

### 3.4 治理证据 `evidence.governance`

`files` 是仓库治理文件是否存在的布尔映射：

| 文件键 | 典型文件 | 文件分权重 |
| --- | --- | ---: |
| `readme` | README | 10 |
| `license` | LICENSE | 15 |
| `contributing` | CONTRIBUTING | 20 |
| `code_of_conduct` | CODE_OF_CONDUCT | 15 |
| `security` | SECURITY | 10 |
| `issue_template` | Issue 模板 | 10 |
| `pull_request_template` | PR 模板 | 10 |
| `governance` | GOVERNANCE | 5 |
| `codeowners` | CODEOWNERS | 5 |

`governance_file_score` 为存在文件的权重之和，满分 100。流程分由 Issue/PR 流转和未关闭年龄组成：Issue 流转 40%、PR 流转 40%、Issue 年龄 10%、PR 年龄 10%。

```text
governance = 0.60 * governance_process_score
           + 0.40 * governance_file_score
```

### 3.5 安全证据 `evidence.scorecard` 与工作流

| 字段/特征 | 单位 | 说明 |
| --- | --- | --- |
| `scorecard.score` | 0–10 | OpenSSF Scorecard 原始分，转换为 0–100 |
| `features.scorecard_component` | 0–100 | `scorecard.score * 10` |
| `features.security_components.security_policy` | 0/100 | 是否存在安全政策 |
| `features.security_components.dependency_update` | 0–100 | 依赖更新检查或配置 |
| `features.security_components.sast` | 0–100 | SAST/代码审查检查或工作流 |
| `features.security_components.workflow_hygiene` | 0–100 | 依赖固定、分支保护或工作流卫生 |

安全子项权重为：Scorecard 60%、安全政策 10%、依赖更新 10%、SAST/代码审查 10%、工作流卫生 10%。

## 4. 结果字段与缺失语义

| 返回字段 | 说明 |
| --- | --- |
| `scores.*` | 五维当前分，0–100；不可计算时为 `null` |
| `scores.comprehensive` | 当前即时综合分；排名唯一使用该字段 |
| `completeness` | 按五维权重计算的证据完整度，0–1 |
| `confidence` | 当前实现中不超过 `completeness` 的置信度，0–1 |
| `risks` | 由当前分和证据触发的风险列表 |
| `evidence` | 计算所用原始证据与派生特征 |
| `source_status` | GitHub、Scorecard 等来源的可用状态 |
| `stale` | 快照过期或最近一次体检有错误 |

`null` 表示没有足够证据，不等于 0 分。前端应显示“暂无数据”，建议规则应标记为“证据不足”，不得据此断言项目存在问题。

## 5. 月度指标与即时指标的边界

月度接口保留历史趋势、异常检测和指标下钻能力，常见字段包括 `activity`、`openrank`、`contributors`、`bus_factor`、`issues_new`、`issues_closed`、`prs_new` 和 `scorecard_score`。这些字段不能替代 `current-v1` 的即时分。

如果即时快照和月度历史同日出现差异，显示层按以下优先级处理：

1. 当前综合分和当前五维分：`/health/current` 的 `current-v1`；
2. 当前风险、完整度和证据：同一 `current-v1` 响应；
3. 趋势、历史对比和月度原始指标：月度历史接口。