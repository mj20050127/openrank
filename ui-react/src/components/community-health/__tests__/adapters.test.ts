import test from 'node:test';
import assert from 'node:assert/strict';
import {
  alignMonthlyRecords,
  buildBusFactorRiskRanges,
  buildGovernancePulseData,
  buildTalentBalanceData,
  deriveUniqueInactiveFlow,
  findNegativeNetFlowRanges,
  hasTalentData,
  latestValidMonth,
  normalizeMetricSeries,
} from '../adapters.ts';

const rawPoint = (month: string, value: number | null) => ({ month, value });

test('正向指标升高映射为治理改善', () => {
  const points = normalizeMetricSeries([rawPoint('2026-01', 10), rawPoint('2026-02', 20), rawPoint('2026-03', 30)], 'positive');
  assert.ok((points[2].visualValue ?? 0) > 0);
  assert.ok((points[0].visualValue ?? 0) < 0);
});

test('负向指标升高映射为治理恶化', () => {
  const points = normalizeMetricSeries([rawPoint('2026-01', 10), rawPoint('2026-02', 20), rawPoint('2026-03', 30)], 'negative');
  assert.ok((points[2].visualValue ?? 0) < 0);
  assert.ok((points[0].visualValue ?? 0) > 0);
});

test('MAD 为 0 时回退到标准差', () => {
  const points = normalizeMetricSeries([
    rawPoint('2026-01', 10), rawPoint('2026-02', 10), rawPoint('2026-03', 10), rawPoint('2026-04', 20),
  ], 'positive');
  assert.ok((points[3].robustZ ?? 0) > 0);
  assert.ok((points[3].visualValue ?? 0) > 0);
});

test('null 保持缺失且不会转成 0', () => {
  const points = normalizeMetricSeries([rawPoint('2026-01', null), rawPoint('2026-02', 8)], 'positive');
  assert.equal(points[0].value, null);
  assert.equal(points[0].visualValue, null);
  assert.equal(points[0].missing, true);
});

test('Issue 关闭率使用真实分子分母计算', () => {
  const pulse = buildGovernancePulseData([{ dt: '2026-01-01', metrics: { issues_closed: 8, issues_new: 10 } }]);
  const point = pulse.metrics.find((metric) => metric.key === 'issue_close_rate')?.points[0];
  assert.equal(point?.value, 80);
  assert.equal(point?.numerator, 8);
  assert.equal(point?.denominator, 10);
});

test('变更接受率在分母为 0 时保持缺失', () => {
  const pulse = buildGovernancePulseData([{ dt: '2026-01-01', metrics: { change_requests_accepted: 3, change_requests: 0 } }]);
  const point = pulse.metrics.find((metric) => metric.key === 'change_request_acceptance_rate')?.points[0];
  assert.equal(point?.value, null);
  assert.equal(point?.missing, true);
});

test('按不活跃快照增量去重，识别连续三个月净流出', () => {
  const points = buildTalentBalanceData([
    { dt: '2026-01-01', metrics: { new_contributors: 2, inactive_contributors: 10 } },
    { dt: '2026-02-01', metrics: { new_contributors: 2, inactive_contributors: 14 } },
    { dt: '2026-03-01', metrics: { new_contributors: 1, inactive_contributors: 17 } },
    { dt: '2026-04-01', metrics: { new_contributors: 0, inactive_contributors: 18 } },
  ]);
  assert.deepEqual(points.map((point) => point.inactiveContributors), [null, 4, 3, 1]);
  assert.deepEqual(findNegativeNetFlowRanges(points), [{ startMonth: '2026-02', endMonth: '2026-04', length: 3, totalNetFlow: -5 }]);
});

test('不活跃快照下降不被计为新的流出，缺失会重置基线', () => {
  assert.deepEqual(deriveUniqueInactiveFlow([10, 14, 14, 12, null, 20, 23]), [null, 4, 0, 0, null, null, 3]);
});

test('识别多个净流出区间并忽略短区间', () => {
  const flows = [-1, -2, -3, 1, -2, -2, -2, 2, -1];
  const points = flows.map((flow, index) => ({
    month: `2026-${String(index + 1).padStart(2, '0')}`,
    newContributors: Math.max(flow, 0),
    inactiveContributors: Math.max(-flow, 0),
    activeContributors: null,
    busFactor: null,
    netFlow: flow,
  }));
  assert.equal(findNegativeNetFlowRanges(points).length, 2);
});

test('Bus Factor 风险按连续月份区间合并', () => {
  const values = [2, 1, 6, 2, 2];
  const points = values.map((busFactor, index) => ({
    month: `2026-${String(index + 1).padStart(2, '0')}`,
    newContributors: null,
    inactiveContributors: null,
    activeContributors: null,
    busFactor,
    netFlow: null,
  }));
  assert.deepEqual(buildBusFactorRiskRanges(points, 3), [
    { startMonth: '2026-01', endMonth: '2026-02', length: 2 },
    { startMonth: '2026-04', endMonth: '2026-05', length: 2 },
  ]);
});

test('不同指标按统一月份对齐且缺失月份填 null', () => {
  const records = [
    { dt: '2026-02-01', metrics: { activity: 20 } },
    { dt: '2026-01-01', metrics: { openrank: 10 } },
  ];
  const aligned = alignMonthlyRecords(records);
  const pulse = buildGovernancePulseData(records);
  assert.deepEqual(aligned.months, ['2026-01', '2026-02']);
  assert.deepEqual(pulse.metrics.find((metric) => metric.key === 'openrank')?.points.map((point) => point.value), [10, null]);
});

test('选择最后一个真正有数据的月份', () => {
  const points = [
    { month: '2026-01', value: 1 },
    { month: '2026-02', value: null },
  ];
  assert.equal(latestValidMonth(points, (point) => point.value !== null), '2026-01');
});

test('人才字段全部缺失时进入空状态', () => {
  const points = buildTalentBalanceData([{ dt: '2026-01-01', metrics: { activity: 10 } }]);
  assert.equal(hasTalentData(points), false);
});
