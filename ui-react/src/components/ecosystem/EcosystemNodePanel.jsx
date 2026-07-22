import { formatMetric, ROLE_LABELS } from './graphVisualConfig';

function MiniMetric({ label, value }) {
  return <div className="ecosystem-mini-metric"><span>{label}</span><strong>{value == null ? '—' : value}</strong></div>;
}

function ContributorDrawer({ node, onExpand, expanding, canExpand }) {
  return <>
    <div className="ecosystem-profile">
      {node.avatar_url ? <img src={node.avatar_url} alt="" /> : <span className="profile-fallback">{(node.login || '?').slice(0, 2).toUpperCase()}</span>}
      <div><span className="node-kind">{ROLE_LABELS[node.role] || '贡献者'}</span><h3>{node.login}</h3><p>{node.name || 'GitHub 贡献者'}</p></div>
    </div>
    <div className="ecosystem-metric-grid">
      <MiniMetric label="综合贡献度" value={node.contribution_score == null ? null : formatMetric(node.contribution_score)} />
      <MiniMetric label="贡献占比" value={node.contribution_share == null ? null : formatMetric(node.contribution_share * 100) + '%'} />
      <MiniMetric label="首次参与" value={node.first_active_month} />
      <MiniMetric label="最近活跃" value={node.last_active_month} />
    </div>
    <div className="ecosystem-metric-grid compact">
      <MiniMetric label="Commit" value={node.commits} />
      <MiniMetric label="PR" value={node.pull_requests} />
      <MiniMetric label="Review" value={node.reviews} />
      <MiniMetric label="Issue" value={node.issues} />
    </div>
    <div className="ecosystem-status-row">
      {node.is_bridge && <span>桥梁贡献者</span>}
      {node.churn_risk && <span className="risk">流失风险：最近活跃距快照已超过两个月</span>}
    </div>
    <section className="ecosystem-drawer-section">
      <h4>其他活跃仓库</h4>
      {node.main_repositories?.length ? node.main_repositories.map((item) => <div className="ecosystem-repo-row" key={item.repo}><span>{item.repo}</span><b>{formatMetric(item.contribution_score)}</b></div>) : <p>当前贡献窗口暂无其他仓库。</p>}
    </section>
    <div className="ecosystem-detail-actions">
      {canExpand && node.depth < 3 && <button type="button" className="primary" onClick={() => onExpand(node)} disabled={expanding}>{expanding ? '正在展开…' : '展开参与仓库'}</button>}
      {node.profile_url && <a href={node.profile_url} target="_blank" rel="noreferrer">GitHub 主页</a>}
    </div>
  </>;
}

function RepositoryDrawer({ node, onExpand, onSetRoot, expanding, canExpand }) {
  return <>
    <div className="ecosystem-detail-title">
      <span className="node-kind">关联仓库</span>
      <h3>{node.repo || node.label}</h3>
      <p>{node.description || '暂无仓库描述'}</p>
    </div>
    <div className="ecosystem-metric-grid">
      <MiniMetric label="健康分" value={node.health_score == null ? null : formatMetric(node.health_score)} />
      <MiniMetric label="Stars" value={node.stars == null ? null : formatMetric(node.stars, 0)} />
      <MiniMetric label="主要语言" value={node.language} />
      <MiniMetric label="共享贡献者" value={node.association_strength == null ? null : formatMetric(node.association_strength)} />
    </div>
    <section className="ecosystem-drawer-section">
      <h4>当前网络路径</h4>
      <p>当前仓库 → 贡献者 → {node.repo || node.label}</p>
    </section>
    <div className="ecosystem-detail-actions">
      {canExpand && node.depth < 3 && <button type="button" onClick={() => onExpand(node)} disabled={expanding}>{expanding ? '正在展开…' : '展开主要贡献者'}</button>}
      {!node.is_root && <button type="button" className="primary" onClick={() => onSetRoot(node.repo)}>设为健康体检仓库</button>}
    </div>
  </>;
}

export default function EcosystemNodePanel({ node, mode, onExpand, onSetRoot, expanding, onClose }) {
  if (!node) return null;
  const canExpand = mode === 'explore';
  return <aside className="ecosystem-node-panel" aria-label="节点详情">
    <button type="button" className="ecosystem-drawer-close" onClick={onClose} aria-label="关闭详情">×</button>
    {node.type === 'repository'
      ? <RepositoryDrawer node={node} onExpand={onExpand} onSetRoot={onSetRoot} expanding={expanding} canExpand={canExpand} />
      : <ContributorDrawer node={node} onExpand={onExpand} expanding={expanding} canExpand={canExpand} />}
  </aside>;
}