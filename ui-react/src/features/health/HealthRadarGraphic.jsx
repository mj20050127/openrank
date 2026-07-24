import { useEffect, useRef, useState } from 'react';
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

function activateOnKeyboard(event, callback) {
  if (event.key !== 'Enter' && event.key !== ' ') return;
  event.preventDefault();
  callback();
}

export default function HealthRadarGraphic({ dimensions, scores, benchmarks, selectedDimension, onSelect }) {
  const [detailKey, setDetailKey] = useState(null);
  const closeButtonRef = useRef(null);
  const triggerRef = useRef(null);
  const activeEntry = detailKey ? dimensions.find(([key]) => key === detailKey) : null;
  const activeDimension = activeEntry?.[1] || null;
  const activeScore = detailKey ? numericValue(scores?.[detailKey]) : null;
  const activeBenchmark = detailKey ? numericValue(benchmarks?.[detailKey]) : null;
  const scoreDelta = activeScore !== null && activeBenchmark !== null ? activeScore - activeBenchmark : null;

  function openDetail(key, event) {
    triggerRef.current = event?.currentTarget || null;
    onSelect?.(key);
    setDetailKey(key);
  }

  function closeDetail() {
    setDetailKey(null);
  }

  useEffect(() => {
    if (!detailKey) return undefined;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const focusFrame = window.requestAnimationFrame(() => closeButtonRef.current?.focus());
    const handleDialogKeyDown = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        setDetailKey(null);
      } else if (event.key === 'Tab') {
        event.preventDefault();
        closeButtonRef.current?.focus();
      }
    };
    document.addEventListener('keydown', handleDialogKeyDown);
    return () => {
      window.cancelAnimationFrame(focusFrame);
      document.removeEventListener('keydown', handleDialogKeyDown);
      document.body.style.overflow = previousOverflow;
      window.requestAnimationFrame(() => {
        if (triggerRef.current?.isConnected) triggerRef.current.focus();
      });
    };
  }, [detailKey]);

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

  return <>
    <svg className="health-radar-svg" viewBox={`0 0 ${VIEWBOX_WIDTH} ${VIEWBOX_HEIGHT}`} role="group" aria-label="五维健康雷达图，点击维度查看评分说明">
      {RINGS.map((scale) => <polygon key={scale} points={polygonPoints(dimensions.map((_, dimensionIndex) => pointAt(dimensionIndex, scale)))} fill="none" stroke="rgba(38, 65, 56, .20)" strokeWidth="1" />)}
      {outerVertices.map((point, index) => <line key={dimensions[index][0]} x1={CENTER_X} y1={CENTER_Y} x2={point.x} y2={point.y} stroke="rgba(38, 65, 56, .16)" strokeWidth="1" />)}
      {hasBenchmark && <polygon points={polygonPoints(benchmarkVertices)} fill="none" stroke="#7f8782" strokeWidth="1.4" strokeDasharray="4 4" />}
      <polygon points={polygonPoints(vertices)} fill="rgba(52, 117, 95, .17)" stroke="#245a48" strokeWidth="2.3" strokeLinejoin="round" />

      {vertices.map((point, index) => {
        const [key, dimension] = dimensions[index];
        const isSelected = selectedDimension === key;
        const score = numericValue(scores?.[key]);
        const accessibleLabel = `${dimension.label}，${score === null ? '暂无数据' : `${score.toFixed(1)}分`}，查看计算说明`;
        return <g
          key={key}
          className="health-radar-point-control"
          role="button"
          tabIndex="0"
          aria-label={accessibleLabel}
          onClick={(event) => openDetail(key, event)}
          onKeyDown={(event) => activateOnKeyboard(event, () => openDetail(key, event))}
        >
          {isSelected && <circle cx={point.x} cy={point.y} r="8" fill="none" stroke="#14231f" strokeWidth="1" />}
          <circle cx={point.x} cy={point.y} r="3.5" fill="#245a48" stroke="#faf8f1" strokeWidth="1.3" />
          <circle className="health-radar-hit-target" cx={point.x} cy={point.y} r="13"><title>{accessibleLabel}</title></circle>
        </g>;
      })}

      {dimensions.map(([key, dimension], index) => {
        const label = pointAt(index, 1, LABEL_RADIUS);
        const score = numericValue(scores?.[key]);
        const baseline = numericValue(benchmarks?.[key]);
        const delta = score !== null && baseline !== null ? score - baseline : null;
        return <text
          key={key}
          className={selectedDimension === key ? 'health-radar-label selected' : 'health-radar-label'}
          x={label.x}
          y={label.y}
          textAnchor={labelAnchor(label.x)}
          role="button"
          tabIndex="0"
          aria-label={`${dimension.label}，${score === null ? '暂无数据' : `${score.toFixed(1)}分`}，查看计算说明`}
          onClick={(event) => openDetail(key, event)}
          onKeyDown={(event) => activateOnKeyboard(event, () => openDetail(key, event))}
        >
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
    </svg>

    {activeDimension?.detail && <div className="health-dimension-dialog-overlay" onMouseDown={(event) => event.target === event.currentTarget && closeDetail()}>
      <section className="health-dimension-dialog" role="dialog" aria-modal="true" aria-labelledby={`health-dimension-dialog-${detailKey}`} style={{ '--dimension-accent': activeDimension.color }}>
        <header className="health-dimension-dialog-header">
          <div><span className="health-dimension-dialog-kicker">五维健康说明 · CURRENT-V1</span><h2 id={`health-dimension-dialog-${detailKey}`}>{activeDimension.label}</h2></div>
          <button ref={closeButtonRef} type="button" className="health-dimension-dialog-close" onClick={closeDetail} aria-label="关闭维度说明">×</button>
        </header>
        <div className="health-dimension-dialog-body">
          <div className="health-dimension-score-summary">
            <div><span>当前得分</span><strong>{activeScore === null ? '—' : activeScore.toFixed(1)}</strong></div>
            <p>{scoreDelta === null ? '暂无可比较的基准数据' : `${scoreDelta >= 0 ? '高于' : '低于'}基准 ${Math.abs(scoreDelta).toFixed(1)} 分`}</p>
          </div>
          <div className="health-dimension-meaning"><h3>这个维度说明什么</h3><p>{activeDimension.detail.meaning}</p></div>
          <div className="health-dimension-formula"><span>核心公式</span><code>{activeDimension.detail.formula}</code></div>
          <div className="health-dimension-components"><h3>指标构成与计算</h3><ul>
            {activeDimension.detail.components.map((component) => <li key={component.name}>
              <div className="health-dimension-component-title"><strong>{component.name}</strong><span>{component.weight}</span></div>
              <code>{component.formula}</code><p>{component.note}</p>
            </li>)}
          </ul></div>
          <p className="health-dimension-method-note"><strong>计算说明：</strong>{activeDimension.detail.note}</p>
        </div>
      </section>
    </div>}
  </>;
}
