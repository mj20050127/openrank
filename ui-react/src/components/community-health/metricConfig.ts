import type { DimensionKey, MetricDirection } from './types.ts';

export const ATLAS_THEME = Object.freeze({
  background: '#f4f0e5',
  panel: '#f8f5ec',
  ink: '#173b32',
  text: '#1f2925',
  muted: '#6d756f',
  rule: 'rgba(23, 59, 50, 0.28)',
  grid: 'rgba(23, 59, 50, 0.10)',
  teal: '#2b8f83',
  tealLight: '#9bcfc7',
  blue: '#6f98c8',
  orange: '#d77b43',
  red: '#b84935',
  neutral: '#e8e2d4',
  tooltip: '#f8f5ec',
});

export const HEALTH_SCALE = ['#b84935', '#e59a72', '#eee9dc', '#92c9c1', '#2b8f83'];
export const BUS_FACTOR_THRESHOLD = 3;
export const CHART_GROUP_ID = 'community-health-evolution';

/** The current-v1 backend score is the authority for the live five-dimension score. */
export const CURRENT_SCORE_WEIGHTS = Object.freeze({
  activity: 0.30,
  responsiveness: 0.25,
  resilience: 0.20,
  governance: 0.15,
  security: 0.10,
});

export interface MetricDefinition {
  key: string;
  label: string;
  direction: MetricDirection;
  unit?: string;
  source: string;
  threshold?: number;
  derivedFrom?: [string, string];
  formula?: string;
  transform?: (value: number) => number;
  scoreKey?: string;
}

export interface DimensionDefinition {
  dimension: DimensionKey;
  label: string;
  weight: number;
  metrics: MetricDefinition[];
}

const OPENDIGGER_SOURCE = 'OpenDigger 月度指标';

export const GOVERNANCE_METRICS: DimensionDefinition[] = [
  {
    dimension: 'activity',
    label: '活跃度',
    weight: CURRENT_SCORE_WEIGHTS.activity,
    metrics: [
      { key: 'openrank', label: 'OpenRank', direction: 'positive', source: OPENDIGGER_SOURCE },
      { key: 'activity', label: '活跃度', direction: 'positive', source: OPENDIGGER_SOURCE },
      { key: 'contributors', label: '活跃贡献者', direction: 'positive', unit: '人', source: OPENDIGGER_SOURCE },
      { key: 'attention', label: '社区关注度', direction: 'positive', source: OPENDIGGER_SOURCE },
    ],
  },
  {
    dimension: 'responsiveness',
    label: '响应度',
    weight: CURRENT_SCORE_WEIGHTS.responsiveness,
    metrics: [
      { key: 'issue_response_time', label: '首次响应时间', direction: 'negative', unit: '小时', source: OPENDIGGER_SOURCE },
      { key: 'issue_resolution_duration', label: '问题解决时间', direction: 'negative', unit: '小时', source: OPENDIGGER_SOURCE },
      {
        key: 'issue_age',
        label: '未解决问题年龄',
        direction: 'negative',
        unit: '天',
        source: OPENDIGGER_SOURCE,
        transform: (hours) => hours / 24,
      },
    ],
  },
  {
    dimension: 'resilience',
    label: '韧性',
    weight: CURRENT_SCORE_WEIGHTS.resilience,
    metrics: [
      { key: 'new_contributors', label: '新贡献者', direction: 'positive', unit: '人', source: OPENDIGGER_SOURCE },
      { key: 'inactive_contributors', label: '不活跃贡献者', direction: 'negative', unit: '人', source: OPENDIGGER_SOURCE },
      { key: 'bus_factor', label: 'Bus Factor', direction: 'positive', source: OPENDIGGER_SOURCE, threshold: BUS_FACTOR_THRESHOLD },
      { key: 'participants', label: '参与者', direction: 'positive', unit: '人', source: OPENDIGGER_SOURCE },
    ],
  },
  {
    dimension: 'governance',
    label: '治理',
    weight: CURRENT_SCORE_WEIGHTS.governance,
    metrics: [
      {
        key: 'issue_close_rate',
        label: 'Issue 关闭率',
        direction: 'positive',
        unit: '%',
        source: '由 OpenDigger issues_closed / issues_new 派生',
        derivedFrom: ['issues_closed', 'issues_new'],
        formula: 'issues_closed / issues_new',
      },
      {
        key: 'change_request_acceptance_rate',
        label: '变更接受率',
        direction: 'positive',
        unit: '%',
        source: '由 OpenDigger change_requests_accepted / change_requests 派生',
        derivedFrom: ['change_requests_accepted', 'change_requests'],
        formula: 'change_requests_accepted / change_requests',
      },
      { key: 'change_requests_reviews', label: '代码审查量', direction: 'positive', unit: '次', source: OPENDIGGER_SOURCE },
    ],
  },
  {
    dimension: 'security',
    label: '安全',
    weight: CURRENT_SCORE_WEIGHTS.security,
    metrics: [
      {
        key: 'security_score',
        label: '安全综合得分',
        direction: 'positive',
        unit: '分',
        source: '月度 Git 历史 / OpenSSF 审计',
        scoreKey: 'security',
      },
    ],
  },
];

export const REQUIRED_HISTORY_METRICS = [...new Set([
  ...GOVERNANCE_METRICS.flatMap((group) => group.metrics.flatMap((metric) => metric.derivedFrom || (metric.scoreKey ? [] : [metric.key]))),
  'new_contributors',
  'inactive_contributors',
  'contributors',
  'bus_factor',
])];
