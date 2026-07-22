import { useEffect, useMemo, useState } from 'react';
import { searchRepositories } from '../../service/api';
import { DIMENSIONS, RANGE_OPTIONS } from '../../utils/governanceConfig';
import HealthScale from './HealthScale';
import './CompactHealthHeader.css';

const dimensions = Object.entries(DIMENSIONS);
const REPOSITORY_LOGOS = Object.freeze({
  'microsoft/vscode': ['https://raw.githubusercontent.com/microsoft/vscode/main/resources/win32/code_150x150.png'],
  'kubernetes/kubernetes': ['https://raw.githubusercontent.com/kubernetes/kubernetes/master/logo/logo.png'],
  'formatjs/formatjs': ['https://raw.githubusercontent.com/formatjs/formatjs/main/website/img/logo.svg'],
  'odoo/odoo': ['https://raw.githubusercontent.com/odoo/odoo/19.0/addons/web/static/img/logo.png'],
});

function CompactIcon({ name }) {
  if (name === 'sync') return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 5.7" /><path d="M20 5v6h-6" /></svg>;
  if (name === 'github') return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2.8a9.3 9.3 0 0 0-2.9 18.1c.5.1.6-.2.6-.5v-1.8c-2.8.6-3.4-1.2-3.4-1.2-.5-1.2-1.1-1.5-1.1-1.5-.9-.6.1-.6.1-.6 1 0 1.6 1.1 1.6 1.1.9 1.6 2.4 1.1 2.9.9.1-.7.4-1.1.7-1.4-2.2-.3-4.6-1.1-4.6-4.9 0-1.1.4-2 1-2.7-.1-.3-.4-1.3.1-2.7 0 0 .8-.3 2.8 1a9.5 9.5 0 0 1 5 0c1.9-1.3 2.8-1 2.8-1 .5 1.4.2 2.4.1 2.7.6.7 1 1.6 1 2.7 0 3.8-2.3 4.6-4.6 4.9.4.3.7.9.7 1.8v2.7c0 .3.2.6.7.5A9.3 9.3 0 0 0 12 2.8Z" /></svg>;
  if (name === 'fork') return <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="7" cy="5" r="2" /><circle cx="17" cy="5" r="2" /><circle cx="12" cy="19" r="2" /><path d="M7 7v2.5c0 2 1.6 3.5 3.5 3.5H12m5-6v2.5c0 2-1.6 3.5-3.5 3.5H12v4" /></svg>;
  if (name === 'robot') return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="7" width="16" height="12" rx="3" /><path d="M12 7V4m-3 8h.01M15 12h.01M8 16h8M2 12v3m20-3v3" /></svg>;
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 1.4 4.1L17.5 8.5l-4.1 1.4L12 14l-1.4-4.1-4.1-1.4 4.1-1.4L12 3Z" /><path d="m18.5 14 .8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z" /></svg>;
}

function RepositoryAvatar({ repo }) {
  const [attempt, setAttempt] = useState(0);
  const candidates = REPOSITORY_LOGOS[String(repo || '').toLowerCase()] || [];
  if (!candidates[attempt]) {
    const fallback = String(repo || '?').split('/').at(-1).slice(0, 2).toUpperCase();
    return <span className="compact-repo__fallback">{fallback}</span>;
  }
  return <img src={candidates[attempt]} alt="" onError={() => setAttempt((value) => value + 1)} />;
}

function formatSnapshotDate(value) {
  const match = String(value || '').match(/^\d{4}-\d{2}-\d{2}/);
  return match?.[0] || String(value || '').slice(0, 7) || '暂无快照';
}

function formatRepositoryCount(value) {
  if (value === null || value === undefined || value === '') return '—';
  const number = Number(value);
  if (!Number.isFinite(number)) return '—';
  return new Intl.NumberFormat('zh-CN', {
    notation: number >= 10000 ? 'compact' : 'standard',
    maximumFractionDigits: 1,
  }).format(number);
}

function repositorySearchText(item) {
  return [
    item.repo,
    item.description,
    item.language,
    ...(item.domains || []),
    ...(item.topics || []),
  ].filter(Boolean).join(' ').toLowerCase();
}

function repositorySearchRank(item, term) {
  const fullName = String(item.repo || '').toLowerCase();
  const [owner = '', repositoryName = ''] = fullName.split('/');
  if (repositoryName.startsWith(term)) return 0;
  if (fullName.startsWith(term)) return 1;
  if (owner.startsWith(term)) return 2;
  if (repositorySearchText(item).split(/\s+/).some((word) => word.startsWith(term))) return 3;
  return 4;
}

function repositoryStatusLabel(item) {
  if (item.sync_status === 'ready') return '数据就绪';
  if (item.sync_status === 'partial') return '部分数据';
  if (item.sync_status === 'failed') return '接入失败';
  if (item.sync_status === 'syncing') return '正在同步';
  return '待接入';
}

export function RepositorySearch({ repo, repositories = [], onSelectRepo, actionStatus }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState(repo || '');
  const [submitting, setSubmitting] = useState(false);
  const [remoteRepositories, setRemoteRepositories] = useState([]);
  const [searching, setSearching] = useState(false);
  const normalized = query.trim();
  const validFullName = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(normalized);
  const exact = repositories.find((item) => item.repo.toLowerCase() === normalized.toLowerCase());
  const matches = useMemo(() => {
    const term = normalized.toLowerCase();
    const merged = new Map(remoteRepositories.map((item) => [item.repo.toLowerCase(), item]));
    repositories.forEach((item) => merged.set(item.repo.toLowerCase(), item));
    const candidates = [...merged.values()];
    if (!term) return repositories.slice(0, 8);
    return candidates
      .filter((item) => repositorySearchText(item).includes(term))
      .sort((a, b) => repositorySearchRank(a, term) - repositorySearchRank(b, term)
        || Number(b.stars || 0) - Number(a.stars || 0)
        || a.repo.localeCompare(b.repo))
      .slice(0, 8);
  }, [normalized, remoteRepositories, repositories]);
  const busy = submitting || actionStatus?.tone === 'loading';

  useEffect(() => {
    if (!open) setQuery(repo || '');
  }, [repo, open]);

  useEffect(() => {
    if (!open || !normalized || validFullName) {
      setRemoteRepositories([]);
      setSearching(false);
      return undefined;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setSearching(true);
      try {
        const response = await searchRepositories(normalized, 8, controller.signal);
        setRemoteRepositories(response?.data || []);
      } catch (error) {
        if (error?.name !== 'AbortError') setRemoteRepositories([]);
      } finally {
        if (!controller.signal.aborted) setSearching(false);
      }
    }, 300);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [normalized, open, validFullName]);

  const choose = async (nextRepo) => {
    const next = String(nextRepo || '').trim();
    if (!next || busy) return;
    setQuery(next);
    setSubmitting(true);
    try {
      const switched = await onSelectRepo?.(next);
      if (switched !== false) setOpen(false);
    } finally {
      setSubmitting(false);
    }
  };

  return <div className={`compact-repo-picker ${open ? 'open' : ''}`}>
    <button
      type="button"
      className="compact-repo-picker__toggle"
      onClick={() => setOpen((value) => {
        const nextOpen = !value;
        if (nextOpen) setQuery('');
        return nextOpen;
      })}
      aria-expanded={open}
      aria-haspopup="listbox"
    >
      切换仓库
    </button>
    {open && <div className="compact-repo-picker__panel">
      <div className="compact-repo-picker__input-row">
        <input
          autoFocus
          value={query}
          placeholder="搜索仓库或输入 owner/repo"
          aria-label="搜索或添加 GitHub 仓库"
          role="combobox"
          aria-expanded="true"
          aria-controls="repository-search-results"
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Escape') setOpen(false);
            if (event.key === 'Enter' && validFullName) {
              event.preventDefault();
              void choose(exact?.repo || normalized);
            }
          }}
        />
        <button
          type="button"
          className="compact-repo-picker__submit"
          disabled={!validFullName || busy || normalized.toLowerCase() === String(repo || '').toLowerCase()}
          onClick={() => void choose(exact?.repo || normalized)}
        >
          {busy ? '处理中…' : exact ? '切换' : '添加并分析'}
        </button>
      </div>
      <div id="repository-search-results" className="compact-repo-picker__results" role="listbox">
        {matches.map((item) => <button
          type="button"
          role="option"
          aria-selected={item.repo === repo}
          className={item.repo === repo ? 'selected' : ''}
          key={item.repo}
          onClick={() => void choose(item.repo)}
          disabled={busy}
        >
          <span><strong>{item.repo}</strong><small>{item.description || item.language || 'GitHub 仓库'}</small></span>
          <em>{repositoryStatusLabel(item)}</em>
        </button>)}
        {!matches.length && validFullName && <button
          type="button"
          className="compact-repo-picker__add"
          onClick={() => void choose(normalized)}
          disabled={busy}
        >
          <span><strong>添加并分析 {normalized}</strong><small>验证 GitHub 仓库并采集全量历史</small></span>
        </button>}
        {searching && <p>正在搜索 GitHub 仓库…</p>}
        {!matches.length && !validFullName && !searching && <p>未找到匹配仓库；也可以输入完整的 owner/repo 后添加。</p>}
      </div>
      {actionStatus?.text && <p className={`compact-repo-picker__status ${actionStatus.tone || ''}`}>{actionStatus.text}</p>}
    </div>}
  </div>;
}
export default function CompactHealthHeader({
  repo,
  range,
  onRange,
  latest,
  historyStart,
  historyLatest,
  historyCount,
  anomalyCount,
  status,
  onRefresh,
  onOpenAI,
  repositories = [],
  onSelectRepo,
  repositoryActionStatus,
}) {
  const health = latest?.scores?.health;
  const completeness = latest?.data_completeness == null ? null : latest.data_completeness * 100;
  const weak = dimensions
    .map(([key, config]) => ({ key, label: config.label, value: latest?.scores?.[key] }))
    .filter((item) => item.value !== null && item.value !== undefined)
    .sort((a, b) => a.value - b.value)[0];
  const snapshot = formatSnapshotDate(historyLatest?.dt || latest?.dt);
  const startMonth = String(historyStart?.dt || '').slice(0, 7) || '—';
  const endMonth = String(historyLatest?.dt || '').slice(0, 7) || '—';
  const repositoryUrl = repo ? `https://github.com/${repo}` : '#';

  const catalogRepository = repositories.find((item) => item.repo === repo);
  const currentMetadata = latest?.evidence?.metadata || {};
  const repositoryMetadata = {
    stars: currentMetadata.stars ?? catalogRepository?.stars,
    forks: currentMetadata.forks ?? catalogRepository?.forks,
  };

  return <header className="compact-health-header health-panel">
    <div className="compact-health-header__main">
      <section className="compact-repo">
        <div className="compact-repo__avatar"><RepositoryAvatar key={repo} repo={repo} /></div>
        <div className="compact-repo__body">
          <span className="compact-repo__eyebrow">REPOSITORY DOSSIER · 仓库档案</span>
          <div className="compact-repo__title-row">
            <h1 title={repo}>{repo || '请选择仓库'}</h1>
            <RepositorySearch
              repo={repo}
              repositories={repositories}
              onSelectRepo={onSelectRepo}
              actionStatus={repositoryActionStatus}
            />
          </div>
          <div className="compact-repo__meta">
            <a href={repositoryUrl} target="_blank" rel="noreferrer"><CompactIcon name="github" />GitHub</a>
            <span className="compact-repo__stat" title="GitHub Stars"><b aria-hidden="true">★</b><strong>{formatRepositoryCount(repositoryMetadata.stars)}</strong></span>
            <span className="compact-repo__stat" title="GitHub Forks"><CompactIcon name="fork" /><strong>{formatRepositoryCount(repositoryMetadata.forks)}</strong></span>
            <span>快照: {snapshot}</span>
          </div>
        </div>
      </section>

      <section className="header-metric header-score">
        <span className="header-metric__label">综合健康 <small>OVERALL HEALTH</small></span>
        <HealthScale score={health} />
      </section>

      <section className="header-metric header-weakest">
        <div><span className="header-metric__label">最弱维度 <small>WEAKEST DIMENSION</small></span><strong className="header-metric__value"><span>{weak?.label || '暂无数据'}</span>{weak?.value == null ? '' : Number(weak.value).toFixed(1)}</strong></div>
      </section>

      <section className="header-metric header-anomaly">
        <div><span className="header-metric__label">异常 <small>ANOMALIES</small></span><strong className="header-metric__value">{anomalyCount ?? '—'}</strong></div>
      </section>

      <section className="header-metric header-completeness">
        <div><span className="header-metric__label">完整度 <small>COMPLETENESS</small></span><strong className="header-metric__value">{completeness == null ? '—' : `${Math.round(completeness)}%`}</strong></div>
      </section>

      <div className="compact-header-actions">
        <button type="button" className="secondary" onClick={onRefresh} disabled={status === 'refreshing'} title="同步当前仓库健康数据">
          <CompactIcon name="sync" /><span>{status === 'refreshing' ? '同步中…' : '同步数据'}</span>
        </button>
        {onOpenAI && <button type="button" className="primary" onClick={onOpenAI} title="打开现有 AI 治理助手">
          <CompactIcon name="robot" /><span className="ai-action-label">AI 治理助手</span>
        </button>}
      </div>
    </div>

    <div className="compact-health-header__controls">
      <div className="range-control">
        <span>观察范围 <small>OBSERVATION PERIOD</small></span>
        <div className="segmented-control" aria-label="观察范围">
          {RANGE_OPTIONS.filter((item) => item.value !== '60').map((item) => <button type="button" key={item.value} className={range === item.value ? 'active' : ''} onClick={() => onRange(item.value)}>{item.label.replace('历史', '')}</button>)}
        </div>
      </div>
      <div className="range-ruler" aria-label={`数据范围 ${startMonth} 至 ${endMonth}，共 ${historyCount || 0} 个月`}><i /></div>
    </div>
  </header>;
}