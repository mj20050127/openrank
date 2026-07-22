import { useState } from 'react';
import { formatMetric, ROLE_LABELS } from './graphVisualConfig';

function MiniMetric({ label, value, icon }) {
  return <div className="ecosystem-mini-metric"><span>{icon} {label}</span><strong>{value == null ? '—' : value}</strong></div>;
}

function ProfileAvatar({ node }) {
  const candidates = [...new Set([
    node.avatar_url,
    node.login ? `https://avatars.githubusercontent.com/${encodeURIComponent(node.login)}?s=192` : null,
  ].filter(Boolean))];
  const [attempt, setAttempt] = useState(0);
  if (!candidates[attempt]) return <span className="profile-fallback">{(node.login || '?').slice(0, 2).toUpperCase()}</span>;
  return <img src={candidates[attempt]} alt={`${node.login} 头像`} onError={() => setAttempt((value) => value + 1)} />;
}

function ActivityHeatmap({ node, month }) {
  const values = Array.isArray(node.activity_12m) ? node.activity_12m : [];
  const cells = Array.from({ length: 12 }, (_, index) => {
    const raw = values[index];
    if (raw && typeof raw === 'object') return raw;
    return { month: null, value: Number.isFinite(Number(raw)) ? Number(raw) : null };
  });
  const max = Math.max(1, ...cells.map((cell) => Number(cell.value || 0)));
  return <section className="ecosystem-drawer-section ecosystem-activity"><h4>近 12 个月活跃度</h4>
    <div className="ecosystem-heatmap">{cells.map((cell, index) => {
      const level = cell.value == null ? 'missing' : cell.value === 0 ? 'zero' : String(Math.max(1, Math.ceil((cell.value / max) * 4)));
      return <i key={cell.month || index} className={`level-${level}`} title={`${cell.month || '月份缺失'}：${cell.value == null ? '数据缺失' : cell.value}`} />;
    })}</div>
    <div className="ecosystem-heatmap-months"><span>{cells[0]?.month || '—'}</span><span>{month || cells.at(-1)?.month || '—'}</span></div>
    <div className="ecosystem-heatmap-legend"><span>低</span><i /><i /><i /><i /><span>高</span></div>
  </section>;
}

function relationshipText(node) {
  const rank = node.role === 'core' ? '属于当前仓库的核心贡献群体' : `属于${ROLE_LABELS[node.role] || '贡献者'}群体`;
  const active = node.active_months == null ? '活跃月份数据暂缺' : `累计活跃 ${node.active_months} 个月`;
  const related = node.main_repositories?.length ? `同时参与 ${Math.min(3, node.main_repositories.length)} 个可验证关联项目` : '当前窗口暂无可验证关联仓库';
  return `该贡献者${rank}，${active}，${related}。`;
}

function GovernanceSignals({ node }) {
  const signals = [];
  if (node.role === 'core' || Number(node.contribution_share || 0) >= 0.2) signals.push(['warning', '知识集中度偏高', `贡献占比 ${formatMetric(Number(node.contribution_share || 0) * 100)}%`]);
  if (node.churn_risk) signals.push(['risk', '存在流失风险', `最近活跃于 ${node.last_active_month || '未知月份'}`]);
  else if (node.last_active_month) signals.push(['good', '近 3 月活跃稳定', `最近活跃于 ${node.last_active_month}`]);
  if (node.is_bridge) signals.push(['bridge', '关联仓库跨度较高', `可验证关联项目 ${Math.min(3, node.main_repositories?.length || 0)} 个`]);
  return <section className="ecosystem-drawer-section"><h4>治理信号</h4><div className="ecosystem-signal-list">
    {signals.slice(0, 3).map(([kind, title, evidence]) => <div className={`ecosystem-signal ${kind}`} key={title}><i>●</i><div><b>{title}</b><span>{evidence}</span></div><em>{kind === 'good' ? '良好' : '需关注'}</em></div>)}
  </div></section>;
}

function ContributorDrawer({ node, month, expanding, expanded, onExpand, onCollapse }) {
  return <>
    <div className="ecosystem-profile"><div className="ecosystem-profile-avatar"><ProfileAvatar key={node.id} node={node} /><i>★</i></div><div><h3>{node.login}</h3><span className="node-kind">✦ {ROLE_LABELS[node.role] || '贡献者'}</span><p>{node.name || 'GitHub 贡献者'}</p></div></div>
    <div className="ecosystem-metric-grid contributor-kpis">
      <MiniMetric icon="⌘" label="提交贡献" value={node.commits == null ? null : formatMetric(node.commits, 0)} />
      <MiniMetric icon="◫" label="代码审查" value={node.reviews == null ? null : formatMetric(node.reviews, 0)} />
      <MiniMetric icon="◉" label="问题处理" value={node.issues == null ? null : formatMetric(node.issues, 0)} />
    </div>
    <ActivityHeatmap node={node} month={month} />
    <section className="ecosystem-drawer-section"><h4>关系解释</h4><p>{relationshipText(node)}</p></section>
    <GovernanceSignals node={node} />
    <div className="ecosystem-detail-actions sticky-actions">
      {expanded ? <button type="button" onClick={() => onCollapse(node)}>收起关联仓库</button> : <button type="button" className="primary" onClick={() => onExpand(node)} disabled={expanding}>{expanding ? '正在加载…' : '查看关联仓库'}</button>}
      {node.profile_url && <a href={node.profile_url} target="_blank" rel="noreferrer">GitHub ↗</a>}
    </div>
  </>;
}

function RepositoryDrawer({ node, onSetRoot }) {
  return <>
    <div className="ecosystem-detail-title"><span className="node-kind">关联仓库</span><h3>{node.repo || node.label}</h3><p>{node.description || '暂无仓库描述'}</p></div>
    <div className="ecosystem-metric-grid"><MiniMetric label="Stars" value={node.stars == null ? null : formatMetric(node.stars, 0)} /><MiniMetric label="主要语言" value={node.language} /><MiniMetric label="贡献关系" value={node.association_strength == null ? null : formatMetric(node.association_strength)} /><MiniMetric label="数据月份" value={node.metric_month?.slice(0, 7)} /></div>
    <section className="ecosystem-drawer-section"><h4>当前网络路径</h4><p>当前仓库 → 贡献者 → {node.repo || node.label}</p></section>
    <div className="ecosystem-detail-actions sticky-actions">{!node.is_root && <button type="button" className="primary" onClick={() => onSetRoot(node.repo)}>设为当前治理对象</button>}</div>
  </>;
}

export default function EcosystemNodePanelV2({ node, month, expanding, expanded, onExpand, onCollapse, onSetRoot, onClose }) {
  if (!node) return null;
  return <aside className="ecosystem-node-panel ecosystem-node-panel-v2" aria-label="节点详情">
    <button type="button" className="ecosystem-drawer-close" onClick={onClose} aria-label="关闭详情">×</button>
    {node.type === 'repository' ? <RepositoryDrawer node={node} onSetRoot={onSetRoot} /> : <ContributorDrawer node={node} month={month} expanding={expanding} expanded={expanded} onExpand={onExpand} onCollapse={onCollapse} />}
  </aside>;
}


