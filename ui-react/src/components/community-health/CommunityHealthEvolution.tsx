import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as echarts from 'echarts';
import type { ECharts } from 'echarts';
import ContributorBalanceChart from './ContributorBalanceChart';
import GovernancePulseMap from './GovernancePulseMap';
import { buildGovernancePulseData, buildTalentBalanceData, latestValidMonth, normalizeEcosystemEvents } from './adapters.ts';
import { BUS_FACTOR_THRESHOLD, CHART_GROUP_ID } from './metricConfig.ts';
import './community-health.css';

interface CommunityHealthEvolutionProps {
  records: Array<Record<string, unknown>>;
  selectedMonth: string | null;
  onSelectedMonthChange(month: string): void;
  events?: unknown[];
}

export default function CommunityHealthEvolution({
  records,
  selectedMonth,
  onSelectedMonthChange,
  events = [],
}: CommunityHealthEvolutionProps) {
  const pulse = useMemo(() => buildGovernancePulseData(records), [records]);
  const talent = useMemo(() => buildTalentBalanceData(records), [records]);
  const normalizedEvents = useMemo(() => normalizeEcosystemEvents(events, pulse.months), [events, pulse.months]);
  const latestMonth = useMemo(() => latestValidMonth(
    pulse.months.map((month) => ({ month, available: pulse.metrics.some((metric) => metric.points.some((point) => point.month === month && !point.missing)) })),
    (point) => point.available,
  ), [pulse]);
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);
  const [range, setRange] = useState<{ start: string | null; end: string | null }>({ start: null, end: null });
  const chartInstances = useRef(new Set<ECharts>());
  const syncChartRange = useCallback((start: string, end: string) => {
    chartInstances.current.forEach((instance) => {
      const zoomOption = instance.getOption().dataZoom;
      const zoomCount = Array.isArray(zoomOption) && zoomOption.length ? zoomOption.length : 1;
      instance.setOption({
        dataZoom: Array.from({ length: zoomCount }, () => ({ startValue: start, endValue: end })),
      }, { lazyUpdate: false });
      instance.dispatchAction({ type: 'hideTip' });
    });
  }, []);
  const monthSignature = pulse.months.join('|');
  const firstMonth = pulse.months[0] || null;
  const lastMonth = pulse.months.at(-1) || null;

  useEffect(() => {
    setRange({ start: firstMonth, end: lastMonth });
    setSelectedMetric(null);
    if (firstMonth && lastMonth) syncChartRange(firstMonth, lastMonth);
  }, [monthSignature, firstMonth, lastMonth, syncChartRange]);

  useEffect(() => {
    if (latestMonth && (!selectedMonth || !pulse.months.includes(selectedMonth))) onSelectedMonthChange(latestMonth);
  }, [monthSignature, latestMonth, selectedMonth, onSelectedMonthChange, pulse.months]);

  useEffect(() => () => {
    echarts.disconnect(CHART_GROUP_ID);
    chartInstances.current.clear();
  }, []);

  const registerChart = useCallback((instance: ECharts) => {
    instance.group = CHART_GROUP_ID;
    chartInstances.current.add(instance);
    echarts.connect(CHART_GROUP_ID);
  }, []);

  const changeRange = useCallback((start: string, end: string) => {
    if (!start || !end) return;
    setRange((current) => current.start === start && current.end === end ? current : { start, end });
  }, []);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    const currentIndex = Math.max(0, pulse.months.indexOf(selectedMonth || latestMonth || ''));
    const nextIndex = Math.max(0, Math.min(pulse.months.length - 1, currentIndex + (event.key === 'ArrowRight' ? 1 : -1)));
    const month = pulse.months[nextIndex];
    if (month) {
      event.preventDefault();
      onSelectedMonthChange(month);
    }
  };

  return <section
    id="community-health-evolution"
    className="community-health-evolution"
    aria-label="社区健康演化分析"
    tabIndex={0}
    onKeyDown={handleKeyDown}
  >
    <GovernancePulseMap
      months={pulse.months}
      metrics={pulse.metrics}
      events={normalizedEvents}
      selectedMonth={selectedMonth || latestMonth}
      onSelectedMonthChange={onSelectedMonthChange}
      rangeStart={range.start}
      rangeEnd={range.end}
      onRangeChange={changeRange}
      selectedMetric={selectedMetric}
      onSelectedMetricChange={setSelectedMetric}
      onChartReady={registerChart}
    />
    <ContributorBalanceChart
      points={talent}
      busFactorThreshold={BUS_FACTOR_THRESHOLD}
      selectedMonth={selectedMonth || latestMonth}
      onSelectedMonthChange={onSelectedMonthChange}
      rangeStart={range.start}
      rangeEnd={range.end}
      onRangeChange={changeRange}
      onChartReady={registerChart}
    />
  </section>;
}
