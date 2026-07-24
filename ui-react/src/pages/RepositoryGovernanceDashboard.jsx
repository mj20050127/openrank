import { lazy, Suspense, useMemo, useState } from 'react';
import CommunityHealthEvolution from '../components/community-health/CommunityHealthEvolution';
import NewcomerOpportunityMap from '../components/newcomer/NewcomerOpportunityMap';
import { HealthDimensions } from '../components/governance/GovernanceVisuals';
import CompactHealthHeader from '../components/health/CompactHealthHeader';
import { adaptEcosystemContributors } from '../features/health/contributorParetoAdapter';
import { useGovernanceData } from '../hooks/useGovernanceData';
import { DIMENSIONS, valueFor } from '../utils/governanceConfig';
import './RepositoryGovernanceDashboard.css';

const EcosystemGraph3D = lazy(() => import('../components/ecosystem/EcosystemGraph3D'));

function anomalyTotal(records) {
  const values = records.map((record) => valueFor(record, 'activity')).filter((value) => value != null);
  if (values.length < 4) return 0;
  const average = values.reduce((sum, value) => sum + value, 0) / values.length;
  const deviation = Math.sqrt(values.reduce((sum, value) => sum + (value - average) ** 2, 0) / values.length);
  return deviation ? values.filter((value) => Math.abs((value - average) / deviation) >= 1.7).length : 0;
}

export default function RepositoryGovernanceDashboard({ initialRepo = 'microsoft/vscode', repositories = [], onSelectRepo, repositoryActionStatus }) {
  const repo = initialRepo;
  const [range, setRange] = useState('24');
  const [dimension, setDimension] = useState('vitality');
  const [refreshStatus, setRefreshStatus] = useState('idle');
  const [ecosystemMonth, setEcosystemMonth] = useState(null);
  const [ecosystemContributorSnapshot, setEcosystemContributorSnapshot] = useState({ month: null, nodes: [], status: 'loading' });
  const [ecosystemSelectedNodeId, setEcosystemSelectedNodeId] = useState(null);
  const [ecosystemHoveredNodeId, setEcosystemHoveredNodeId] = useState(null);

  const { payload, records, current, status, error, refresh } = useGovernanceData(repo, range);
  const paretoContributors = useMemo(
    () => adaptEcosystemContributors(ecosystemContributorSnapshot.nodes),
    [ecosystemContributorSnapshot.nodes],
  );


  const reset = () => {
    setRange('24');
    setDimension('vitality');
    setEcosystemMonth(null);
  };

  const refreshDashboard = async () => {
    setRefreshStatus('refreshing');
    try {
      await refresh();
      setRefreshStatus('idle');
    } catch {
      setRefreshStatus('idle');
    }
  };

  const selectDimension = (key) => {
    const next = DIMENSIONS[key] ? key : 'vitality';
    setDimension(next);
    setEcosystemMonth(null);
  };

  const dashboardHeader = <CompactHealthHeader
    repo={repo}
    range={range}
    onRange={setRange}
    latest={current}
    historyStart={records[0]}
    historyLatest={records.at(-1)}
    historyCount={records.length}
    anomalyCount={anomalyTotal(records)}
    status={refreshStatus}
    onRefresh={refreshDashboard}
    repositories={repositories}
    onSelectRepo={onSelectRepo}
    repositoryActionStatus={repositoryActionStatus}
  />;
  if (status === 'loading' && !payload) {
    return <div className="gov-dashboard health-observatory-main">{dashboardHeader}<div className="gov-loading"><span />正在加载真实治理数据…</div></div>;
  }

  if (status === 'error') {
    return <div className="gov-dashboard health-observatory-main">{dashboardHeader}<div className="gov-empty"><h2>无法加载治理数据</h2><p>{error}</p><button type="button" onClick={reset}>重置筛选</button></div></div>;
  }

  if (!records.length) {
    return <div className="gov-dashboard health-observatory-main">{dashboardHeader}<div className="gov-empty"><h2>当前范围暂无真实数据</h2><p>请搜索并切换其他仓库，或先为该仓库执行全量历史接入；系统不会用日级或演示数据替代。</p><button type="button" onClick={() => setRange('all')}>查看全量历史</button></div></div>;
  }



  return <div className="gov-dashboard health-observatory-main">
    {dashboardHeader}


    <main className="gov-main">
      <section className="health-primary-layout">
        <div className="health-primary-main gov-ecosystem-slot">
          <Suspense fallback={<div className="gov-panel ecosystem-lazy-loading">正在加载三维生态网络…</div>}>
            <EcosystemGraph3D
              rootRepo={repo}
              records={records}
              healthScore={current?.scores?.health}
              focusMonth={ecosystemMonth}
              onMonthFocus={setEcosystemMonth}
              onSetRoot={onSelectRepo}
              selectedNodeId={ecosystemSelectedNodeId}
              onSelectedNodeIdChange={setEcosystemSelectedNodeId}
              hoveredNodeId={ecosystemHoveredNodeId}
              onHoveredNodeIdChange={setEcosystemHoveredNodeId}
              onContributorsChange={setEcosystemContributorSnapshot}
            />
          </Suspense>
        </div>

        <aside className="health-context-column">
          <HealthDimensions
            current={current}
            selectedDimension={dimension}
            onSelect={selectDimension}
            contributors={paretoContributors}
            contributorMonth={ecosystemContributorSnapshot.month || ecosystemMonth}
            contributorStatus={ecosystemContributorSnapshot.status}
            selectedContributorId={ecosystemSelectedNodeId}
            hoveredContributorId={ecosystemHoveredNodeId}
            onSelectContributor={setEcosystemSelectedNodeId}
            onHoverContributor={setEcosystemHoveredNodeId}
          />
        </aside>
      </section>
      <CommunityHealthEvolution
        records={records}
        selectedMonth={ecosystemMonth}
        onSelectedMonthChange={setEcosystemMonth}
      />
      <NewcomerOpportunityMap onSelectRepo={onSelectRepo} />
    </main>
  </div>;
}