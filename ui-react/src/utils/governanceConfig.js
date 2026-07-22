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
  },
  responsiveness: {
    label: '响应度',
    scoreKey: 'responsiveness',
    color: '#0f9f9a',
    description: '衡量 Issue 与 PR 得到回应和关闭的效率。',
    metrics: ['issues_new', 'issues_closed', 'change_requests', 'change_requests_accepted'],
  },
  resilience: {
    label: '韧性',
    scoreKey: 'resilience',
    color: '#7557d5',
    description: '衡量关键贡献依赖、人才留存和社区抗波动能力。',
    metrics: ['contributors', 'new_contributors', 'bus_factor'],
  },
  governance: {
    label: '治理',
    scoreKey: 'governance',
    color: '#d98521',
    description: '衡量协作队列管理、流程与治理基础能力。',
    metrics: ['issues_closed', 'change_requests_accepted', 'change_requests_reviews'],
  },
  security: {
    label: '安全',
    scoreKey: 'security',
    color: '#1a9a67',
    description: '衡量安全实践与供应链检查的覆盖情况。',
    metrics: ['code_change_lines_add', 'code_change_lines_remove'],
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