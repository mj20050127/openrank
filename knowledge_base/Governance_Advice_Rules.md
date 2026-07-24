# Governance Advice Rules

## 1. 目标与适用范围

本规则把 `current-v1` 即时体检中的风险和证据转换为可执行的治理建议。建议必须能回溯到当前快照的 `scores`、`risks`、`evidence` 或 `features`；没有证据时只提示补采集，不生成确定性结论。

建议的目标是形成“发现问题 → 指定责任动作 → 验收指标 → 下一次体检复核”的闭环，而不是单纯重复分数。

## 2. 优先级与通用阈值

### 2.1 风险级别

后端当前风险分级：

| 条件 | 级别 | 建议处理时限 |
| --- | --- | --- |
| 任一维度 `< 40` | 高风险 | 纳入本周治理计划，明确负责人 |
| 任一维度 `40–<60` | 中风险 | 纳入近期迭代，通常 30 天内复核 |
| 任一维度 `>= 60` | 不触发分数风险建议 | 继续观察趋势和证据 |
| `push_age_days > 30` | 中风险 | 检查维护节奏和发布计划 |
| Scorecard 当前证据不可用 | 未知 | 先补充审计证据，不把未知当作安全或不安全 |

同一维度同时命中多个规则时，只输出一条合并建议：优先保留严重级别最高、证据最具体、验收最容易量化的动作。

### 2.2 建议排序

按以下顺序排序：

1. 高风险维度；
2. 安全和供应链证据缺口；
3. 响应队列和积压年龄；
4. 贡献集中度和 Bus Factor；
5. 治理文件与流程完善；
6. 活跃度和维护节奏优化。

若高风险建议超过 3 条，先输出最影响综合分的 3 条，其余标记为“后续治理项”。综合分影响可按维度权重估算：活跃度 30%、响应度 25%、韧性 20%、治理 15%、安全 10%。

## 3. 规则表

### G-01 活跃度不足或维护停滞

- 触发：`scores.vitality < 60`，或 `features.push_age_days > 30`。
- 证据：`commits_current`、`commits_previous`、`active_weeks`、`push_age_days`、`active_contributors`。
- 建议动作：建立每周维护节奏；安排 Issue triage、PR review 和版本发布负责人；为长期未处理任务设置批次清理计划。
- 验收指标：下一窗口活跃周比例提升；默认分支推送间隔回到 30 天以内；提交或已处理协作任务不再持续下降。
- 注意：不能仅凭提交量少断定项目不健康；若 `weeks_observed` 或贡献者数据不足，先提示补采集。

### G-02 协作响应效率不足

- 触发：`scores.responsiveness < 60`，或 `features.issue_flow_score < 60`，或 `features.pr_flow_score < 60`。
- 证据：`issues_opened`、`issues_closed`、`prs_opened`、`prs_merged`、`open_issue_median_age_days`、`open_pr_median_age_days`。
- 建议动作：设置 Issue/PR triage 值班；为新任务增加首次响应 SLA；按标签分派 reviewer；优先清理超过年龄阈值的开放队列。
- 验收指标：Issue 流转分和 PR 流转分提升；开放 Issue 中位年龄低于 180 天；开放 PR 中位年龄低于 120 天。
- 注意：当新增量为 0 时，流转率不是有效的“100% 效率”证据，应在建议中说明样本不足。

### G-03 社区贡献过度集中

- 触发：`scores.resilience < 60`，或 `features.concentration_score < 50`，或 `contributors.top1_share > 0.50`，或 `contributors.bus_factor < 3`。
- 证据：`top1_share`、`bus_factor`、`active_contributors`、`total_contributions`。
- 建议动作：建立双人 review 和知识交接；把可拆分任务标注为 `good first issue`/`help wanted`；邀请第二梯队贡献者共同维护关键模块；补充贡献指南。
- 验收指标：Top1 占比下降；Bus Factor 达到至少 3；活跃贡献者数连续窗口不下降。
- 注意：贡献者样本被截断时，应把结论标为低置信度，并优先扩大采样。

### G-04 治理文件缺失

- 触发：`features.governance_file_score < 80`，或以下任一关键文件缺失：`readme`、`license`、`contributing`、`code_of_conduct`、`security`、`issue_template`、`pull_request_template`。
- 证据：`evidence.governance.files` 与 `features.governance_file_score`。
- 建议动作：按缺失项补齐 README、LICENSE、CONTRIBUTING、行为准则、安全政策和 Issue/PR 模板；将 CODEOWNERS/GOVERNANCE 作为团队协作扩展项。
- 验收指标：关键文件全部可发现；治理文件分达到 80 分以上；新贡献者能够从文档找到开发、测试和提交规范。
- 注意：文件存在不代表内容有效；内容质量需要后续人工审阅或专门检查。

### G-05 治理流程不透明

- 触发：`scores.governance < 60`，或 `features.governance_process_score < 60`。
- 证据：Issue/PR 流转分、开放队列年龄、模板和协作文件状态。
- 建议动作：公开 triage 节奏和维护者职责；明确 PR review、合并和发布规则；为长期开放任务设置状态、负责人和下一步。
- 验收指标：治理流程分提升；Issue/PR 年龄分改善；模板和责任人信息在仓库内可直接找到。

### G-06 安全审计或供应链证据不足

- 触发：`scores.security < 60`，或 `features.scorecard_component < 60`，或 `scorecard` 来源状态为不可用。
- 证据：`scorecard.score`、`features.security_components`、`governance.files.security`、工作流卫生分。
- 建议动作：先恢复 OpenSSF Scorecard 采集；补充 SECURITY.md；启用依赖自动更新和依赖版本固定；补充 SAST/代码审查与分支保护工作流。
- 验收指标：Scorecard 可成功获取且达到 6/10 以上；安全政策存在；依赖更新、SAST/审查和工作流卫生组件不再为 0。
- 注意：Scorecard 缺失是“未知”，不是“安全分为 0”；建议应先写补证据动作。

### G-07 当前体检完整度不足

- 触发：`completeness < 0.80`，或任一 `scores.*` 为 `null`。
- 证据：`completeness`、`confidence`、`source_status`、`last_error`。
- 建议动作：显示缺失来源和失败原因；重试对应的 GitHub/Scorecard 采集；在证据恢复前不做跨仓库强排名结论。
- 验收指标：五维分全部可计算；完整度达到 80% 以上；下一次体检不再有对应来源错误。

## 4. 建议输出格式

每条建议至少包含以下字段：

```json
{
  "rule_id": "G-02",
  "dimension": "responsiveness",
  "level": "medium",
  "title": "缩短 Issue/PR 处理队列",
  "evidence": [
    {"field": "features.issue_flow_score", "value": 42.5},
    {"field": "evidence.collaboration.open_issue_median_age_days", "value": 196}
  ],
  "actions": ["安排每周 triage 值班", "优先处理超过 180 天的开放 Issue"],
  "acceptance": ["Issue 流转分提升", "开放 Issue 中位年龄低于 180 天"],
  "source": "current-v1"
}
```

前端展示时应同时显示规则标题、当前值、目标值和数据来源；点击建议应能定位到当前快照的证据字段。

## 5. 禁止事项

- 不得用月度历史分覆盖当前 `current-v1` 分数。
- 不得把 `null`、来源失败或样本不足解释为 0 分或高风险。
- 不得只给“提升活跃度”“加强治理”这类没有验收指标的泛化建议。
- 不得在没有当前证据时声称 Scorecard、流程文件或贡献者结构已经改善。
- 不得把仓库 Stars、Forks 直接当作健康分或治理质量分。