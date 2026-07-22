export default function EcosystemTimeline({ months, value, onChange, disabled }) {
  const index = Math.max(0, months.indexOf(value));

  return <div className="ecosystem-timeline">
    <span>{months[0] || '—'}</span>
    <input
      type="range"
      min="0"
      max={Math.max(0, months.length - 1)}
      value={index}
      disabled={disabled || !months.length}
      onChange={(event) => onChange(months[Number(event.target.value)])}
      aria-label="月度网络快照"
    />
    <strong>{value || '暂无月份'}</strong>
    <span>{months.at(-1) || '—'}</span>
  </div>;
}