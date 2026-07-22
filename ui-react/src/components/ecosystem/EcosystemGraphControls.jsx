export default function EcosystemGraphControls({
  filters,
  onFilters,
  mode,
  onMode,
  onFit,
  onReset,
  onFullscreen,
}) {
  return <div className="ecosystem-controls" aria-label="生态网络工具">
    <div className="ecosystem-mode" aria-label="布局模式">
      <button type="button" className={mode === 'explore' ? 'active' : ''} onClick={() => onMode('explore')}><span aria-hidden="true">◎</span>探索</button>
      <button type="button" className={mode === 'community' ? 'active' : ''} onClick={() => onMode('community')}><span aria-hidden="true">◌</span>社区</button>
    </div>
    <label className="ecosystem-role-filter">
      <span>角色</span>
      <select value={filters.role} onChange={(event) => onFilters({ ...filters, role: event.target.value })}>
        <option value="all">全部</option>
        <option value="core">核心</option>
        <option value="active">活跃</option>
        <option value="new">新加入</option>
        <option value="risk">流失风险</option>
        <option value="inactive">不活跃</option>
      </select>
    </label>
    <label className="ecosystem-strength">
      <span>贡献 ≥ {filters.minimum}</span>
      <input type="range" min="0" max="100" step="5" value={filters.minimum} onChange={(event) => onFilters({ ...filters, minimum: Number(event.target.value) })} />
    </label>
    <label className="ecosystem-check"><input type="checkbox" checked={filters.onlyNeighbors} onChange={(event) => onFilters({ ...filters, onlyNeighbors: event.target.checked })} /><span>仅看邻居</span></label>
    <div className="ecosystem-command-group">
      <button type="button" onClick={onFit} title="适应视图"><span aria-hidden="true">⌗</span>适应</button>
      <button type="button" onClick={onReset} title="重置网络"><span aria-hidden="true">↺</span>重置</button>
      <button type="button" onClick={onFullscreen} title="全屏查看"><span aria-hidden="true">⛶</span>全屏</button>
    </div>
  </div>;
}