import { useMemo, useState } from 'react';

const statusLabel = {
  healthy: '健康',
  attention: '关注',
  risk: '风险',
};

function ObservatoryMark() {
  return <svg className="observatory-mark" viewBox="0 0 48 48" aria-hidden="true">
    <circle cx="24" cy="24" r="19" /><circle cx="24" cy="24" r="4" />
    <path d="M24 5v38M5 24h38M11 11l26 26M37 11 11 37" />
    <path d="m24 10 4 10 10 4-10 4-4 10-4-10-10-4 10-4 4-10Z" />
  </svg>;
}

function Sparkline({ values }) {
  const points = useMemo(() => {
    const data = (Array.isArray(values) ? values : [])
      .map((item) => Number(item?.score ?? item?.value ?? item))
      .filter(Number.isFinite);
    if (data.length < 2) return null;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const spread = Math.max(1, max - min);
    return data.map((value, index) => {
      const x = (index / (data.length - 1)) * 100;
      const y = 18 - ((value - min) / spread) * 14;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
  }, [values]);

  if (!points) return <span className="ranking-sparkline-empty" aria-label="暂无历史健康分">—</span>;
  return <svg className="ranking-sparkline" viewBox="0 0 100 20" preserveAspectRatio="none" aria-hidden="true"><polyline points={points} /></svg>;
}

function RankingItem({ item, selected, onSelect, pinned = false }) {
  const score = item.score === null || item.score === undefined || item.score === '' ? Number.NaN : Number(item.score);
  const tone = score >= 80 ? 'healthy' : score >= 60 ? 'attention' : 'risk';
  const history = item.history || item.score_history || item.trend;
  return <button type="button" className={`ranking-item ${selected ? 'selected' : ''} ${pinned ? 'pinned' : ''}`} onClick={() => onSelect(item.repo)} title={item.repo}>
    <span className={`ranking-position rank-${item.rank}`}>{String(item.rank).padStart(2, '0')}</span>
    <span className="ranking-repo"><strong>{item.repo}</strong><small><i className={tone} />{pinned ? '当前仓库实际排名' : statusLabel[tone] || '已评估'}</small><Sparkline values={history} /></span>
    <span className={`ranking-score ${tone}`}><strong>{Number.isFinite(score) ? score.toFixed(1) : '—'}</strong></span>
  </button>;
}

export default function HealthRankingRail({ payload, status, error, selectedRepo, onSelect, onRetry }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const top = payload?.top || [];
  const selectedOutsideTop = payload?.current && !top.some((item) => item.repo === payload.current.repo);
  const coverage = payload?.coverage;
  const observedDate = payload?.observed_at ? new Date(payload.observed_at).toLocaleDateString('zh-CN') : null;

  return <aside className={`health-ranking-rail health-ranking-sidebar ${mobileOpen ? 'mobile-open' : ''}`}>
    <button type="button" className="ranking-mobile-toggle" onClick={() => setMobileOpen((open) => !open)} aria-expanded={mobileOpen}>
      <span><strong>仓库健康排名</strong><small>{observedDate ? `体检于 ${observedDate}` : '等待当前体检'}</small></span>
      <span aria-hidden="true">{mobileOpen ? '收起' : '查看'}</span>
    </button>
    <div className="ranking-panel-body">
      <div className="ranking-brand"><ObservatoryMark /><div><strong>OPEN-SOURCE</strong><strong>GOVERNANCE</strong><strong>OBSERVATORY</strong></div></div>
      <div className="ranking-section-label"><span>01</span><div><strong>REPOSITORY</strong><small>仓库健康排名</small></div></div>
      <div className="ranking-heading"><h2>当前健康分排名</h2><span className="ranking-date">{observedDate || '暂无体检'}</span></div>
      <p className="ranking-coverage">{coverage ? `${coverage.covered_repositories} 个仓库已评分 · ${coverage.fresh_repositories ?? 0} 个数据在24小时内有效` : '正在确认当前体检覆盖'}</p>

      {status === 'loading' && <div className="ranking-state">正在加载当前体检排名…</div>}
      {status === 'error' && <div className="ranking-state error"><span>{error || '排行榜加载失败'}</span><button type="button" onClick={onRetry}>重试</button></div>}
      {status === 'ready' && payload?.status === 'insufficient_coverage' && <div className="ranking-state">尚无仓库完成当前五维体检。</div>}
      {status === 'ready' && top.length > 0 && <div className="ranking-list">{top.map((item) => <RankingItem key={item.repo} item={item} selected={selectedRepo === item.repo} onSelect={onSelect} />)}</div>}
      {selectedOutsideTop && <div className="ranking-current"><span>当前仓库</span><RankingItem item={payload.current} selected pinned onSelect={onSelect} /></div>}

      <div className="ranking-observation">
        <span>数据说明</span><p>排名与详情使用同一当前体检结果；历史趋势缺失时不生成模拟曲线。</p>
        <dl><div><dt>最近更新</dt><dd>{observedDate || '—'}</dd></div><div><dt>观察口径</dt><dd>当前体检快照</dd></div></dl>
      </div>
    </div>
  </aside>;
}
