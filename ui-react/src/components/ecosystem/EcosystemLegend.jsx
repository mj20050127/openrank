const items = [
  { label: '核心维护者', color: '#42679A', kind: 'community' },
  { label: '活跃贡献者', color: '#34765F', kind: 'community' },
  { label: '新晋与流失风险', color: '#BD6047', kind: 'community' },
];

export default function EcosystemLegend() {
  return <div className="ecosystem-legend" aria-label="网络图例">
    {items.map(({ label, color, kind }) => <span key={label}>
      <i className={kind} style={{ '--legend-color': color }} />
      {label}
    </span>)}
  </div>;
}
