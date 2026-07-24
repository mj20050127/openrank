interface MetricOption {
  key: string;
  label: string;
}

interface CommunityHealthToolbarProps {
  metrics?: MetricOption[];
  selectedMetric?: string | null;
  onMetricChange?: (metric: string | null) => void;
  onResetZoom: () => void;
  onFullscreen: () => void;
  onExport: () => void;
}

export default function CommunityHealthToolbar({
  metrics = [],
  selectedMetric = null,
  onMetricChange,
  onResetZoom,
  onFullscreen,
  onExport,
}: CommunityHealthToolbarProps) {
  return <div className="atlas-toolbar" aria-label="图表工具栏">
    {metrics.length > 0 && <label className="atlas-metric-filter" title="指标筛选">
      <span>指标</span>
      <select
        value={selectedMetric || ''}
        onChange={(event) => onMetricChange?.(event.target.value || null)}
        aria-label="筛选或聚焦治理指标"
      >
        <option value="">全部指标</option>
        {metrics.map((metric) => <option value={metric.key} key={metric.key}>{metric.label}</option>)}
      </select>
    </label>}
    <button type="button" onClick={onResetZoom} title="恢复全部月份" aria-label="恢复全部月份">缩放复位</button>
    <button type="button" onClick={onFullscreen} title="全屏查看" aria-label="全屏查看">全屏</button>
    <button type="button" onClick={onExport} title="导出 PNG" aria-label="导出 PNG">导出</button>
  </div>;
}
