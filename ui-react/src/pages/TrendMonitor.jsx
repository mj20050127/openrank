import { useCallback, useEffect, useMemo, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { fetchTrendDerived, fetchTrendSeries, fetchCompositeTrends, fetchRiskViability } from '../service/api';

const OVERVIEW_CARDS = [
  { key: 'metric_activity', title: '活跃度趋势', desc: 'commit / issue / PR 综合活跃' },
  { key: 'metric_pr_response_time_h', title: '响应性趋势', desc: 'Time to First Response & Close' },
  { key: 'metric_bus_factor', title: '风险趋势', desc: 'Bus Factor / Top1 Share' },
];

const RESPONSIVENESS_METRICS = [
  { key: 'metric_pr_response_time_h', title: 'PR Time to First Response (h)', unit: 'h' },
  { key: 'metric_issue_response_time_h', title: 'Issue Time to First Response (h)', unit: 'h' },
  { key: 'metric_pr_resolution_duration_h', title: 'PR Time to Close (h)', unit: 'h' },
  { key: 'metric_issue_resolution_duration_h', title: 'Issue Time to Close (h)', unit: 'h' },
];

const ACTIVITY_METRICS = [
  { key: 'metric_activity', title: 'Activity' },
  { key: 'metric_participants', title: 'Participants' },
  { key: 'metric_new_contributors', title: 'New Contributors' },
  { key: 'metric_openrank', title: 'OpenRank' },
  { key: 'metric_attention', title: 'Attention' },
  { key: 'metric_activity_growth', title: 'Activity Growth' },
];

const RISK_METRICS = [
  { key: 'metric_bus_factor', title: 'Bus Factor' },
  { key: 'metric_hhi', title: 'HHI' },
  { key: 'metric_top1_share', title: 'Top1 Share' },
  { key: 'metric_retention_rate', title: 'Retention Rate' },
  { key: 'metric_scorecard_score', title: 'Scorecard Score' },
];

const METRIC_KEYS = Array.from(
  new Set([
    ...OVERVIEW_CARDS.map((c) => c.key),
    ...RESPONSIVENESS_METRICS.map((m) => m.key),
    ...ACTIVITY_METRICS.map((m) => m.key),
    ...RISK_METRICS.map((m) => m.key),
    'metric_issues_new',
    'metric_issues_closed',
    'metric_prs_new',
    'metric_change_requests_accepted',
  ]),
);

const CHAOSS_LABELS = {
  metric_issue_response_time_h: 'Issue Response Time',
  metric_issue_resolution_duration_h: 'Issue Resolution Duration',
  metric_issue_age_h: 'Issue Age',
  metric_pr_response_time_h: 'Time to First Response',
  metric_pr_resolution_duration_h: 'Time to Close (PR)',
  metric_pr_age_h: 'PR Age',
};

const formatNumber = (val, unit) => {
  if (val === null || val === undefined || Number.isNaN(val)) return '--';
  const num = typeof val === 'number' ? val : Number(val);
  if (Number.isNaN(num)) return '--';
  if (Math.abs(num) >= 1000) return `${num.toFixed(0)}`;
  if (Math.abs(num) >= 10) return `${num.toFixed(1)}${unit || ''}`;
  return `${num.toFixed(2)}${unit || ''}`;
};

function buildLineOption(metricKey, data, derived, accent = '#2563eb', unit = '') {
  const x = data.map((d) => d.dt);
  const y = data.map((d) => d.value);
  const markLines = [];
  if (derived?.rolling_mean_7d !== undefined && derived?.rolling_mean_7d !== null) {
    markLines.push({ yAxis: derived.rolling_mean_7d, name: '7d mean' });
  }
  if (derived?.rolling_median_7d !== undefined && derived?.rolling_median_7d !== null) {
    markLines.push({ yAxis: derived.rolling_median_7d, name: '7d median' });
  }

  return {
    tooltip: { trigger: 'axis', valueFormatter: (v) => formatNumber(v, unit) },
    grid: { left: 56, right: 16, top: 32, bottom: 46 },
    xAxis: { type: 'category', data: x, boundaryGap: false },
    yAxis: { type: 'value' },
    series: [
      {
        name: metricKey,
        type: 'line',
        data: y,
        smooth: true,
        showSymbol: false,
        lineStyle: { color: accent, width: 2 },
        areaStyle: { color: `${accent}1a` },
        markLine: markLines.length ? { symbol: 'none', label: { formatter: '{b}' }, data: markLines } : undefined,
      },
    ],
  };
}



const TIME_PRESETS = [
  { value: 180, label: '180天' },
  { value: 365, label: '365天' },
  { value: 'all', label: '全量' },
];


export default function TrendMonitor({ repo }) {
  const [timeRange, setTimeRange] = useState(180);
  const [activeTab, setActiveTab] = useState('overview');
  const [series, setSeries] = useState([]);
  const [derived, setDerived] = useState({});
  const [composite, setComposite] = useState({ series: null, kpis: null, explain: null });
  const [riskViability, setRiskViability] = useState({ kpis: null, series: null, explain: null });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
  }, [repo]);

  const dateRange = useMemo(() => {
    const end = new Date();
    if (timeRange === 'all') {
      // 对于全量数据，设置一个默认的起始日期（例如一年前）
      const start = new Date(end.getTime() - 365 * 24 * 60 * 60 * 1000);
      const fmt = (d) => d.toISOString().split('T')[0];
      return { start: fmt(start), end: fmt(end) };
    }
    const start = new Date(end.getTime() - timeRange * 24 * 60 * 60 * 1000);
    const fmt = (d) => d.toISOString().split('T')[0];
    return { start: fmt(start), end: fmt(end) };
  }, [timeRange]);

  const seriesMap = useMemo(() => {
    const map = {};
    series.forEach((row) => {
      METRIC_KEYS.forEach((key) => {
        if (row[key] === null || row[key] === undefined) return;
        if (!map[key]) map[key] = [];
        map[key].push({ dt: row.dt, value: typeof row[key] === 'number' ? row[key] : Number(row[key]) });
      });
    });
    return map;
  }, [series]);

  const latestValue = useCallback((key) => {
    const arr = seriesMap[key] || [];
    if (!arr.length) return null;
    return arr[arr.length - 1].value;
  }, [seriesMap]);

  const delta = useCallback((key) => {
    const arr = seriesMap[key] || [];
    if (arr.length < 2) return null;
    return arr[arr.length - 1].value - arr[0].value;
  }, [seriesMap]);

  

  const load = useCallback(async () => {
    if (!repo) {
      setError('请选择仓库');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const payload = { repo: repo, metrics: METRIC_KEYS };
      // 全量数据时不传递start和end，让后端自动获取完整范围
      if (timeRange !== 'all') {
        if (dateRange.start) payload.start = dateRange.start;
        if (dateRange.end) payload.end = dateRange.end;
      }
      const windowDays = timeRange === 'all' ? 180 : Math.max(30, Math.min(180, Number(timeRange) || 180));
      
      // 构建各个API的参数
      const seriesParams = { ...payload };
      const derivedParams = { ...payload, slope_window: timeRange === 'all' ? 30 : Math.min(14, timeRange) };
      const compositeParams = { 
        repo: repo, 
        window_days: windowDays 
      };
      if (timeRange !== 'all') {
        if (dateRange.start) compositeParams.start = dateRange.start;
        if (dateRange.end) compositeParams.end = dateRange.end;
      }
      
      // 构建风险可行性参数
      const riskParams = { repo };
      if (timeRange !== 'all') {
        if (dateRange.start) riskParams.start = dateRange.start;
        if (dateRange.end) riskParams.end = dateRange.end;
      }
      
      const [seriesRes, derivedRes, compositeRes, riskRes] = await Promise.all([
        fetchTrendSeries(seriesParams),
        fetchTrendDerived(derivedParams),
        fetchCompositeTrends(compositeParams),
        fetchRiskViability(riskParams.repo, riskParams.start, riskParams.end)
      ]);
      setSeries(seriesRes.series || seriesRes.data?.series || []);
      setDerived(derivedRes.derived || derivedRes.data?.derived || {});
      setComposite({
        series: compositeRes.series || compositeRes.data?.series,
        kpis: compositeRes.kpis || compositeRes.data?.kpis,
        explain: compositeRes.explain || compositeRes.data?.explain,
      });
      setRiskViability({
        kpis: riskRes.kpis || riskRes.data?.kpis,
        series: riskRes.series || riskRes.data?.series,
        explain: riskRes.explain || riskRes.data?.explain,
      });
    } catch (err) {
      setError(err?.message || '加载失败，请稍后再试');
      setSeries([]);
      setDerived({});
    } finally {
      setLoading(false);
    }
  }, [repo, dateRange.start, dateRange.end, timeRange]);

  useEffect(() => {
    load();
  }, [load]);

  const renderStatsRow = (items) => (
    <>
      {items.map((item) => {
        const val = latestValue(item.key);
        const diff = delta(item.key);
        return (
          <div key={item.key} className="trend-stat-card">
            <div className="stat-label">{item.title}</div>
            <div className="stat-value">{formatNumber(val, item.unit)}</div>
            <div className={`stat-delta ${diff > 0 ? 'up' : diff < 0 ? 'down' : ''}`}>
              {diff === null ? '—' : `${diff > 0 ? '+' : ''}${formatNumber(diff, item.unit)}`}
            </div>
          </div>
        );
      })}
    </>
  );

  const renderChartGrid = (items, accent = '#2563eb') => (
    <>
      {items.map((item) => (
        <div key={item.key} className="chart-card">
          <div className="chart-head">
            <div>
              <div className="eyebrow">{CHAOSS_LABELS[item.key] || 'CHAOSS'}</div>
              <h3>{item.title}</h3>
            </div>
            <div className="chart-meta">最新 {formatNumber(latestValue(item.key), item.unit)}</div>
          </div>
          <ReactECharts
            option={buildLineOption(item.key, seriesMap[item.key] || [], derived[item.key], accent, item.unit)}
            style={{ height: 260 }}
            opts={{ useResizeObserver: false }}
          />
        </div>
      ))}
    </>
  );

  return (
    <div className="trend-shell">
      <div className="trend-hero">
        <div>
          <div className="eyebrow">Trends · CHAOSS</div>
          <h1>趋势监控 & AI 解读</h1>
          <p>按仓库拉通活跃、响应、风险三大趋势，附带可解释指标与行动提示。</p>
        </div>
        <div className="hero-actions">
          {/* 当前仓库 */}
          <div className="current-repo-badge">
            <span className="repo-label">当前仓库:</span>
            <span className="repo-value">{repo || '未选择'}</span>
          </div>
          <div className="pill-group">
            {TIME_PRESETS.map((p) => (
              <button key={p.value} className={`pill ${timeRange === p.value ? 'active' : ''}`} onClick={() => setTimeRange(p.value)}>
                {p.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="trend-tabs">
        {[
          { key: 'overview', label: 'Overview 总览' },
          { key: 'responsiveness', label: 'Responsiveness 响应性' },
          { key: 'activity', label: 'Activity & Growth' },
          { key: 'risk', label: 'Risk & Viability' },
        ].map((tab) => (
          <button key={tab.key} className={`trend-tab ${activeTab === tab.key ? 'active' : ''}`} onClick={() => setActiveTab(tab.key)}>
            {tab.label}
          </button>
        ))}
      </div>

      {error && <div className="error-row">{error}</div>}
      {loading && <div className="loading-text">加载中...</div>}

      {!loading && activeTab === 'overview' && (
        <>
          {/* Composite overview cards */}
          {composite.series && (
            <div className="trend-cards">
              {[{ key: 'vitality', title: '活跃度综合分', accent: '#2563eb', seriesKey: 'vitality_composite' },
                { key: 'responsiveness', title: '响应性综合分', accent: '#f97316', seriesKey: 'responsiveness_composite' },
                { key: 'resilience', title: '稳健度综合分', accent: '#22c55e', seriesKey: 'resilience_composite' }].map((card) => {
                  const s = composite.series[card.seriesKey] || [];
                  const kpi = composite.kpis?.[card.key] || { value: null, delta: null };
                  return (
                    <div key={card.key} className="trend-card">
                      <div className="trend-card-header">
                        <div className="eyebrow">Composite</div>
                        <h3>{card.title}</h3>
                        <p>滚动窗口归一化 + 加权求和（0~100）</p>
                      </div>
                      <div className="trend-card-body">
                        <div className="trend-value">{formatNumber(kpi.value, '')}</div>
                        <div className={`trend-change ${kpi.delta > 0 ? 'trend-up' : kpi.delta < 0 ? 'trend-down' : ''}`}>
                          {kpi.delta === null ? '—' : `${kpi.delta > 0 ? '↑' : kpi.delta < 0 ? '↓' : '→'} ${formatNumber(Math.abs(kpi.delta), '')}`}
                        </div>
                      </div>
                      <ReactECharts
                        option={buildLineOption(card.seriesKey, s, null, card.accent, '')}
                        style={{ height: 180 }}
                        opts={{ useResizeObserver: false }}
                      />
                    </div>
                  );
                })}
            </div>
          )}
          <div className="trend-cards">
            {OVERVIEW_CARDS.map((card, idx) => {
              const val = latestValue(card.key);
              const diff = delta(card.key);
              return (
                <div key={card.key} className="trend-card">
                  <div className="trend-card-header">
                    <div className="eyebrow">{CHAOSS_LABELS[card.key] || 'CHAOSS 指标'}</div>
                    <h3>{card.title}</h3>
                    <p>{card.desc}</p>
                  </div>
                  <div className="trend-card-body">
                    <div className="trend-value">{formatNumber(val)}</div>
                    <div className={`trend-change ${diff > 0 ? 'trend-up' : diff < 0 ? 'trend-down' : ''}`}>
                      {diff === null ? '—' : `${diff > 0 ? '↑' : diff < 0 ? '↓' : '→'} ${formatNumber(Math.abs(diff))}`}
                    </div>
                  </div>
                  <ReactECharts
                    option={buildLineOption(card.key, seriesMap[card.key] || [], derived[card.key], idx === 1 ? '#f97316' : idx === 2 ? '#22c55e' : '#2563eb')}
                    style={{ height: 180 }}
                    opts={{ useResizeObserver: false }}
                  />
                </div>
              );
            })}
          </div>
        </>
      )}

      {!loading && activeTab === 'responsiveness' && (
        <>
          <div className="responsiveness-stats">
            {renderStatsRow(RESPONSIVENESS_METRICS.slice(0, 2))}
            {renderStatsRow(RESPONSIVENESS_METRICS.slice(2))}
          </div>
          <div className="trend-meta-row">
            <div className="stat-chip">48h 内响应占比：{formatNumber(derived?.metric_pr_response_time_h?.response_ratio_48h, '')}</div>
            <div className="stat-chip">Issue 48h 占比：{formatNumber(derived?.metric_issue_response_time_h?.response_ratio_48h, '')}</div>
          </div>
          <div className="responsiveness-charts">
            {renderChartGrid(RESPONSIVENESS_METRICS, '#f97316')}
          </div>
        </>
      )}

      {!loading && activeTab === 'activity' && (
        <>
          <div className="activity-stats">
            {renderStatsRow(ACTIVITY_METRICS.slice(0, 3))}
            {renderStatsRow(ACTIVITY_METRICS.slice(3))}
          </div>
          <div className="activity-charts">
            {renderChartGrid(ACTIVITY_METRICS, '#2563eb')}
          </div>
        </>
      )}

      {!loading && activeTab === 'risk' && (
        <>
          {riskViability.kpis && (
            <div className="trend-stat-row">
              {[
                { key: 'bus_factor', title: 'Bus Factor' },
                { key: 'resilience', title: 'Resilience Index' },
                { key: 'top1_share', title: 'Top1 Share' },
                { key: 'retention_proxy', title: 'Retention Rate (Proxy)' },
                { key: 'scorecard', title: 'Scorecard Score' }
              ].map((item) => {
                const kpi = riskViability.kpis[item.key] || { value: null, delta: null };
                return (
                  <div key={item.key} className="trend-stat-card">
                    <div className="stat-label">{item.title}</div>
                    <div className="stat-value">{formatNumber(kpi.value)}</div>
                    <div className={`stat-delta ${kpi.delta > 0 ? 'up' : kpi.delta < 0 ? 'down' : ''}`}>
                      {kpi.delta === null ? '—' : `${kpi.delta > 0 ? '+' : ''}${formatNumber(kpi.delta)}`}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          {riskViability.series && (
            <div className="trend-chart-grid">
              {[
                { key: 'bus_factor', title: 'Bus Factor' },
                { key: 'resilience', title: 'Resilience Index' },
                { key: 'top1_share', title: 'Top1 Share' },
                { key: 'retention_proxy', title: 'Retention Rate (Proxy)' },
                { key: 'scorecard', title: 'Scorecard Score' }
              ].map((item) => {
                const data = riskViability.series[item.key] || [];
                const latestValue = data.length > 0 ? data[data.length - 1].value : null;
                return (
                  <div key={item.key} className="chart-card">
                    <div className="chart-head">
                      <div>
                        <div className="eyebrow">CHAOSS</div>
                        <h3>{item.title}</h3>
                      </div>
                      <div className="chart-meta">最新 {formatNumber(latestValue)}</div>
                    </div>
                    <ReactECharts
                      option={buildLineOption(item.key, data, null, '#22c55e')}
                      style={{ height: 260 }}
                      opts={{ useResizeObserver: false }}
                    />
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
