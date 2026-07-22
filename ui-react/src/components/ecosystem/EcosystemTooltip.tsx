import { ROLE_LABELS } from './graphVisualConfig';

export default function EcosystemTooltip({ node }) {
  if (!node) return null;
  const name = node.label || node.login || node.repo;
  const isRepository = node.visualType === 'repository' || node.visualType === 'root-repository' || node.type === 'repository';
  const kind = isRepository ? (node.is_root ? '当前仓库' : '关联仓库') : (ROLE_LABELS[node.role] || '贡献者');
  return <div className="ecosystem-tooltip" role="status">
    {!isRepository && (node.avatar_url || node.avatarUrl)
      ? <img className="ecosystem-tooltip-avatar" src={node.avatar_url || node.avatarUrl} alt="" />
      : <span className="ecosystem-tooltip-icon">{isRepository ? '⌘' : (node.login || '?').slice(0, 1).toUpperCase()}</span>}
    <div className="ecosystem-tooltip-content">
      <strong title={name}>{name}</strong>
      <span>{kind} · 贡献 {node.contribution_score ?? node.association_strength ?? '—'}</span>
      <small>{node.last_active_month ? `最近活跃 ${node.last_active_month} · ` : ''}双击{isRepository ? '展开贡献者' : '展开仓库'}</small>
      {(node.risk || node.churn_risk || node.role === 'risk') && <em>风险：最近活跃时间距当前快照较远</em>}
    </div>
  </div>;
}