import { useCallback, useEffect, useState } from 'react';
import './App.css';
import RepositoryGovernanceDashboard from './pages/RepositoryGovernanceDashboard';
import HealthRankingRail from './components/governance/HealthRankingRail';
import {
  fetchRepositoryCatalog,
  fetchHealthRanking,
  importRepository,
  fetchImportJob,
} from './service/api';

const REPO_PATTERN = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;

function App() {
  const [selectedRepo, setSelectedRepo] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('repo');
    return requested && REPO_PATTERN.test(requested) ? requested : 'microsoft/vscode';
  });
  const [repositoryCatalog, setRepositoryCatalog] = useState([]);
  const [healthRanking, setHealthRanking] = useState(null);
  const [rankingStatus, setRankingStatus] = useState('loading');
  const [rankingError, setRankingError] = useState('');
  const [repoImportStatus, setRepoImportStatus] = useState(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.resolve().then(async () => {
      try {
        const response = await fetchRepositoryCatalog();
        if (!cancelled) setRepositoryCatalog(response?.data || []);
      } catch {
        if (!cancelled) setRepositoryCatalog([]);
      }
    });
    return () => { cancelled = true; };
  }, []);

  const loadHealthRanking = useCallback(async () => {
    setRankingStatus('loading');
    setRankingError('');
    try {
      const response = await fetchHealthRanking(selectedRepo, 10);
      setHealthRanking(response);
      setRankingStatus('ready');
    } catch (error) {
      setRankingError(error?.message || '健康排行榜加载失败');
      setRankingStatus('error');
    }
  }, [selectedRepo]);

  useEffect(() => {
    void Promise.resolve().then(loadHealthRanking);
  }, [loadHealthRanking]);

  const selectGlobalRepo = async (repo) => {
    const next = repo?.trim();
    if (!next || !REPO_PATTERN.test(next)) {
      setRepoImportStatus({ tone: 'error', text: '请输入 owner/repo 格式' });
      return false;
    }

    const known = repositoryCatalog.find((item) => item.repo.toLowerCase() === next.toLowerCase());
    const hasUsableData = known && (
      known.sync_status === 'ready'
      || Number(known.metric_count || 0) > 0
      || Number(known.month_count || 0) > 0
      || (known.sync_status === 'partial' && known.opendigger_supported === false)
    );
    if (hasUsableData) {
      setSelectedRepo(known.repo);
      setRepoImportStatus(null);
      return true;
    }

    setRepoImportStatus({ tone: 'loading', text: '正在验证仓库并创建全量采集任务…' });
    try {
      let job = await importRepository(next);
      for (let attempt = 0; attempt < 120 && ['queued', 'running'].includes(job.status); attempt += 1) {
        setRepoImportStatus({
          tone: 'loading',
          text: `${job.stage || '排队中'} · ${Math.round((job.progress || 0) * 100)}%`,
        });
        await new Promise((resolve) => window.setTimeout(resolve, 1500));
        job = await fetchImportJob(job.job_id);
      }
      if (job.status !== 'succeeded') throw new Error(job.error || '仓库接入失败');

      const response = await fetchRepositoryCatalog();
      setRepositoryCatalog(response?.data || []);
      const canonical = job.result?.repo || job.repo || next;
      setSelectedRepo(canonical);
      setRepoImportStatus({
        tone: job.stage === 'degraded_ready' ? 'warn' : 'success',
        text: job.stage === 'degraded_ready' ? '已降级接入：无 OpenDigger 历史' : '全量月度历史已接入',
      });
      return true;
    } catch (error) {
      setRepoImportStatus({ tone: 'error', text: error?.message || '仓库接入失败' });
      return false;
    }
  };

  return (
    <div className="app-shell">
      <div className="content-grid health-workspace">
        <HealthRankingRail
          payload={healthRanking}
          status={rankingStatus}
          error={rankingError}
          selectedRepo={selectedRepo}
          onSelect={selectGlobalRepo}
          onRetry={loadHealthRanking}
        />
        <main className="chat-column health-column health-workspace-main">
          <RepositoryGovernanceDashboard
            initialRepo={selectedRepo}
            repositories={repositoryCatalog}
            onSelectRepo={selectGlobalRepo}
            repositoryActionStatus={repoImportStatus}
          />
        </main>
      </div>
    </div>
  );
}

export default App;