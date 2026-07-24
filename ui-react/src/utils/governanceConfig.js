export const GOVERNANCE_THEME = {
  canvas: '#f4f7fb',
  panel: '#ffffff',
  panelStrong: '#172033',
  border: '#dce5ef',
  text: '#172033',
  muted: '#64748b',
  primary: '#2878e3',
  cyan: '#0f9f9a',
  success: '#1a9a67',
  warning: '#d98521',
  risk: '#d94f66',
  grid: 'rgba(100, 116, 139, 0.18)',
  tooltip: '#172033',
};

export const DIMENSIONS = {
  vitality: {
    label: '活跃度',
    scoreKey: 'vitality',
    color: '#2878e3',
    description: '衡量项目的影响力、活跃投入与社区增长。',
    metrics: ['openrank', 'activity'],
    detail: {
      meaning: '衡量仓库在最近 90 天是否持续产生开发活动，以及当前活跃水平相较上一周期是在增长还是衰退。',
      formula: '活跃度 = 30% × 提交动量 + 25% × 活跃周覆盖 + 20% × 最近推送 + 15% × 协作吞吐动量 + 10% × 活跃贡献者',
      components: [
        { name: '提交动量', weight: '30%', formula: '50 + 50 × tanh((本期提交 − 上期提交) ÷ |上期提交|)', note: '比较相邻两个 90 天窗口；持平约为 50 分，增长趋近 100 分。' },
        { name: '活跃周覆盖', weight: '25%', formula: '100 × 活跃周数 ÷ 已观测周数', note: '有提交的周越连续，分数越高。' },
        { name: '最近推送', weight: '20%', formula: '100 × (1 − min(距最近推送天数, 90) ÷ 90)', note: '最近有推送得分更高，90 天未推送时降至 0 分。' },
        { name: '协作吞吐动量', weight: '15%', formula: '对 Issue 与 PR 新增总量使用动量公式', note: '反映协作事项的近期变化趋势。' },
        { name: '活跃贡献者', weight: '10%', formula: '100 × ln(1 + 人数) ÷ ln(101)', note: '采用对数缩放，避免超大型社区对分数形成数量级碾压。' },
      ],
      note: '所有子项限制在 0–100 分。可用指标权重达到 80% 才计算，缺失项会按剩余权重重新归一化。',
    },
  },
  responsiveness: {
    label: '响应度',
    scoreKey: 'responsiveness',
    color: '#0f9f9a',
    description: '衡量 Issue 与 PR 得到回应和关闭的效率。',
    metrics: ['issues_new', 'issues_closed', 'change_requests', 'change_requests_accepted'],
    detail: {
      meaning: '衡量维护者处理 Issue 与 PR 的效率，兼顾事项消化能力和当前积压事项的等待时长。',
      formula: '响应度 = 30% × Issue 流转 + 30% × PR 流转 + 20% × Issue 时效 + 20% × PR 时效',
      components: [
        { name: 'Issue 流转', weight: '30%', formula: '100 × 已关闭 Issue ÷ 新增 Issue', note: '达到或超过 100% 时记为 100 分。' },
        { name: 'PR 流转', weight: '30%', formula: '100 × (已合并 PR ÷ 新增 PR) ÷ 80%', note: '以 80% 合并率作为满分目标。' },
        { name: 'Issue 时效', weight: '20%', formula: '100 × (1 − min(未关闭 Issue 中位年龄, 180) ÷ 180)', note: '积压 Issue 越年轻，分数越高。' },
        { name: 'PR 时效', weight: '20%', formula: '100 × (1 − min(未关闭 PR 中位年龄, 120) ÷ 120)', note: '积压 PR 达到 120 天时该项为 0 分。' },
      ],
      note: '所有子项限制在 0–100 分。可用指标权重达到 80% 才计算，缺失项会按剩余权重重新归一化。',
    },
  },
  resilience: {
    label: '韧性',
    scoreKey: 'resilience',
    color: '#7557d5',
    description: '衡量关键贡献依赖、人才留存和社区抗波动能力。',
    metrics: ['contributors', 'new_contributors', 'bus_factor'],
    detail: {
      meaning: '衡量项目能否承受核心成员离开或短期活动波动，重点观察贡献是否过度集中以及社区是否持续活跃。',
      formula: '韧性 = 35% × Bus Factor + 30% × 贡献分散度 + 20% × 活跃贡献者 + 15% × 活跃周覆盖',
      components: [
        { name: 'Bus Factor', weight: '35%', formula: '100 × ln(1 + Bus Factor) ÷ ln(11)', note: '关键贡献者越多，项目对单点人员风险越不敏感。' },
        { name: '贡献分散度', weight: '30%', formula: '100 × (1 − Top1 贡献占比)', note: '第一贡献者占比越低，贡献结构越均衡。' },
        { name: '活跃贡献者', weight: '20%', formula: '100 × ln(1 + 人数) ÷ ln(101)', note: '衡量近期仍在参与项目的贡献者规模。' },
        { name: '活跃周覆盖', weight: '15%', formula: '100 × 活跃周数 ÷ 已观测周数', note: '持续活跃能降低偶发高峰造成的误判。' },
      ],
      note: '所有子项限制在 0–100 分。可用指标权重达到 80% 才计算，缺失项会按剩余权重重新归一化。',
    },
  },
  governance: {
    label: '治理',
    scoreKey: 'governance',
    color: '#d98521',
    description: '衡量协作队列管理、流程与治理基础能力。',
    metrics: ['issues_closed', 'change_requests_accepted', 'change_requests_reviews'],
    detail: {
      meaning: '衡量项目是否既能有效处理协作事项，又具备清晰、完整且可执行的社区治理规范。',
      formula: '治理 = 60% × 协作流程分 + 40% × 治理文件分',
      components: [
        { name: '协作流程', weight: '60%', formula: '40% × Issue 流转 + 40% × PR 流转 + 10% × Issue 时效 + 10% × PR 时效', note: '沿用响应度中的流转率与积压年龄评分。' },
        { name: '基础治理文件', weight: '40%', formula: '存在即累加：README 10、LICENSE 15、CONTRIBUTING 20、行为准则 15、安全策略 10、Issue 模板 10、PR 模板 10、治理说明 5、CODEOWNERS 5', note: '文件权重合计 100 分，强调贡献指南、许可证和行为准则。' },
      ],
      note: '协作流程的可用指标权重需达到 80%；治理文件由仓库默认分支当前内容检测。',
    },
  },
  security: {
    label: '安全',
    scoreKey: 'security',
    color: '#1a9a67',
    description: '衡量安全实践与供应链检查的覆盖情况。',
    metrics: ['code_change_lines_add', 'code_change_lines_remove'],
    detail: {
      meaning: '衡量仓库的软件供应链防护、安全策略和自动化安全检查是否形成完整闭环。',
      formula: '安全 = 60% × OpenSSF Scorecard + 10% × 安全策略 + 10% × 依赖更新 + 10% × SAST / 代码审查 + 10% × 工作流安全',
      components: [
        { name: 'OpenSSF Scorecard', weight: '60%', formula: 'Scorecard 原始分（0–10）× 10', note: '作为供应链安全实践的核心综合证据。' },
        { name: '安全策略', weight: '10%', formula: '存在 SECURITY 文件为 100 分，否则为 0 分', note: '检查漏洞报告渠道是否明确。' },
        { name: '依赖更新', weight: '10%', formula: 'Dependency-Update-Tool 检查分', note: '不可用时回退检查 Dependabot 等依赖更新配置。' },
        { name: 'SAST / 代码审查', weight: '10%', formula: 'SAST 或 Code-Review 检查分', note: '不可用时回退检查仓库工作流。' },
        { name: '工作流安全', weight: '10%', formula: 'Pinned-Dependencies / Branch-Protection 检查分', note: '不可用时采用工作流卫生评分。' },
      ],
      note: '所有子项统一换算为 0–100 分。可用指标权重达到 80% 才计算，缺失项会按剩余权重重新归一化。',
    },
  },
};

export const METRICS = {
  score_health: { label: '当前健康分', unit: '分', betterWhen: 'higher', threshold: 70, source: 'current-v1 当前体检' },
  score_vitality: { label: '活跃与影响力', unit: '分', betterWhen: 'higher', threshold: 60, source: 'GitHub 最近 90 天窗口' },
  score_responsiveness: { label: '协作响应力', unit: '分', betterWhen: 'higher', threshold: 60, source: 'GitHub 最近 90 天协作窗口' },
  score_resilience: { label: '社区韧性', unit: '分', betterWhen: 'higher', threshold: 60, source: 'GitHub 最近 90 天贡献统计' },
  score_governance: { label: '治理成熟度', unit: '分', betterWhen: 'higher', threshold: 60, source: '当前协作流程与治理文件' },
  score_security: { label: '安全能力', unit: '分', betterWhen: 'higher', threshold: 60, source: '当前 GitHub / OpenSSF 审计' },
  activity: { label: '活跃度', unit: '', betterWhen: 'higher', source: 'OpenDigger 月度指标' },
  openrank: { label: 'OpenRank', unit: '', betterWhen: 'higher', source: 'OpenDigger 月度指标' },
  contributors: { label: '贡献者数', unit: '人', betterWhen: 'higher', source: 'OpenDigger 月度指标' },
  new_contributors: { label: '新贡献者', unit: '人', betterWhen: 'higher', source: 'OpenDigger 月度指标' },
  issue_response_time_h: { label: 'Issue 首次响应', unit: '小时', betterWhen: 'lower', threshold: 48, source: 'OpenDigger / 代理换算' },
  pr_response_time_h: { label: 'PR 首次响应', unit: '小时', betterWhen: 'lower', threshold: 48, source: 'OpenDigger / 代理换算' },
  issue_resolution_duration_h: { label: 'Issue 关闭周期', unit: '小时', betterWhen: 'lower', threshold: 168, source: 'OpenDigger / 代理换算' },
  pr_resolution_duration_h: { label: 'PR 关闭周期', unit: '小时', betterWhen: 'lower', threshold: 168, source: 'OpenDigger / 代理换算' },
  bus_factor: { label: 'Bus Factor', unit: '', betterWhen: 'higher', threshold: 3, source: 'OpenDigger 月度指标' },
  top1_share: { label: 'Top1 贡献占比', unit: '%', betterWhen: 'lower', threshold: 50, source: 'OpenDigger 月度指标' },
  hhi: { label: '贡献集中度 HHI', unit: '', betterWhen: 'lower', threshold: 2500, source: 'OpenDigger 月度指标' },
  retention_rate: { label: '贡献者留存率（代理）', unit: '%', betterWhen: 'higher', threshold: 50, source: '基于活跃贡献者估算' },
  issues_new: { label: '新增 Issue', unit: '项', betterWhen: 'neutral', source: 'OpenDigger 月度指标' },
  issues_closed: { label: '关闭 Issue', unit: '项', betterWhen: 'higher', source: 'OpenDigger 月度指标' },
  prs_new: { label: '新增 PR', unit: '项', betterWhen: 'neutral', source: 'OpenDigger 月度指标' },
  change_requests_accepted: { label: '合并 PR', unit: '项', betterWhen: 'higher', source: 'OpenDigger 月度指标' },
  scorecard_score: { label: '安全 Scorecard', unit: '分', betterWhen: 'higher', threshold: 7, source: 'OpenSSF Scorecard' },
};

export const RANGE_OPTIONS = [
  { value: '12', label: '12个月' },
  { value: '24', label: '24个月' },
  { value: '36', label: '36个月' },
  { value: '60', label: '60个月' },
  { value: 'all', label: '全部历史' },
];

export function valueFor(record, key) {
  if (!record) return null;
  if (key.startsWith('score_')) return record.scores?.[key.slice(6)] ?? null;
  return record.metrics?.[key] ?? null;
}