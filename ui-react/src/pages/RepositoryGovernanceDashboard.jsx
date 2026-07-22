import { lazy, Suspense, useMemo, useState } from 'react';
import { EvidencePanel } from '../components/governance/EvidencePanel';
import {
  GovernanceTrendChart,
  HealthDimensions,
  MetricSmallMultiples,
} from '../components/governance/GovernanceVisuals';
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

export default function RepositoryGovernanceDashboard({ initialRepo = 'microsoft/vscode', repositories = [], onSelectRepo, onOpenAI, repositoryActionStatus }) {
  const repo = initialRepo;
  const [range, setRange] = useState('24');
  const [dimension, setDimension] = useState('vitality');
  const [metrics, setMetrics] = useState(DIMENSIONS.vitality.metrics.slice(0, 2));
  const [focusRange, setFocusRange] = useState(null);
  const [evidence, setEvidence] = useState(null);
  const [refreshStatus, setRefreshStatus] = useState('idle');
  const [ecosystemMonth, setEcosystemMonth] = useState(null);
  const [ecosystemContributorSnapshot, setEcosystemContributorSnapshot] = useState({ month: null, nodes: [], status: 'loading' });
  const [ecosystemSelectedNodeId, setEcosystemSelectedNodeId] = useState(null);
  const [ecosystemHoveredNodeId, setEcosystemHoveredNodeId] = useState(null);

  const { payload, records, current, coverage, currentError, status, error, refresh } = useGovernanceData(repo, range);

  const focusedRecords = useMemo(() => {
    if (!focusRange || !records.length) return records;
    return records.slice(focusRange.start, focusRange.end + 1);
  }, [records, focusRange]);
  const paretoContributors = useMemo(
    () => adaptEcosystemContributors(ecosystemContributorSnapshot.nodes),
    [ecosystemContributorSnapshot.nodes],
  );


  const reset = () => {
    setRange('24');
    setDimension('vitality');
    setMetrics(DIMENSIONS.vitality.metrics.slice(0, 2));
    setFocusRange(null);
    setEvidence(null);
    setEcosystemMonth(null);
  };

  const toggleMetric = (metric) => {
    setMetrics((current) => {
      if (current.includes(metric)) return current.length > 1 ? current.filter((item) => item !== metric) : current;
      return [...current, metric];
    });
  };

  const handleZoom = (event) => {
    const batch = event.batch?.[0] || event;
    if (batch.start == null || batch.end == null || !records.length) return;
    const start = Math.round((batch.start / 100) * (records.length - 1));
    const end = Math.round((batch.end / 100) * (records.length - 1));
    setFocusRange({ start: Math.min(start, end), end: Math.max(start, end) });
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
    setMetrics(DIMENSIONS[next].metrics.slice(0, 2));
    setEvidence(null);
    setEcosystemMonth(null);
  };

  const dashboardHeader = <CompactHealthHeader
    repo={repo}
    range={range}
    onRange={(value) => { setRange(value); setFocusRange(null); }}
    latest={current}
    historyStart={focusedRecords[0]}
    historyLatest={focusedRecords.at(-1)}
    historyCount={focusedRecords.length}
    anomalyCount={anomalyTotal(focusedRecords)}
    status={refreshStatus}
    onRefresh={refreshDashboard}
    onOpenAI={onOpenAI}
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
              records={focusedRecords}
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

      <section className="health-evidence-row">
        <EvidencePanel records={focusedRecords} dimension={dimension} evidence={evidence} />
      </section>

      <section className="health-evolution-section">
        <GovernanceTrendChart
          records={focusedRecords}
          selectedDimension={dimension}
          selectedMetrics={metrics}
          focusMonth={ecosystemMonth}
          onToggleMetric={toggleMetric}
          onAnomaly={(point) => {
            setEvidence(point);
            setEcosystemMonth(String(point.record?.dt || '').slice(0, 7) || null);
          }}
          onZoom={handleZoom}
        />

        <MetricSmallMultiples records={focusedRecords} dimension={dimension} />

        <section className="diagnostic-section">
          <div className="section-heading">
            <div><span className="eyebrow">数据质量</span><h2>OpenDigger 指标覆盖</h2></div>
            <p>{coverage ? `${coverage.verified_metric_count}/${coverage.canonical_metric_count} 个规范指标与源端一致` : '尚未执行新版完整性验证'}</p>
          </div>
          {currentError && <p className="gov-inline-warning">当前体检尚不可用：{currentError}</p>}
          <div className="coverage-matrix">
            {(coverage?.metrics || []).map((item) => (
              <div className={`coverage-cell ${item.status}`} key={item.metric}>
                <strong>{item.metric}</strong>
                <span>{item.first_month?.slice(0, 7) || '—'} 至 {item.latest_month?.slice(0, 7) || '—'}</span>
                <small>{item.status === 'available' ? `${item.source_key_count} 月 · 缺失 ${item.missing_keys.length} · 遗留 ${item.extra_keys.length}` : item.status}</small>
              </div>
            ))}
          </div>
        </section>
      </section>
    </main>
  </div>;
}