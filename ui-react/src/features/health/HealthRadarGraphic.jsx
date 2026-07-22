import './HealthRadarGraphic.css';

const VIEWBOX_WIDTH = 420;
const VIEWBOX_HEIGHT = 292;
const CENTER_X = 210;
const CENTER_Y = 142;
const RADIUS = 94;
const LABEL_RADIUS = 130;
const RINGS = [0.25, 0.5, 0.75, 1];

function pointAt(index, scale, radius = RADIUS) {
  const angle = (-90 - index * 72) * (Math.PI / 180);
  return {
    x: CENTER_X + Math.cos(angle) * radius * scale,
    y: CENTER_Y + Math.sin(angle) * radius * scale,
  };
}

function polygonPoints(points) {
  return points.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(' ');
}

function labelAnchor(x) {
  if (x < CENTER_X - 12) return 'end';
  if (x > CENTER_X + 12) return 'start';
  return 'middle';
}

function numericValue(value) {
  if (value === null || value === undefined || value === '') return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

export default function HealthRadarGraphic({ dimensions, scores, benchmarks, selectedDimension, onSelect }) {
  const values = dimensions.map(([key]) => {
    const value = numericValue(scores?.[key]);
    return value === null ? 0 : Math.max(0, Math.min(100, value));
  });
  const benchmarkValues = dimensions.map(([key]) => numericValue(benchmarks?.[key]));
  const hasBenchmark = benchmarkValues.every((value) => value !== null);
  const vertices = values.map((value, index) => pointAt(index, value / 100));
  const benchmarkVertices = hasBenchmark
    ? benchmarkValues.map((value, index) => pointAt(index, Math.max(0, Math.min(100, value)) / 100))
    : [];
  const outerVertices = dimensions.map((_, index) => pointAt(index, 1));

  return <svg className="health-radar-svg" viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`} role="img" aria-label="五维健康雷达图">
    {RINGS.map((scale) => <polygon key={scale} points={polygonPoints(dimensions.map((_, dimensionIndex) => pointAt(dimensionIndex, scale)))} fill="none" stroke="rgba(38, 65, 56, .20)" strokeWidth="1" />)}
    {outerVertices.map((point, index) => <line key={dimensions[index][0]} x1={CENTER_X} y1={CENTER_Y} x2={point.x} y2={point.y} stroke="rgba(38, 65, 56, .16)" strokeWidth="1" />)}
    {hasBenchmark && <polygon points={polygonPoints(benchmarkVertices)} fill="none" stroke="#7f8782" strokeWidth="1.4" strokeDasharray="4 4" />}
    <polygon points={polygonPoints(vertices)} fill="rgba(52, 117, 95, .17)" stroke="#245a48" strokeWidth="2.3" strokeLinejoin="round" />

    {vertices.map((point, index) => {
      const [key] = dimensions[index];
      const isSelected = selectedDimension === key;
      return <g key={key}>
        {isSelected && <circle cx={point.x} cy={point.y} r="8" fill="none" stroke="#14231f" strokeWidth="1" />}
        <circle cx={point.x} cy={point.y} r="3.5" fill="#245a48" stroke="#faf8f1" strokeWidth="1.3" />
        <circle className="health-radar-hit-target" cx={point.x} cy={point.y} r="13" onClick={() => onSelect?.(key)}>
          <title>{dimensions[index][1].label}：{scores?.[key] == null ? '暂无数据' : `${Number(scores[key]).toFixed(1)}分`}</title>
        </circle>
      </g>;
    })}

    {dimensions.map(([key, dimension], index) => {
      const label = pointAt(index, 1, LABEL_RADIUS);
      const score = numericValue(scores?.[key]);
      const baseline = numericValue(benchmarks?.[key]);
      const delta = score !== null && baseline !== null ? score - baseline : null;
      return <text key={key} className={selectedDimension === key ? 'health-radar-label selected' : 'health-radar-label'} x={label.x} y={label.y} textAnchor={labelAnchor(label.x)} onClick={() => onSelect?.(key)}>
        <tspan x={label.x}>{dimension.label}</tspan>
        <tspan className="health-radar-label-score" x={label.x} dy="17">{score === null ? '—' : score.toFixed(1)}</tspan>
        {baseline !== null && <tspan className="health-radar-label-baseline" dx="5">基准 {baseline.toFixed(0)}</tspan>}
        {delta !== null && <tspan className={delta >= 0 ? 'health-radar-delta up' : 'health-radar-delta down'} dx="5">{delta >= 0 ? '↑' : '↓'}{Math.abs(delta).toFixed(1)}</tspan>}
      </text>;
    })}

    <g className="health-radar-legend" aria-hidden="true">
      <line x1="270" y1="277" x2="290" y2="277" stroke="#245a48" strokeWidth="2" /><text x="296" y="280">本仓库</text>
      <line x1="348" y1="277" x2="368" y2="277" stroke="#7f8782" strokeWidth="1.4" strokeDasharray="4 3" /><text x="374" y="280">{hasBenchmark ? '基准' : '基准 —'}</text>
    </g>
  </svg>;
}
