export type DimensionKey = 'activity' | 'responsiveness' | 'resilience' | 'governance' | 'security';

export type MetricDirection = 'positive' | 'negative';

export interface MonthlyMetricPoint {
  month: string;
  value: number | null;
  rawValue: number | null;
  visualValue: number | null;
  robustZ: number | null;
  healthZ: number | null;
  median: number | null;
  anomaly: boolean;
  missing: boolean;
  violation: boolean;
  source: string;
  numerator?: number | null;
  denominator?: number | null;
  formula?: string;
}

export interface GovernanceMetric {
  key: string;
  label: string;
  dimension: DimensionKey;
  dimensionLabel: string;
  direction: MetricDirection;
  weight: number;
  unit?: string;
  source: string;
  points: MonthlyMetricPoint[];
}

export interface EcosystemEvent {
  id: string;
  month: string;
  type: 'release' | 'security' | 'maintainer' | 'governance';
  label: string;
}

export interface TalentMonthlyPoint {
  month: string;
  newContributors: number | null;
  inactiveContributors: number | null;
  inactiveContributorsSnapshot?: number | null;
  activeContributors: number | null;
  busFactor: number | null;
  netFlow: number | null;
}

export interface MonthRange {
  startMonth: string;
  endMonth: string;
  length: number;
  totalNetFlow?: number;
}

export interface SharedChartProps {
  selectedMonth: string | null;
  onSelectedMonthChange(month: string): void;
  rangeStart: string | null;
  rangeEnd: string | null;
  onRangeChange(start: string, end: string): void;
}
