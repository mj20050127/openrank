import { useEffect, useMemo, useRef } from 'react';
import ReactECharts from 'echarts-for-react';
import type { ECharts } from 'echarts';
import CommunityHealthToolbar from './CommunityHealthToolbar';
import { atlasTooltip, exportChartPng, formatNumber, healthColor } from './chartTheme.ts';
import { ATLAS_THEME, HEALTH_SCALE } from './metricConfig.ts';
import type { EcosystemEvent, GovernanceMetric, SharedChartProps } from './types.ts';

interface GovernancePulseMapProps extends SharedChartProps {
  months: string[];
  metrics: GovernanceMetric[];
  events: EcosystemEvent[];
  selectedMetric: string | null;
  onSelectedMetricChange(metric: string | null): void;
  onChartReady(instance: ECharts): void;
}

function zoomMonth(value: unknown, percentage: unknown, months: string[]): string | null {
  if (typeof value === 'string' && months.includes(value)) return value;
  if (Number.isFinite(Number(value))) return months[Math.max(0, Math.min(months.length - 1, Number(value)))] || null;
  if (Number.isFinite(Number(percentage)) && months.length) {
    return months[Math.round((Number(percentage) / 100) * (months.length - 1))] || null;
  }
  return null;
}

function rawTooltip(data: Record<string, any> | null | undefined, events: EcosystemEvent[]): string {
  if (!data) return '';
  const { point, metric } = data;
  if (!point || !metric) return '';
  const related = events.filter((event) => event.month === point.month);
  if (point.missing) {
    return `<strong>${metric.dimensionLabel} · ${metric.label}</strong><br/>${point.month}<br/><span style="color:${ATLAS_THEME.muted}">该月暂无数据</span><br/>数据来源：${metric.source}`;
  }
  const change = point.median === null ? null : point.value - point.median;
  const changeRatio = point.median ? (change / Math.abs(point.median)) * 100 : null;
  const sourceValue = metric.key === 'issue_age' && point.rawValue !== point.value
    ? `<br/>源值：${formatNumber(point.rawValue)}小时`
    : '';
  const formula = point.formula
    ? `<br/>公式：${point.formula}<br/>分子 / 分母：${formatNumber(point.numerator)} / ${formatNumber(point.denominator)}`
    : '';
  const eventText = related.length ? `<br/>相关事件：${related.map((event) => event.label).join('；')}` : '';
  return [
    `<strong>${metric.dimensionLabel} · ${metric.label}</strong>`,
    point.month,
    `原始值：${formatNumber(point.value)}${metric.unit || ''}${sourceValue}`,
    `历史中位数：${formatNumber(point.median)}${metric.unit || ''}`,
    `相对基线：${change === null ? '暂无数据' : `${change >= 0 ? '+' : ''}${formatNumber(change)}${metric.unit || ''}${changeRatio === null ? '' : `（${changeRatio >= 0 ? '+' : ''}${formatNumber(changeRatio)}%）`}`}`,
    `标准化健康偏离：${formatNumber(point.healthZ, 2)}`,
    `治理含义：${point.visualValue > 0.12 ? '改善' : point.visualValue < -0.12 ? '恶化' : '接近稳定'}`,
    `异常：${point.anomaly ? '是 ▲' : '否'}　阈值违规：${point.violation ? '是' : '否'}`,
    `数据来源：${point.source}${formula}${eventText}`,
  ].join('<br/>');
}

export default function GovernancePulseMap({
  months,
  metrics,
  events,
  selectedMonth,
  onSelectedMonthChange,
  rangeStart,
  rangeEnd,
  onRangeChange,
  selectedMetric,
  onSelectedMetricChange,
  onChartReady,
}: GovernancePulseMapProps) {
  const panelRef = useRef<HTMLElement>(null);
  const chartRef = useRef<ReactECharts>(null);

  useEffect(() => {
    chartRef.current?.getEchartsInstance().dispatchAction({ type: 'hideTip' });
  }, [selectedMetric]);

  const option = useMemo(() => {
    const displayedMetrics = selectedMetric
      ? metrics.filter((metric) => metric.key === selectedMetric)
      : metrics;
    const cells = displayedMetrics.flatMap((metric) => metric.points.map((point) => ({
      value: [point.month, metric.key, point.visualValue ?? 0],
      month: point.month,
      point,
      metric,
    })));
    const groupFirstRows = new Map<string, number>();
    displayedMetrics.forEach((metric, index) => {
      if (!groupFirstRows.has(metric.dimension)) groupFirstRows.set(metric.dimension, index);
    });

    const renderItem = (params: any, api: any) => {
      const cell = cells[params.dataIndex];
      if (!cell) return { type: 'group', children: [] };
      const point = cell.point;
      const coord = api.coord([api.value(0), api.value(1)]);
      const size = api.size([1, 1]);
      const width = Math.max(3, size[0] - 3);
      const height = Math.max(3, Math.abs(size[1]) - 3);
      const x = coord[0] - width / 2;
      const y = coord[1] - height / 2;
      const isFocusedMetric = !selectedMetric || cell.metric.key === selectedMetric;
      const borderColor = point.violation ? ATLAS_THEME.orange : ATLAS_THEME.panel;
      const children: any[] = [{
        type: 'rect',
        shape: { x, y, width, height },
        style: {
          fill: point.missing ? ATLAS_THEME.neutral : (api.visual('color') || healthColor(point.visualValue)),
          stroke: borderColor,
          lineWidth: point.violation ? 1.5 : 1,
          opacity: isFocusedMetric ? 1 : 0.28,
        },
      }];
      if (point.missing) {
        for (let offset = -height; offset < width; offset += 8) {
          const startX = Math.max(x, x + offset);
          const startY = y + Math.max(0, -offset);
          const endX = Math.min(x + width, x + offset + height);
          const endY = y + Math.min(height, height + offset);
          children.push({
            type: 'line',
            shape: { x1: startX, y1: startY, x2: endX, y2: endY },
            style: { stroke: 'rgba(109,117,111,.34)', lineWidth: 1, opacity: isFocusedMetric ? 1 : 0.28 },
          });
        }
      }
      if (point.anomaly) {
        children.push({
          type: 'polygon',
          shape: { points: [[x + width - 8, y + 2], [x + width - 2, y + 2], [x + width - 2, y + 8]] },
          style: { fill: '#101915', opacity: isFocusedMetric ? 1 : 0.35 },
        });
      }
      return { type: 'group', children };
    };

    const eventLines = events.map((event) => ({
      name: event.label,
      xAxis: event.month,
      event,
      lineStyle: { color: ATLAS_THEME.muted, type: 'dashed', width: 1 },
      label: { show: true, formatter: event.label, color: ATLAS_THEME.ink, fontSize: 10, rotate: 0, position: 'insideEndTop' },
    }));
    const selectedLine = selectedMonth ? [{
      name: '选中月份',
      xAxis: selectedMonth,
      lineStyle: { color: ATLAS_THEME.ink, type: 'solid', width: 2 },
      label: { show: false },
    }] : [];

    return {
      animation: true,
      animationDuration: 320,
      animationDurationUpdate: 150,
      backgroundColor: 'transparent',
      grid: { left: 218, right: 24, top: 38, bottom: 78 },
      tooltip: {
        ...atlasTooltip,
        trigger: 'item',
        triggerOn: 'mousemove',
        alwaysShowContent: false,
        hideDelay: 0,
        transitionDuration: 0,
        enterable: false,
        confine: true,
        formatter: (params: any) => rawTooltip(params.data, events),
      },
      xAxis: {
        type: 'category',
        data: months,
        position: 'top',
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
        axisPointer: { show: true, type: 'line', lineStyle: { color: ATLAS_THEME.ink, width: 1 } },
      },
      yAxis: {
        type: 'category',
        inverse: true,
        data: displayedMetrics.map((metric) => metric.key),
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          margin: 10,
          color: ATLAS_THEME.text,
          fontSize: 11,
          formatter: (_value: string, index: number) => {
            const metric = displayedMetrics[index];
            if (!metric) return '';
            const first = groupFirstRows.get(metric.dimension) === index;
            return `{group|${first ? `${metric.dimensionLabel} ${Math.round(metric.weight * 100)}%` : ''}} {metric|${metric.label}}`;
          },
          rich: {
            group: { width: 82, align: 'left', color: ATLAS_THEME.ink, fontWeight: 700, fontSize: 12 },
            metric: { width: 104, align: 'left', color: ATLAS_THEME.text, fontSize: 11 },
          },
        },
        splitLine: { show: true, lineStyle: { color: ATLAS_THEME.grid } },
      },
      visualMap: {
        type: 'continuous',
        seriesIndex: 0,
        dimension: 2,
        min: -1,
        max: 1,
        orient: 'horizontal',
        right: 24,
        bottom: 12,
        itemWidth: 15,
        itemHeight: 120,
        calculable: false,
        text: ['改善', '恶化'],
        textGap: 6,
        textStyle: { color: ATLAS_THEME.text, fontSize: 10 },
        inRange: { color: HEALTH_SCALE },
      },
      dataZoom: [
        { type: 'inside', xAxisIndex: 0, filterMode: 'none', startValue: rangeStart || months[0], endValue: rangeEnd || months.at(-1), throttle: 70 },
        {
          type: 'slider',
          xAxisIndex: 0,
          filterMode: 'none',
          height: 18,
          left: 218,
          right: 230,
          bottom: 18,
          startValue: rangeStart || months[0],
          endValue: rangeEnd || months.at(-1),
          borderColor: ATLAS_THEME.rule,
          backgroundColor: ATLAS_THEME.neutral,
          fillerColor: 'rgba(43,143,131,.20)',
          handleStyle: { color: ATLAS_THEME.panel, borderColor: ATLAS_THEME.ink },
          moveHandleStyle: { color: ATLAS_THEME.tealLight },
          textStyle: { color: ATLAS_THEME.muted, fontSize: 9 },
        },
      ],
      graphic: [{
        type: 'text',
        right: 26,
        bottom: 48,
        silent: true,
        style: { text: '恶化  —  稳定  —  改善　▲ 异常', fill: ATLAS_THEME.muted, font: '10px Consolas, monospace' },
      }],
      series: [
        {
          name: '治理健康偏离',
          type: 'custom',
          coordinateSystem: 'cartesian2d',
          renderItem,
          dimensions: ['month', 'metric', 'health'],
          encode: { x: 0, y: 1, tooltip: [0, 1, 2] },
          data: cells,
          z: 2,
        },
        {
          name: '月份与生态事件',
          type: 'line',
          data: months.map(() => null),
          silent: false,
          symbol: 'none',
          markLine: {
            silent: false,
            symbol: ['none', 'circle'],
            symbolSize: [0, 6],
            data: [...eventLines, ...selectedLine],
          },
          z: 4,
        },
      ],
    };
  }, [months, metrics, events, selectedMonth, selectedMetric, rangeStart, rangeEnd]);

  const resetZoom = () => {
    const chart = chartRef.current?.getEchartsInstance();
    const first = months[0];
    const last = months.at(-1);
    if (chart && first && last) {
      chart.setOption({
        dataZoom: [
          { startValue: first, endValue: last },
          { startValue: first, endValue: last },
        ],
      }, { lazyUpdate: false });
      chart.dispatchAction({ type: 'hideTip' });
      onRangeChange(first, last);
    }
  };
  const period = months.length ? `${months[0]} — ${months.at(-1)}` : '暂无数据';

  return <section className="atlas-analysis-panel atlas-pulse-panel" ref={panelRef} aria-labelledby="governance-pulse-title">
    <header className="atlas-panel-heading">
      <div><h2 id="governance-pulse-title">五维治理脉谱</h2><span>FIVE-DIMENSION PULSE MAP</span></div>
      <CommunityHealthToolbar
        metrics={metrics.map((metric) => ({ key: metric.key, label: `${metric.dimensionLabel} · ${metric.label}` }))}
        selectedMetric={selectedMetric}
        onMetricChange={onSelectedMetricChange}
        onResetZoom={resetZoom}
        onFullscreen={() => panelRef.current?.requestFullscreen()}
        onExport={() => exportChartPng(chartRef.current?.getEchartsInstance() || null, '五维治理脉谱', 'OpenDigger / 月度治理审计', period)}
      />
    </header>
    <p className="atlas-chart-explainer">颜色表示治理意义上的健康偏离：负向指标数值上升会被反转为恶化；灰色斜纹表示真实数据缺失。</p>
    <div className="atlas-chart-scroll">
      <div
        className="atlas-chart-min-width atlas-pulse-canvas"
        role="img"
        aria-label="五维治理指标按月份排列的健康偏离热力矩阵，红色表示恶化，蓝绿色表示改善，斜纹表示数据缺失"
        onDoubleClick={resetZoom}
        onMouseLeave={() => chartRef.current?.getEchartsInstance().dispatchAction({ type: 'hideTip' })}
        onPointerLeave={() => chartRef.current?.getEchartsInstance().dispatchAction({ type: 'hideTip' })}
      >
        <ReactECharts
          ref={chartRef}
          option={option}
          notMerge={false}
          replaceMerge={['series', 'yAxis']}
          lazyUpdate
          style={{ height: '440px', width: '100%' }}
          onChartReady={onChartReady}
          onEvents={{
            click: (params: any) => {
              const month = params.data?.month || params.data?.event?.month;
              if (month) onSelectedMonthChange(month);
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
    </div>
    <footer className="atlas-panel-footnote"><span>数据来源：OpenDigger 月度指标 / 月度治理审计</span><span>观察周期：{period}</span></footer>
  </section>;
}
