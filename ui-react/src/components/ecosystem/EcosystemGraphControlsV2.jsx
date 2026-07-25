import { useMemo, useState } from 'react';

const MODE_OPTIONS = [['structure', '结构'], ['community', '社区']];

function CommandIcon({ type }) {
  if (type === 'search') return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.5" cy="10.5" r="5.5" /><path d="m15 15 4 4" /></svg>;
  if (type === 'fit') return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 4H4v4M16 4h4v4M4 16v4h4M20 16v4h-4" /></svg>;
  if (type === 'reset') return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M19 8a8 8 0 1 0 1 6" /><path d="M19 3v5h-5" /></svg>;
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4H4v5M15 4h5v5M4 15v5h5M20 15v5h-5" /><path d="m4 9 6-6M20 9l-6-6M4 15l6 6M20 15l-6 6" /></svg>;
}

export default function EcosystemGraphControlsV2({ filters, onFilters, mode, onMode, nodes, onSearchSelect, onFit, onReset, onFullscreen }) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState('');
  const results = useMemo(() => {
    const value = query.trim().toLowerCase();
    if (!value) return [];
    return (nodes || []).filter((node) => String(node.login || node.repo || node.label || '').toLowerCase().includes(value)).slice(0, 8);
  }, [nodes, query]);

  return <div className="ecosystem-controls ecosystem-controls-v2" aria-label="生态网络工具">
    <div className="ecosystem-mode" aria-label="网络模式">
      {MODE_OPTIONS.map(([value, label]) => <button key={value} type="button" className={mode === value ? 'active' : ''} onClick={() => onMode(value)}>{label}</button>)}
    </div>
    <label className="ecosystem-role-filter">
      <select value={filters.role} onChange={(event) => onFilters({ ...filters, role: event.target.value })} aria-label="角色过滤">
        <option value="all">角色：全部</option><option value="core">核心维护者</option><option value="active">活跃贡献者</option><option value="new">新贡献者</option><option value="risk">流失风险</option><option value="inactive">低活跃</option>
      </select>
    </label>
    <label className="ecosystem-strength"><span>贡献度阈值</span><input type="range" min="0" max="100" step="5" value={filters.minimum} onChange={(event) => onFilters({ ...filters, minimum: Number(event.target.value) })} /><b>≥ {filters.minimum}</b></label>
    <div className="ecosystem-command-group">
      <div className="ecosystem-search">
        <button type="button" title="搜索节点" aria-label="搜索节点" onClick={() => setSearchOpen((open) => !open)}><CommandIcon type="search" /></button>
        {searchOpen && <div className="ecosystem-search-popover">
          <input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索 login 或仓库" aria-label="搜索 login 或仓库" />
          {query && <div className="ecosystem-search-results">{results.length ? results.map((node) => <button type="button" key={node.id} onClick={() => { onSearchSelect(node); setSearchOpen(false); setQuery(''); }}><span>{node.type === 'repository' ? '▣' : '●'}</span>{node.login || node.repo || node.label}</button>) : <p>没有匹配节点</p>}</div>}
        </div>}
      </div>
      <button type="button" onClick={onFit} title="适应视图" aria-label="适应视图"><CommandIcon type="fit" /></button>
      <button type="button" onClick={onReset} title="重置网络" aria-label="重置网络"><CommandIcon type="reset" /></button>
      <button type="button" onClick={onFullscreen} title="全屏查看" aria-label="全屏查看"><CommandIcon type="fullscreen" /></button>
    </div>
  </div>;
}
