const TICKS = [0, 20, 40, 60, 80, 100];
const SEGMENTS = Array.from({ length: 20 }, (_, index) => {
  const midpoint = index * 5 + 2.5;
  const tone = midpoint < 35 ? 'risk' : midpoint < 55 ? 'attention' : midpoint < 85 ? 'healthy' : 'neutral';
  return { index, tone };
});

export default function HealthScale({ score }) {
  const numeric = Number(score);
  const hasScore = score !== null && score !== undefined && score !== '' && Number.isFinite(numeric);
  const clamped = hasScore ? Math.max(0, Math.min(100, numeric)) : 0;

  return <div className="health-scale" aria-label={hasScore ? `综合健康分 ${numeric.toFixed(1)}` : '综合健康分暂无数据'}>
    <div className="health-scale__value-row">
      <strong>{hasScore ? numeric.toFixed(1) : '—'}</strong>
      <span>/100</span>
    </div>
    <div className="health-scale__track" aria-hidden="true">
      {SEGMENTS.map((segment) => <span key={segment.index} className={`health-scale__segment ${segment.tone}`} />)}
      {hasScore && <b style={{ left: `${clamped}%` }}><em>{numeric.toFixed(1)}</em></b>}
    </div>
    <div className="health-scale__ticks" aria-hidden="true">
      {TICKS.map((tick) => <span key={tick}>{tick}</span>)}
    </div>
  </div>;
}
