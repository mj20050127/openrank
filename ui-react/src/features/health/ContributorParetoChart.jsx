import { useEffect, useMemo, useRef } from 'react';
import ReactECharts from 'echarts-for-react';
import ChartFullscreenButton from './ChartFullscreenButton';
import {
  buildContributorPareto,
  CONTRIBUTOR_ROLE_COLORS,
  CONTRIBUTOR_ROLE_LABELS,
  formatParetoPercent,
} from './contributorParetoAdapter';
import './ContributorParetoChart.css';

const tooltipStyle = {
  backgroundColor: '#14231F',
  borderColor: '#43524C',
  borderWidth: 1,
  textStyle: { color: '#FAF8F1', fontSize: 11 },
  extraCssText: 'box-shadow:0 10px 24px rgba(20,35,31,.2);border-radius:2px;padding:9px 11px;',
};

function displayNumber(value) {
  if (!Number.isFinite(value)) return '—';
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 1 }).format(value);
}

function resolveChartContributorId(contributorId, chartContributors, sourceContributors) {
  if (!contributorId) return null;
  if (chartContributors.some((item) => item.id === contributorId)) return contributorId;
  const belongsToAggregate = sourceContributors.some((item) => item.id === contributorId);
  return belongsToAggregate
    ? chartContributors.find((item) => item.isAggregate)?.id || null
    : null;
}

export default function ContributorParetoChart({
  contributors = [],
  month,
  status: dataStatus,
  selectedContributorId,
  hoveredContributorId,
  onSelectContributor,
  onHoverContributor,
}) {
  const panelRef = useRef(null);
  const chartRef = useRef(null);
  const pareto = useMemo(() => buildContributorPareto(contributors), [contributors]);
  const selectedChartId = useMemo(
    () => resolveChartContributorId(selectedContributorId, pareto.contributors, contributors),
    [contributors, pareto.contributors, selectedContributorId],
  );
  const hoveredChartId = useMemo(
    () => resolveChartContributorId(hoveredContributorId, pareto.contributors, contributors),
    [contributors, hoveredContributorId, pareto.contributors],
  );
  const chartFocusId = hoveredChartId || selectedChartId;

  const option = useMemo(() => {
    const rows = pareto.contributors;
    const busDisplayIndex = pareto.busFactor == null
      ? null
      : Math.min(pareto.busFactor - 1, rows.length - 1);
    const categories = rows.map((item) => item.login);

    return {
      animationDuration: 420,
      grid: { left: 44, right: 52, top: 24, bottom: 68, containLabel: false },
      tooltip: {
        ...tooltipStyle,
        trigger: 'axis',
        axisPointer: { type: 'shadow', shadowStyle: { color: 'rgba(52,117,95,.06)' } },
        formatter: (items) => {
          const dataIndex = items?.[0]?.dataIndex;
          const item = rows[dataIndex];
          if (!item) return '';
          const role = item.isAggregate
            ? `其他贡献者（${item.aggregateCount}人）`
            : CONTRIBUTOR_ROLE_LABELS[item.role] || CONTRIBUTOR_ROLE_LABELS.other;
          const activeMonths = item.activeMonths12 == null ? '—' : `${item.activeMonths12}个月`;
          return [
            `<strong>${item.login}</strong>`,
            `角色：${role}`,
            `当前贡献度：${displayNumber(item.contribution)}`,
            `贡献占比：${formatParetoPercent(item.share)}`,
            `累计贡献占比：${formatParetoPercent(item.cumulativeShare)}`,
            `近12月活跃：${activeMonths}`,
            `Bus Factor成员：${item.isBusFactorMember && !item.isAggregate ? '是' : '否'}`,
          ].join('<br/>');
        },
      },
      xAxis: {
        type: 'category',
        data: categories,
        axisTick: { show: false },
        axisLine: { lineStyle: { color: 'rgba(27,47,41,.24)' } },
        axisLabel: {
          color: '#5F6D67',
          fontSize: 10,
          interval: 0,
          rotate: categories.length > 7 ? 36 : 0,
          width: 70,
          overflow: 'truncate',
        },
      },
      yAxis: [
        {
          type: 'value',
          name: '个人占比',
          min: 0,
          axisLabel: { color: '#718079', fontSize: 10, formatter: '{value}%' },
          nameTextStyle: { color: '#718079', fontSize: 10, padding: [0, 0, 2, -4] },
          splitLine: { lineStyle: { color: 'rgba(38,65,56,.10)' } },
        },
        {
          type: 'value',
          name: '累计占比',
          min: 0,
          max: 100,
          interval: 25,
          axisLabel: { color: '#718079', fontSize: 10, formatter: '{value}%' },
          nameTextStyle: { color: '#718079', fontSize: 10, padding: [0, -4, 2, 0] },
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: '个人贡献占比',
          type: 'bar',
          yAxisIndex: 0,
          barMaxWidth: 26,
          z: 3,
          data: rows.map((item) => ({
            value: Number(item.share.toFixed(4)),
            contributorId: item.id,
            itemStyle: {
              color: CONTRIBUTOR_ROLE_COLORS[item.role] || CONTRIBUTOR_ROLE_COLORS.other,
              opacity: selectedChartId && selectedChartId !== item.id ? 0.48 : 0.92,
              borderColor: selectedChartId === item.id ? '#14231F' : 'transparent',
              borderWidth: selectedChartId === item.id ? 2 : 0,
              borderRadius: 0,
            },
          })),
          emphasis: { itemStyle: { opacity: 1 } },
          markArea: busDisplayIndex == null ? undefined : {
            silent: true,
            itemStyle: { color: 'rgba(189,132,45,.08)' },
            data: [[{ xAxis: 0 }, { xAxis: busDisplayIndex }]],
          },
        },
        {
          name: '累计贡献占比',
          type: 'line',
          yAxisIndex: 1,
          z: 5,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { color: '#14231F', width: 2 },
          itemStyle: { color: '#FAF8F1', borderColor: '#14231F', borderWidth: 1.5 },
          data: rows.map((item) => ({
            value: Number(item.cumulativeShare.toFixed(4)),
            contributorId: item.id,
          })),
          markLine: {
            silent: true,
            symbol: ['none', 'none'],
            label: {
              position: 'insideEndTop',
              distance: 6,
              color: '#718079',
              fontSize: 10,
              padding: [1, 3],
              borderRadius: 2,
              backgroundColor: 'rgba(248,246,239,.94)',
            },
            data: [
              { yAxis: 50, name: '50%', lineStyle: { color: '#C45F3A', type: 'dashed', width: 1.4 }, label: { formatter: '50%', color: '#A34D31', position: 'insideEndTop' } },
              { yAxis: 80, name: '80%', lineStyle: { color: '#A94336', type: 'dashed', width: 1.1 }, label: { formatter: '80%', color: '#A94336', position: 'insideEndTop' } },
              ...(busDisplayIndex == null ? [] : [{
                xAxis: busDisplayIndex,
                name: `Bus Factor ${pareto.busFactor}`,
                lineStyle: { color: '#BD842D', type: 'dashed', width: 1.4 },
                label: { formatter: `BF ${pareto.busFactor}`, color: '#C97313', position: 'insideEndTop' },
              }]),
            ],
          },
        },
      ],
    };
  }, [pareto, selectedChartId]);

  useEffect(() => {
    const instance = chartRef.current?.getEchartsInstance?.();
    if (!instance) return;
    instance.dispatchAction({ type: 'downplay', seriesIndex: 0 });
    if (!chartFocusId) return;
    const dataIndex = pareto.contributors.findIndex((item) => item.id === chartFocusId);
    if (dataIndex >= 0) instance.dispatchAction({ type: 'highlight', seriesIndex: 0, dataIndex });
  }, [pareto.contributors, chartFocusId]);

  useEffect(() => {
    const resizeChart = () => {
      window.requestAnimationFrame(() => chartRef.current?.getEchartsInstance?.().resize());
    };
    document.addEventListener('fullscreenchange', resizeChart);
    return () => document.removeEventListener('fullscreenchange', resizeChart);
  }, []);

  const handleInteraction = (event, callback) => {
    const item = pareto.contributors[event?.dataIndex];
    if (!item || item.isAggregate) return;
    callback?.(item.id);
  };

  return <article className="gov-panel contribution-panel contributor-pareto-panel" ref={panelRef}>
    <div className="pareto-heading">
      <h2>贡献集中度与 Bus Factor</h2>
      <div className="pareto-heading-actions">
        <span className="pareto-month">{month || '—'}</span>
        <ChartFullscreenButton targetRef={panelRef} />
      </div>
    </div>

    {pareto.contributors.length ? <>
      <div className="pareto-summary" aria-label="核心贡献依赖摘要">
        <div><span>Bus Factor</span><strong>{pareto.busFactor ?? '—'}</strong></div>
        <div><span>Top5占比</span><strong>{formatParetoPercent(pareto.top5Share)}</strong></div>
        <div><span>最大单人</span><strong>{formatParetoPercent(pareto.maxSingleShare)}</strong></div>
        <em className={`pareto-status ${pareto.status?.tone || ''}`}>{pareto.status?.label || '—'}</em>
      </div>
      <div className="pareto-visual-grid">
        <ReactECharts
          ref={chartRef}
          option={option}
          notMerge
          className="gov-chart contributor-pareto-chart"
          onEvents={{
            mouseover: (event) => handleInteraction(event, onHoverContributor),
            mouseout: () => onHoverContributor?.(null),
            click: (event) => handleInteraction(event, onSelectContributor),
          }}
        />
      </div>
    </> : <div className="pareto-empty" role="status">
      <strong>{dataStatus === 'loading' ? '正在同步贡献者明细…' : '当前月份暂无可计算的贡献者明细'}</strong>
      <span>仅使用生态网络当前月份的真实贡献数据</span>
    </div>}
  </article>;
}
