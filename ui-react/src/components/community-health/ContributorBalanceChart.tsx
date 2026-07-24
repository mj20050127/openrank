import { useMemo, useRef } from 'react';
import ReactECharts from 'echarts-for-react';
import type { ECharts } from 'echarts';
import CommunityHealthToolbar from './CommunityHealthToolbar';
import { atlasTooltip, exportChartPng, formatNumber } from './chartTheme.ts';
import { ATLAS_THEME } from './metricConfig.ts';
import { buildBusFactorRiskRanges, findNegativeNetFlowRanges, hasTalentData } from './adapters.ts';
import type { SharedChartProps, TalentMonthlyPoint } from './types.ts';

interface ContributorBalanceChartProps extends SharedChartProps {
  points: TalentMonthlyPoint[];
  busFactorThreshold: number;
  onChartReady(instance: ECharts): void;
}

function zoomMonth(value: unknown, percentage: unknown, months: string[]): string | null {
  if (typeof value === 'string' && months.includes(value)) return value;
  if (Number.isFinite(Number(value))) return months[Math.max(0, Math.min(months.length - 1, Number(value)))] || null;
  if (Number.isFinite(Number(percentage)) && months.length) return months[Math.round((Number(percentage) / 100) * (months.length - 1))] || null;
  return null;
}

function summaryText(point: TalentMonthlyPoint | undefined): string {
  if (!point || point.netFlow === null) return '人才流入或流出字段缺失，暂无法判断社区净流向。';
  return point.netFlow < 0
    ? '新人补充不足以抵消成员流失，社区韧性承压。'
    : '新人流入覆盖成员流失，社区更新保持正向。';
}

export default function ContributorBalanceChart({
  points,
  busFactorThreshold,
  selectedMonth,
  onSelectedMonthChange,
  rangeStart,
  rangeEnd,
  onRangeChange,
  onChartReady,
}: ContributorBalanceChartProps) {
  const panelRef = useRef<HTMLElement>(null);
  const chartRef = useRef<ReactECharts>(null);
  const months = useMemo(() => points.map((point) => point.month), [points]);
  const pointByMonth = useMemo(() => new Map(points.map((point) => [point.month, point])), [points]);
  const negativeRanges = useMemo(() => findNegativeNetFlowRanges(points), [points]);
  const busRiskRanges = useMemo(() => buildBusFactorRiskRanges(points, busFactorThreshold), [points, busFactorThreshold]);
  const summaryPoint = pointByMonth.get(selectedMonth || '') || [...points].reverse().find((point) => (
    point.newContributors !== null || point.inactiveContributors !== null || point.inactiveContributorsSnapshot !== null || point.activeContributors !== null
  ));
  const mostSevereRange = useMemo(() => [...negativeRanges].sort((left, right) => (
    (left.totalNetFlow ?? 0) - (right.totalNetFlow ?? 0) || right.endMonth.localeCompare(left.endMonth)
  ))[0], [negativeRanges]);

  const option = useMemo(() => ({
    animation: true,
    animationDuration: 320,
    animationDurationUpdate: 150,
    backgroundColor: 'transparent',
    color: [ATLAS_THEME.teal, ATLAS_THEME.orange, ATLAS_THEME.ink],
    grid: { left: 58, right: 64, top: 52, bottom: 46 },
    legend: {
      left: 58,
      top: 10,
      itemWidth: 14,
      itemHeight: 9,
      textStyle: { color: ATLAS_THEME.text, fontSize: 11 },
      data: ['新贡献者', '新进入不活跃', '活跃贡献者'],
    },
    tooltip: {
      ...atlasTooltip,
      trigger: 'axis',
      triggerOn: 'mousemove',
      alwaysShowContent: false,
      hideDelay: 0,
      transitionDuration: 0,
      enterable: false,
      confine: true,
      axisPointer: { type: 'line', lineStyle: { color: ATLAS_THEME.ink, width: 1 } },
      formatter: (params: any[]) => {
        const month = String(params[0]?.axisValue || '');
        const point = pointByMonth.get(month);
        if (!point) return `${month}<br/>暂无数据`;
        const busRisk = point.busFactor !== null && point.busFactor < busFactorThreshold;
        const flowState = point.netFlow === null ? '净流向未知' : point.netFlow < 0 ? '净流出' : '净流入';
        return [
          `<strong>${month}</strong>`,
          `新贡献者：${formatNumber(point.newContributors)}${point.newContributors === null ? '' : '人'}`,
          `新进入不活跃：${formatNumber(point.inactiveContributors)}${point.inactiveContributors === null ? '' : '人'}`,
          `不活跃状态快照：${formatNumber(point.inactiveContributorsSnapshot)}${point.inactiveContributorsSnapshot === null || point.inactiveContributorsSnapshot === undefined ? '' : '人'}`,
          `净流入：${point.netFlow === null ? '暂无数据' : `${point.netFlow >= 0 ? '+' : ''}${formatNumber(point.netFlow)}人`}`,
          `活跃贡献者：${formatNumber(point.activeContributors)}${point.activeContributors === null ? '' : '人'}`,
          `Bus Factor：${formatNumber(point.busFactor)}　阈值：${busFactorThreshold}`,
          `社区状态：${flowState}${busRisk ? ' / Bus Factor 风险关注' : ''}`,
        ].join('<br/>');
      },
    },
    xAxis: {
      type: 'category',
      data: months,
      axisLine: { lineStyle: { color: ATLAS_THEME.rule } },
      axisTick: { alignWithLabel: true, lineStyle: { color: ATLAS_THEME.rule } },
      axisLabel: {
        interval: months.length > 36 ? 2 : months.length > 24 ? 1 : 0,
        color: ATLAS_THEME.text,
        fontSize: 10,
        fontFamily: 'Consolas, monospace',
        formatter: (value: string) => value === selectedMonth ? `{selected|${value}}` : value,
        rich: { selected: { color: ATLAS_THEME.ink, borderColor: ATLAS_THEME.ink, borderWidth: 1, padding: [3, 4], backgroundColor: ATLAS_THEME.panel } },
      },
      axisPointer: { show: true, snap: true, label: { show: false } },
    },
    yAxis: [
      {
        type: 'value',
        name: '人数变化（人）',
        nameTextStyle: { color: ATLAS_THEME.muted, fontSize: 10, align: 'left' },
        axisLabel: { color: ATLAS_THEME.muted, fontSize: 10 },
        axisLine: { show: true, lineStyle: { color: ATLAS_THEME.rule } },
        splitLine: { lineStyle: { color: ATLAS_THEME.grid } },
      },
      {
        type: 'value',
        name: '活跃贡献者（人）',
        nameTextStyle: { color: ATLAS_THEME.muted, fontSize: 10, align: 'right' },
        axisLabel: { color: ATLAS_THEME.muted, fontSize: 10 },
        axisLine: { show: true, lineStyle: { color: ATLAS_THEME.rule } },
        splitLine: { show: false },
      },
    ],
    dataZoom: [{
      type: 'inside',
      xAxisIndex: 0,
      filterMode: 'none',
      startValue: rangeStart || months[0],
      endValue: rangeEnd || months.at(-1),
      throttle: 70,
    }],
    series: [
      {
        name: '新贡献者',
        type: 'bar',
        yAxisIndex: 0,
        data: points.map((point) => point.newContributors),
        barMaxWidth: 18,
        itemStyle: { color: ATLAS_THEME.teal },
        emphasis: { itemStyle: { borderColor: ATLAS_THEME.ink, borderWidth: 1 } },
      },
      {
        name: '新进入不活跃',
        type: 'bar',
        yAxisIndex: 0,
        data: points.map((point) => point.inactiveContributors === null ? null : -Math.abs(point.inactiveContributors)),
        barMaxWidth: 18,
        itemStyle: { color: ATLAS_THEME.orange },
        emphasis: { itemStyle: { borderColor: ATLAS_THEME.ink, borderWidth: 1 } },
      },
      {
        name: '活跃贡献者',
        type: 'line',
        yAxisIndex: 1,
        data: points.map((point) => point.activeContributors),
        connectNulls: false,
        symbol: 'circle',
        symbolSize: 5,
        lineStyle: { color: ATLAS_THEME.ink, width: 2 },
        itemStyle: { color: ATLAS_THEME.ink },
        markLine: selectedMonth ? {
          silent: true,
          symbol: 'none',
          label: { show: false },
          lineStyle: { color: ATLAS_THEME.ink, width: 2, type: 'solid' },
          data: [{ xAxis: selectedMonth }],
        } : undefined,
      },
      {
        name: 'Bus Factor 风险月份',
        type: 'line',
        data: months.map(() => null),
        silent: true,
        symbol: 'none',
        markArea: {
          silent: true,
          itemStyle: { color: 'rgba(184,73,53,.12)' },
          label: { show: false },
          data: busRiskRanges.map((range) => [
            { name: `Bus Factor < ${busFactorThreshold}`, xAxis: range.startMonth },
            { xAxis: range.endMonth },
          ]),
        },
      },
      {
        name: '连续净流出',
        type: 'line',
        data: months.map(() => null),
        silent: true,
        symbol: 'none',
        markArea: {
          silent: true,
          itemStyle: { color: 'rgba(184,73,53,.025)', borderColor: ATLAS_THEME.red, borderWidth: 1.5, borderType: 'dashed' },
          label: {
            show: true,
            color: ATLAS_THEME.red,
            fontSize: 10,
            formatter: (params: any) => params.name || '',
            position: 'insideTop',
          },
          data: negativeRanges.map((range) => [
            {
              name: range === mostSevereRange ? `连续 ${range.length} 个月净流出\n累计 ${formatNumber(range.totalNetFlow)} 人` : '',
              xAxis: range.startMonth,
            },
            { xAxis: range.endMonth },
          ]),
        },
      },
    ],
  }), [points, months, pointByMonth, busFactorThreshold, busRiskRanges, negativeRanges, mostSevereRange, selectedMonth, rangeStart, rangeEnd]);

  const resetZoom = () => {
    const chart = chartRef.current?.getEchartsInstance();
    const first = months[0];
    const last = months.at(-1);
    if (chart && first && last) {
      chart.setOption({ dataZoom: [{ startValue: first, endValue: last }] }, { lazyUpdate: false });
      chart.dispatchAction({ type: 'hideTip' });
      onRangeChange(first, last);
    }
  };
  const period = months.length ? `${months[0]} — ${months.at(-1)}` : '暂无数据';
  const available = hasTalentData(points);

  return <section className="atlas-analysis-panel atlas-talent-panel" ref={panelRef} aria-labelledby="contributor-balance-title">
    <header className="atlas-panel-heading atlas-talent-heading">
      <div><h2 id="contributor-balance-title">社区人才收支</h2><span>CONTRIBUTOR INFLOW &amp; OUTFLOW</span></div>
      <div className="talent-current-summary" aria-live="polite">
        <span>月份 <strong>{summaryPoint?.month || '—'}</strong></span>
        <span className="inflow">新增 <strong>{formatNumber(summaryPoint?.newContributors)}</strong></span>
        <span className="outflow">新进入不活跃 <strong>{formatNumber(summaryPoint?.inactiveContributors)}</strong></span>
        <span className={summaryPoint?.netFlow !== null && summaryPoint?.netFlow !== undefined && summaryPoint.netFlow < 0 ? 'net-negative' : 'net-positive'}>
          净流入 <strong>{summaryPoint?.netFlow === null || summaryPoint?.netFlow === undefined ? '暂无数据' : `${summaryPoint.netFlow >= 0 ? '+' : ''}${formatNumber(summaryPoint.netFlow)}`}</strong>
        </span>
      </div>
      <CommunityHealthToolbar
        onResetZoom={resetZoom}
        onFullscreen={() => panelRef.current?.requestFullscreen()}
        onExport={() => exportChartPng(chartRef.current?.getEchartsInstance() || null, '社区人才收支', 'OpenDigger 月度指标', period)}
      />
    </header>
    <p className="talent-dynamic-explanation">{summaryText(summaryPoint)}<span className="talent-data-method">不活跃人数按月度快照增量去重估算，同一人不会重复计入。</span></p>
    {!available ? <div className="atlas-empty-state" role="status">当前仓库暂无贡献者月度数据</div> : <div className="atlas-chart-scroll">
      <div
        className="atlas-chart-min-width atlas-talent-canvas"
        role="img"
        aria-label="社区新贡献者正柱、不活跃贡献者负柱和活跃贡献者折线图，Bus Factor 风险以月份背景区间表示"
        onDoubleClick={resetZoom}
        onMouseLeave={() => chartRef.current?.getEchartsInstance().dispatchAction({ type: 'hideTip' })}
        onPointerLeave={() => chartRef.current?.getEchartsInstance().dispatchAction({ type: 'hideTip' })}
      >
        <ReactECharts
          ref={chartRef}
          option={option}
          notMerge={false}
          lazyUpdate
          style={{ height: '330px', width: '100%' }}
          onChartReady={onChartReady}
          onEvents={{
            click: (params: any) => {
              const month = String(params.name || params.data?.month || '');
              if (months.includes(month)) onSelectedMonthChange(month);
            },
            mouseout: () => {
              chartRef.current?.getEchartsInstance().dispatchAction({ type: 'hideTip' });
            },
            globalout: () => {
              chartRef.current?.getEchartsInstance().dispatchAction({ type: 'hideTip' });
            },
            datazoom: (event: any) => {
              const zoom = event.batch?.[0] || event;
              const start = zoomMonth(zoom.startValue, zoom.start, months);
              const end = zoomMonth(zoom.endValue, zoom.end, months);
              if (start && end) onRangeChange(start, end);
            },
          }}
        />
      </div>
    </div>}
    <footer className="atlas-panel-footnote"><span>不活跃流出：按月度快照增量去重估算　·　Bus Factor 风险阈值：&lt; {busFactorThreshold}</span><span>观察周期：{period}</span></footer>
  </section>;
}
