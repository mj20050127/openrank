import { GOVERNANCE_METRICS, type MetricDefinition } from './metricConfig.ts';
import type {
  EcosystemEvent,
  GovernanceMetric,
  MetricDirection,
  MonthRange,
  MonthlyMetricPoint,
  TalentMonthlyPoint,
} from './types.ts';

type HistoryRecord = Record<string, unknown> & {
  dt?: string;
  metric_month?: string;
  metrics?: Record<string, unknown>;
  scores?: Record<string, unknown>;
};

type RawPoint = {
  month: string;
  value: number | null;
  rawValue?: number | null;
  anomaly?: boolean;
  violation?: boolean;
  source?: string;
  numerator?: number | null;
  denominator?: number | null;
  formula?: string;
  normalizedScore?: number | null;
};

export function finiteOrNull(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

export function monthKey(value: unknown): string | null {
  if (!value) return null;
  const rendered = String(value).slice(0, 7);
  return /^\d{4}-\d{2}$/.test(rendered) ? rendered : null;
}

export function median(values: number[]): number | null {
  if (!values.length) return null;
  const ordered = [...values].sort((left, right) => left - right);
  const middle = Math.floor(ordered.length / 2);
  return ordered.length % 2 ? ordered[middle] : (ordered[middle - 1] + ordered[middle]) / 2;
}

function standardDeviation(values: number[]): { mean: number; deviation: number } {
  if (!values.length) return { mean: 0, deviation: 0 };
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
  return { mean, deviation: Math.sqrt(variance) };
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}

export function normalizeMetricSeries(points: RawPoint[], direction: MetricDirection): MonthlyMetricPoint[] {
  const values = points.map((point) => point.value).filter((value): value is number => value !== null);
  const baseline = median(values);
  const mad = baseline === null ? null : median(values.map((value) => Math.abs(value - baseline)));
  const fallback = standardDeviation(values);

  return points.map((point) => {
    if (point.value === null) {
      return {
        month: point.month,
        value: null,
        rawValue: point.rawValue ?? null,
        visualValue: null,
        robustZ: null,
        healthZ: null,
        median: baseline,
        anomaly: false,
        missing: true,
        violation: false,
        source: point.source || '暂无数据',
        numerator: point.numerator,
        denominator: point.denominator,
        formula: point.formula,
      };
    }

    let robustZ = 0;
    if (baseline !== null && mad !== null && mad > 0) {
      robustZ = 0.6745 * (point.value - baseline) / mad;
    } else if (fallback.deviation > 0) {
      robustZ = (point.value - fallback.mean) / fallback.deviation;
    }
    const healthZ = direction === 'negative' ? -robustZ : robustZ;
    const scoreVisual = point.normalizedScore === null || point.normalizedScore === undefined
      ? null
      : clamp((point.normalizedScore - 50) / 50, -1, 1);
    const visualValue = scoreVisual ?? clamp(healthZ / 3, -1, 1);

    return {
      month: point.month,
      value: point.value,
      rawValue: point.rawValue ?? point.value,
      visualValue,
      robustZ,
      healthZ: scoreVisual === null ? healthZ : scoreVisual * 3,
      median: baseline,
      anomaly: Boolean(point.anomaly) || Math.abs(robustZ) >= 2.5,
      missing: false,
      violation: Boolean(point.violation),
      source: point.source || 'OpenDigger 月度指标',
      numerator: point.numerator,
      denominator: point.denominator,
      formula: point.formula,
    };
  });
}

function valueFor(record: HistoryRecord, key: string): number | null {
  return finiteOrNull(record.metrics?.[key] ?? record[key]);
}

function normalizedScoreFor(record: HistoryRecord, metric: MetricDefinition): number | null {
  if (metric.scoreKey) return finiteOrNull(record.scores?.[metric.scoreKey]);
  const metricScores = record.metric_scores as Record<string, unknown> | undefined;
  const normalizedScores = record.normalized_scores as Record<string, unknown> | undefined;
  return finiteOrNull(metricScores?.[metric.key] ?? normalizedScores?.[metric.key]);
}

function flagFor(record: HistoryRecord, bucket: string, key: string): boolean {
  const flags = record[bucket];
  if (Array.isArray(flags)) return flags.includes(key);
  if (flags && typeof flags === 'object') return Boolean((flags as Record<string, unknown>)[key]);
  const metadata = record.metric_meta as Record<string, Record<string, unknown>> | undefined;
  return Boolean(metadata?.[key]?.[bucket === 'anomalies' ? 'anomaly' : 'violation']);
}

function sourceFor(record: HistoryRecord, metric: MetricDefinition): string {
  const sources = record.sources as Record<string, unknown> | undefined;
  return String(sources?.[metric.key] || metric.source);
}

function rawPointFor(record: HistoryRecord, month: string, metric: MetricDefinition): RawPoint {
  const anomaly = flagFor(record, 'anomalies', metric.key);
  const explicitViolation = flagFor(record, 'violations', metric.key);
  const normalizedScore = normalizedScoreFor(record, metric);

  if (metric.derivedFrom) {
    const numerator = valueFor(record, metric.derivedFrom[0]);
    const denominator = valueFor(record, metric.derivedFrom[1]);
    const ratio = numerator !== null && denominator !== null && denominator > 0
      ? (numerator / denominator) * 100
      : null;
    return {
      month,
      value: ratio,
      rawValue: ratio,
      anomaly,
      violation: explicitViolation,
      source: sourceFor(record, metric),
      numerator,
      denominator,
      formula: metric.formula,
      normalizedScore,
    };
  }

  const sourceValue = metric.scoreKey ? normalizedScore : valueFor(record, metric.key);
  const value = sourceValue === null ? null : metric.transform ? metric.transform(sourceValue) : sourceValue;
  const thresholdViolation = metric.threshold === undefined || value === null
    ? false
    : metric.direction === 'negative' ? value > metric.threshold : value < metric.threshold;
  return {
    month,
    value,
    rawValue: sourceValue,
    anomaly,
    violation: explicitViolation || thresholdViolation,
    source: sourceFor(record, metric),
    normalizedScore,
  };
}

export function alignMonthlyRecords(records: HistoryRecord[]): { months: string[]; recordsByMonth: Map<string, HistoryRecord> } {
  const recordsByMonth = new Map<string, HistoryRecord>();
  for (const record of records || []) {
    const month = monthKey(record.dt || record.metric_month);
    if (month) recordsByMonth.set(month, record);
  }
  return { months: [...recordsByMonth.keys()].sort(), recordsByMonth };
}

export function buildGovernancePulseData(records: HistoryRecord[]): { months: string[]; metrics: GovernanceMetric[] } {
  const { months, recordsByMonth } = alignMonthlyRecords(records);
  const metrics = GOVERNANCE_METRICS.flatMap((group) => group.metrics.map((metric) => {
    const rawPoints = months.map((month) => rawPointFor(recordsByMonth.get(month) || {}, month, metric));
    return {
      key: metric.key,
      label: metric.label,
      dimension: group.dimension,
      dimensionLabel: group.label,
      direction: metric.direction,
      weight: group.weight,
      unit: metric.unit,
      source: metric.source,
      points: normalizeMetricSeries(rawPoints, metric.direction),
    } satisfies GovernanceMetric;
  }));
  return { months, metrics };
}

/**
 * Convert the monthly inactive-contributor snapshot into people entering the
 * inactive state during that month. The source field is a repeated snapshot,
 * so using it directly would count the same person again every month.
 * A missing snapshot breaks the baseline instead of being treated as zero.
 */
export function deriveUniqueInactiveFlow(snapshots: Array<number | null>): Array<number | null> {
  let previous: number | null = null;
  return snapshots.map((snapshot) => {
    if (snapshot === null) {
      previous = null;
      return null;
    }
    const flow = previous === null ? null : Math.max(0, snapshot - previous);
    previous = snapshot;
    return flow;
  });
}

export function buildTalentBalanceData(records: HistoryRecord[]): TalentMonthlyPoint[] {
  const { months, recordsByMonth } = alignMonthlyRecords(records);
  const snapshots = months.map((month) => valueFor(recordsByMonth.get(month) || {}, 'inactive_contributors'));
  const inactiveFlows = deriveUniqueInactiveFlow(snapshots);
  return months.map((month, index) => {
    const record = recordsByMonth.get(month) || {};
    const newContributors = valueFor(record, 'new_contributors');
    const inactiveContributors = inactiveFlows[index];
    return {
      month,
      newContributors,
      inactiveContributors,
      inactiveContributorsSnapshot: snapshots[index],
      activeContributors: valueFor(record, 'contributors'),
      busFactor: valueFor(record, 'bus_factor'),
      netFlow: newContributors !== null && inactiveContributors !== null
        ? newContributors - inactiveContributors
        : null,
    };
  });
}

function nextMonth(month: string): string {
  const [year, monthNumber] = month.split('-').map(Number);
  const date = new Date(Date.UTC(year, monthNumber, 1));
  return `${date.getUTCFullYear()}-${String(date.getUTCMonth() + 1).padStart(2, '0')}`;
}

function mergeRanges<T>(points: T[], isRisk: (point: T) => boolean, monthOf: (point: T) => string): Array<{ start: number; end: number }> {
  const ranges: Array<{ start: number; end: number }> = [];
  let start = -1;
  for (let index = 0; index <= points.length; index += 1) {
    const currentRisk = index < points.length && isRisk(points[index]);
    const followsPrevious = index > 0 && index < points.length && nextMonth(monthOf(points[index - 1])) === monthOf(points[index]);
    if (currentRisk && start < 0) start = index;
    if (currentRisk && start >= 0 && index > start && !followsPrevious) {
      ranges.push({ start, end: index - 1 });
      start = index;
    }
    if (!currentRisk && start >= 0) {
      ranges.push({ start, end: index - 1 });
      start = -1;
    }
  }
  return ranges;
}

export function findNegativeNetFlowRanges(points: TalentMonthlyPoint[], minLength = 3): MonthRange[] {
  return mergeRanges(points, (point) => point.netFlow !== null && point.netFlow < 0, (point) => point.month)
    .filter((range) => range.end - range.start + 1 >= minLength)
    .map((range) => ({
      startMonth: points[range.start].month,
      endMonth: points[range.end].month,
      length: range.end - range.start + 1,
      totalNetFlow: points.slice(range.start, range.end + 1).reduce((sum, point) => sum + (point.netFlow || 0), 0),
    }));
}

export function buildBusFactorRiskRanges(points: TalentMonthlyPoint[], threshold: number): MonthRange[] {
  return mergeRanges(points, (point) => point.busFactor !== null && point.busFactor < threshold, (point) => point.month)
    .map((range) => ({
      startMonth: points[range.start].month,
      endMonth: points[range.end].month,
      length: range.end - range.start + 1,
    }));
}

export function latestValidMonth<T extends { month: string }>(points: T[], hasData: (point: T) => boolean): string | null {
  for (let index = points.length - 1; index >= 0; index -= 1) {
    if (hasData(points[index])) return points[index].month;
  }
  return null;
}

export function hasTalentData(points: TalentMonthlyPoint[]): boolean {
  return points.some((point) => [point.newContributors, point.inactiveContributors, point.inactiveContributorsSnapshot, point.activeContributors, point.busFactor].some((value) => value !== null));
}

export function normalizeEcosystemEvents(events: unknown[], validMonths: string[]): EcosystemEvent[] {
  const allowed = new Set(validMonths);
  return (events || []).map((raw, index) => {
    const event = (raw || {}) as Record<string, unknown>;
    const month = monthKey(event.month || event.date || event.occurred_at || event.created_at || event.dt);
    const rawType = String(event.type || event.event_type || event.kind || '').toLowerCase();
    const type = rawType.includes('release') || rawType.includes('version')
      ? 'release'
      : rawType.includes('security') || rawType.includes('cve')
        ? 'security'
        : rawType.includes('maintainer') || rawType.includes('member')
          ? 'maintainer'
          : rawType.includes('govern') || rawType.includes('policy')
            ? 'governance'
            : null;
    if (!month || !type || !allowed.has(month)) return null;
    return {
      id: String(event.id || event.event_id || `${type}-${month}-${index}`),
      month,
      type,
      label: String(event.label || event.title || event.summary || event.name || type),
    } satisfies EcosystemEvent;
  }).filter((event): event is EcosystemEvent => event !== null);
}
