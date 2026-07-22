import { useMemo, useRef } from 'react';
import ReactECharts from 'echarts-for-react';
import ContributorParetoChart from '../../features/health/ContributorParetoChart';
import ChartFullscreenButton from '../../features/health/ChartFullscreenButton';
import '../../features/health/HealthDimensions.css';
import HealthRadarGraphic from '../../features/health/HealthRadarGraphic';
import { DIMENSIONS, GOVERNANCE_THEME, METRICS, valueFor } from '../../utils/governanceConfig';

const dimensions = Object.entries(DIMENSIONS);

function formatValue(value, metricKey, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '暂无数据';
  const config = METRICS[metricKey] || {};
  const numeric = Number(value);
  const rendered = new Intl.NumberFormat('zh-CN', { maximumFractionDigits: digits }).format(numeric);
  return `${rendered}${config.unit || ''}`;
}



function DashboardIcon({ name }) {
  if (name === 'switch') return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7h12m0 0-3-3m3 3-3 3M17 17H5m0 0 3 3m-3-3 3-3" /></svg>;
  if (name === 'refresh') return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 5v6h-6" /></svg>;
  if (name === 'download') return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m0 0 4-4m-4 4-4-4" /><path d="M5 17v3h14v-3" /></svg>;
  if (name === 'trend') return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m4 7 5 5 4-4 7 7" /><path d="M20 10v5h-5" /></svg>;
  if (name === 'warning') return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3 2.8 20h18.4L12 3Z" /><path d="M12 9v5m0 3h.01" /></svg>;
  if (name === 'bell') return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 17h14l-2-3V9a5 5 0 0 0-10 0v5l-2 3Z" /><path d="M10 20h4" /></svg>;
  if (name === 'shield') return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 7 3v5c0 4.4-2.7 7.8-7 10-4.3-2.2-7-5.6-7-10V6l7-3Z" /><path d="m9 12 2 2 4-4" /></svg>;
  if (name === 'database') return <svg viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="6" rx="7" ry="3" /><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" /></svg>;
  return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="5" cy="12" r="1" /><circle cx="12" cy="12" r="1" /><circle cx="19" cy="12" r="1" /></svg>;
}


export function HealthSummaryCards({ current, activeDimension, anomalyCount, onDimension }) {
  const latest = current;
  const completeness = latest?.data_completeness == null ? null : latest.data_completeness * 100;
  const delta = latest?.score_delta ?? latest?.delta ?? null;
  const weak = dimensions
    .map(([key, config]) => ({ key, label: config.label, value: latest?.scores?.[key] }))
    .filter((item) => item.value != null)
    .sort((a, b) => a.value - b.value)[0];
  const cards = [
    { label: '本期变化', value: delta == null ? '—' : `${delta > 0 ? '+' : ''}${Number(delta).toFixed(1)}分`, note: '较上一快照', tone: 'blue', icon: 'trend' },
    { label: '最弱维度', value: weak ? `${weak.label} ${Number(weak.value).toFixed(1)}` : '—', note: '点击查看维度证据', tone: 'orange', icon: 'warning', key: weak?.key },
    { label: '异常事件', value: anomalyCount ?? 0, note: '阈值或移动偏差触发', tone: 'red', icon: 'bell' },
    { label: '数据可信度', value: completeness == null ? '—' : `${Math.round(completeness)}%`, note: '指标字段覆盖完整', tone: 'green', icon: 'shield' },
  ];
  return <section className="gov-kpi-grid">
    {cards.map((card) => <button type="button" className={`gov-kpi ${card.tone} ${activeDimension === card.key ? 'selected' : ''}`} key={card.label} onClick={() => card.key && onDimension(card.key)}>
      <span className="gov-kpi-icon"><DashboardIcon name={card.icon} /></span>
      <span className="gov-kpi-content"><span>{card.label}</span><strong>{card.value}</strong><small>{card.note}</small></span>
    </button>)}
  </section>;
}

function finiteScore(value) {
  if (value === null || value === undefined || value === '') return Number.NaN;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : Number.NaN;
}

function diagnosisFor(scores, benchmarks) {
  const available = dimensions
    .map(([key, config]) => ({ key, label: config.label, value: finiteScore(scores?.[key]), benchmark: finiteScore(benchmarks?.[key]) }))
    .filter((item) => Number.isFinite(item.value))
    .sort((left, right) => left.value - right.value);
  if (!available.length) return ['五维健康数据尚未就绪。'];
  const weakest = available[0];
  const strongest = available.at(-1);
  const weakComparison = Number.isFinite(weakest.benchmark)
    ? weakest.value < weakest.benchmark
      ? `低于基准 ${(weakest.benchmark - weakest.value).toFixed(1)} 分，建议优先排查。`
      : `高于基准 ${(weakest.value - weakest.benchmark).toFixed(1)} 分。`
    : '为当前五维中的最低项，建议优先观察。';
  return [
    `${weakest.label} ${weakest.value.toFixed(1)}，${weakComparison}`,
    `${strongest.label} ${strongest.value.toFixed(1)}，是当前表现最稳定的维度。`,
  ];
}

export function HealthDimensions({
  current,
  selectedDimension,
  onSelect,
  contributors,
  contributorMonth,
  contributorStatus,
  selectedContributorId,
  hoveredContributorId,
  onSelectContributor,
  onHoverContributor,
}) {
  const latest = current;
  const radarPanelRef = useRef(null);
  const benchmarks = latest?.benchmark_scores || latest?.benchmarks?.scores || latest?.benchmarks || latest?.evidence?.benchmarks || null;
  const diagnosis = diagnosisFor(latest?.scores, benchmarks);

  return <section className="gov-two-up diagnosis-report">

    <article className="gov-panel dimension-panel" ref={radarPanelRef}>
      <div className="panel-title radar-panel-title"><h2>五维健康剖面</h2><ChartFullscreenButton targetRef={radarPanelRef} /></div>
      <div className="radar-compact-body">
        <HealthRadarGraphic dimensions={dimensions} scores={latest?.scores} benchmarks={benchmarks} selectedDimension={selectedDimension} onSelect={onSelect} />
      </div>
      <div className="diagnosis-summary"><strong>诊断结论：</strong>{diagnosis.map((line) => <p key={line}>{line}</p>)}</div>
    </article>
    <ContributorParetoChart
      contributors={contributors}
      month={contributorMonth}
      status={contributorStatus}
      selectedContributorId={selectedContributorId}
      hoveredContributorId={hoveredContributorId}
      onSelectContributor={onSelectContributor}
      onHoverContributor={onHoverContributor}
    />
  </section>;
}
const tooltip = {
  backgroundColor: GOVERNANCE_THEME.tooltip,
  borderColor: GOVERNANCE_THEME.border,
  borderWidth: 1,
  textStyle: { color: '#f8fafc', fontSize: 12 },
  extraCssText: 'box-shadow:0 14px 30px rgba(0,0,0,.28);border-radius:8px;padding:10px 12px;',
};

function anomalyPoints(records, metricKey) {
  const values = records.map((record) => valueFor(record, metricKey)).filter((value) => value != null);
  if (values.length < 4) return [];
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
  const deviation = Math.sqrt(values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length);
  if (!deviation) return [];
  return records.map((record, index) => {
    const value = valueFor(record, metricKey);
    if (value == null || Math.abs((value - mean) / deviation) < 1.7) return null;
    return { coord: [record.dt, value], value, record, dataIndex: index, symbolSize: 38, itemStyle: { color: GOVERNANCE_THEME.warning } };
  }).filter(Boolean);
}

export function GovernanceTrendChart({ records, selectedDimension, selectedMetrics, focusMonth, onToggleMetric, onAnomaly, onZoom }) {
  const ref = useRef(null);
  const metricOptions = useMemo(() => (selectedDimension === 'score_health' ? ['score_health'] : DIMENSIONS[selectedDimension]?.metrics || []), [selectedDimension]);
  const primary = selectedMetrics[0] || metricOptions[0] || 'score_health';
  const option = useMemo(() => {
    const labels = records.map((record) => record.dt);
    const selected = selectedMetrics.length ? selectedMetrics : metricOptions.slice(0, 2);
    return {
      animationDuration: 420,
      color: [GOVERNANCE_THEME.primary, GOVERNANCE_THEME.cyan, GOVERNANCE_THEME.warning, '#9c8cff', GOVERNANCE_THEME.success],
      tooltip: { ...tooltip, trigger: 'axis', axisPointer: { type: 'cross', label: { backgroundColor: GOVERNANCE_THEME.panelStrong } }, formatter: (items) => {
        const date = items[0]?.axisValue || '';
        return [date, ...items.map((item) => `${item.marker}${METRICS[item.seriesName]?.label || item.seriesName}：${formatValue(item.value, item.seriesName)}`)].join('<br/>');
      } },
      legend: { top: 8, type: 'scroll', textStyle: { color: GOVERNANCE_THEME.muted }, selected: Object.fromEntries(metricOptions.map((key) => [key, selected.includes(key)])) },
      grid: { left: 58, right: 24, top: 48, bottom: 70 },
      xAxis: { type: 'category', data: labels, boundaryGap: false, axisLine: { lineStyle: { color: GOVERNANCE_THEME.grid } }, axisLabel: { color: GOVERNANCE_THEME.muted, hideOverlap: true } },
      yAxis: { type: 'value', scale: true, axisLabel: { color: GOVERNANCE_THEME.muted }, splitLine: { lineStyle: { color: GOVERNANCE_THEME.grid } } },
      dataZoom: [{ type: 'inside', throttle: 40 }, { type: 'slider', height: 18, bottom: 18, borderColor: 'transparent', fillerColor: 'rgba(40,120,227,.16)', textStyle: { color: GOVERNANCE_THEME.muted } }],
      toolbox: { right: 8, top: 4, iconStyle: { borderColor: GOVERNANCE_THEME.muted }, feature: { restore: {}, saveAsImage: { name: 'OpenSage-趋势' } } },
      series: metricOptions.map((key) => {
        const config = METRICS[key] || {};
        const threshold = config.threshold;
        const focusLabel = focusMonth ? records.find((record) => String(record.dt).startsWith(focusMonth))?.dt : null;
        const markLines = [
          threshold == null ? null : {
            name: '治理阈值',
            yAxis: threshold,
            lineStyle: { color: config.betterWhen === 'lower' ? GOVERNANCE_THEME.risk : GOVERNANCE_THEME.warning, type: 'dashed' },
          },
          key === primary && focusLabel ? {
            name: '网络快照',
            xAxis: focusLabel,
            lineStyle: { color: GOVERNANCE_THEME.primary, type: 'solid' },
          } : null,
        ].filter(Boolean);
        return {
          name: key,
          type: 'line',
          data: records.map((record) => valueFor(record, key)),
          connectNulls: false,
          showSymbol: true,
          symbolSize: 4,
          smooth: false,
          lineStyle: { width: 2 },
          markLine: markLines.length ? { symbol: 'none', label: { color: GOVERNANCE_THEME.muted, formatter: (params) => params.name }, data: markLines } : undefined,
          markPoint: key === primary ? { data: anomalyPoints(records, key), label: { formatter: '异常' } } : undefined,
        };
      }),
    };
  }, [records, metricOptions, selectedMetrics, primary, focusMonth]);

  const exportChart = () => {
    const instance = ref.current?.getEchartsInstance();
    if (!instance) return;
    const link = document.createElement('a');
    link.href = instance.getDataURL({ pixelRatio: 2, backgroundColor: GOVERNANCE_THEME.canvas });
    link.download = 'OpenSage-治理趋势.png';
    link.click();
  };

  return <section className="gov-panel trend-panel" id="governance-trend">
    <div className="panel-title trend-title"><div><span className="eyebrow">核心分析</span><h2>健康趋势与异常定位</h2><p>刷选时间区间后，KPI、诊断和证据同步更新。点击橙色异常标记查看证据。</p></div>
      <div className="metric-toggles">{metricOptions.map((key) => <button type="button" className={selectedMetrics.includes(key) ? 'active' : ''} key={key} onClick={() => onToggleMetric(key)}>{METRICS[key]?.label || key}</button>)}<button type="button" onClick={exportChart}>导出图片</button><button type="button" onClick={() => document.getElementById('governance-trend')?.requestFullscreen()}>全屏</button></div>
    </div>
    <ReactECharts ref={ref} option={option} className="gov-chart trend-chart" onEvents={{ datazoom: onZoom, click: (event) => event.data?.record && onAnomaly(event.data) }} />
  </section>;
}

export function MetricSmallMultiples({ records, dimension }) {
  const keys = DIMENSIONS[dimension]?.metrics || [];
  return <section className="diagnostic-section"><div className="section-heading"><div><span className="eyebrow">指标下钻</span><h2>{DIMENSIONS[dimension]?.label || '综合健康'}诊断</h2></div><p>{DIMENSIONS[dimension]?.description}</p></div><div className="small-multiples">
    {keys.map((key) => {
      const option = {
        animationDuration: 260,
        tooltip: { ...tooltip, trigger: 'axis', formatter: (items) => `${items[0]?.axisValue || ''}<br/>${METRICS[key]?.label}：${formatValue(items[0]?.value, key)}` },
        grid: { left: 48, right: 12, top: 30, bottom: 34 },
        xAxis: { type: 'category', data: records.map((record) => record.dt), boundaryGap: false, axisLabel: { color: GOVERNANCE_THEME.muted, fontSize: 10, hideOverlap: true }, axisLine: { lineStyle: { color: GOVERNANCE_THEME.grid } } },
        yAxis: { type: 'value', scale: true, axisLabel: { color: GOVERNANCE_THEME.muted, fontSize: 10 }, splitLine: { lineStyle: { color: GOVERNANCE_THEME.grid } } },
        series: [{ type: 'line', data: records.map((record) => valueFor(record, key)), connectNulls: false, showSymbol: false, smooth: false, lineStyle: { color: DIMENSIONS[dimension]?.color, width: 2 }, areaStyle: { color: `${DIMENSIONS[dimension]?.color}18` }, markLine: METRICS[key]?.threshold == null ? undefined : { symbol: 'none', lineStyle: { color: GOVERNANCE_THEME.warning, type: 'dashed' }, label: { show: false }, data: [{ yAxis: METRICS[key].threshold }] } }],
      };
      return <article className="small-chart" key={key}><div><strong>{METRICS[key]?.label}</strong><span>{METRICS[key]?.source}</span></div><ReactECharts option={option} className="small-chart-canvas" /></article>;
    })}
  </div></section>;
}




