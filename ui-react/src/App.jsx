/* eslint-disable no-unused-vars */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { marked } from 'marked';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './App.css';
import TrendMonitor from './pages/TrendMonitor';
import RepositoryGovernanceDashboard from './pages/RepositoryGovernanceDashboard';
import HealthRankingRail from './components/governance/HealthRankingRail';
import {
  refreshMonthlyRepository,
  fetchRepositoryCatalog,
  fetchHealthRanking,
  refreshHealth,
  fetchLatestHealthOverview,
  postNewcomerPlan,
  fetchNewcomerIssues,
  postTaskBundle,
  fetchTrend,
  bootstrapHealth,
  importRepository,
  fetchImportJob,
  fetchHealthReport,
  fetchNewcomerReport,
  fetchTrendReport,
  postAgentRun,
} from './service/api';

const navItems = [
  { key: 'ai', label: 'AI 聊天', note: '主界面' },
  { key: 'health', label: '健康体检', note: '指标与报告' },
  { key: 'benchmark', label: '开源新人', note: '贡献导航' },
  { key: 'trend', label: '趋势监控', note: '趋势解读' },

];

const quickPrompts = [
  '给我最新的健康总分摘要',
  '为什么响应度下降？',
  '帮我写三条治理建议',
  '和 microsoft/vscode 做对标',
  '生成本周行动闭环',
];

const healthSnapshot = {
  score: 82,
  radar: [
    { label: '活跃', value: 78 },
    { label: '响应', value: 64 },
    { label: '韧性', value: 72 },
    { label: '治理', value: 88 },
    { label: '风险', value: 81 },
  ],
  takeaways: [
    '项目保持稳定活跃，OpenRank 持续上升。',
    '响应度略低，建议关注 issue 回复及时性。',
    '治理能力较强，可继续优化风险监测。',
  ],
};

const initialMessages = [
  {
    id: 'm-1',
    role: 'assistant',
    text: `🎉 欢迎使用 OpenSage AI —— 这一刻，数据拥有了预测未来的能力。

我由华东师范大学“爱错”团队研发，是面向开源社区月度数据的治理分析与新人贡献决策助手。

## 🚀 核心优势（为什么选择我？）
- 📐 行业标尺：内置全域项目 P50/P80 水位线，一眼看清项目处于行业头部还是尾部。
- 🔮 趋势预演：独创 时序预测算法，基于历史数据科学推演未来 30 天的走势。
- 🧠 算法评分：不仅仅是列数字，更通过 Readiness Score 等模型量化评估项目对新人的友好度。

## 🌟 您可以这样问我（覆盖四大核心场景）
### 👨‍💻 项目体检 & 预测（维护者）
- "帮我分析 odoo/odoo 的健康状况，预测下个月活跃度是涨是跌？"
- "为什么 Bus Factor 降低了？给我具体的治理建议。"

### 🏢 战略决策 & 对标（OSPO/决策者）
- "帮我评估引入 microsoft/vscode 的 ROI，它的各项指标在行业里算 Top 级吗？"
- "生成一份包含长期趋势分析的深度治理报告。"

### 🧑‍🎓 新手领航 & 评分（开发者）
- "我对 Python 感兴趣，tensorflow 这个项目对新人友好吗？上手难度打几分？"
- "帮我规划一条参与 LangChain 贡献的最佳路径。"

> 注：法律合规咨询功能暂未上线

### ⚖️ 技术选型 & PK（架构师）
- "对比 microsoft/vscode 和 odoo/odoo 的响应速度与社区韧性，谁更适合长期依赖？"

📈 数据不只是数字，更是行动的指南。
请告诉我想分析的仓库名（如 odoo/odoo），我们开始吧 👇`,
  },
];

const actionTasks = [
  { title: '提升响应度：Issue 首响 < 24h', impact: '高影响', effort: '中' },
  { title: '治理欠缺：补充安全扫描 + License 检查', impact: '中影响', effort: '中' },
  { title: '社区活跃：安排每周 triage & 新人引导', impact: '中影响', effort: '低' },
];

const alertList = [
  { title: '响应度连续下降 14 天', level: 'high', time: '2h 前' },
  { title: 'OpenRank 波动 > 15%', level: 'medium', time: '1 天前' },
  { title: 'Top5 贡献占比 82%', level: 'medium', time: '3 天前' },
];

function pickMarkdown(payload) {
  const candidates = [
    payload?.analysis_markdown,
    payload?.report_markdown,
    payload?.analysis_md,
    payload?.analysis,
    payload?.report_text,
    payload?.raw_payloads?.analysis_markdown,
  ];
  return candidates.find((t) => typeof t === 'string' && t.trim()) || '';
}

function extractTop5Share(payload) {
  const candidates = [
    payload?.metric_top5_share,
    payload?.metric_top5_contrib,
    payload?.metric_top5_contribution,
    payload?.top5_share,
    payload?.raw_payloads?.top5_share,
    payload?.raw_payloads?.metrics?.['Top5贡献占比'],
    payload?.raw_payloads?.top_contributors?.top5_share,
  ];

  for (const value of candidates) {
    if (typeof value === 'number' && !Number.isNaN(value)) return value;
    if (typeof value === 'string' && value.trim()) {
      const numeric = parseFloat(value.replace('%', ''));
      if (!Number.isNaN(numeric)) return numeric;
    }
  }
  return null;
}


function App() {
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedRepo, setSelectedRepo] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('repo');
    return requested && /^[^/]+\/[^/]+$/.test(requested) ? requested : 'microsoft/vscode';
  });
  const [domain, setDomain] = useState('frontend');
  const [stack, setStack] = useState('javascript');
  const [timePerWeek, setTimePerWeek] = useState('1-2h');
  const [plan, setPlan] = useState(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState('');
  const [activeTaskTab, setActiveTaskTab] = useState('good_first_issue');
  const [planModalOpen, setPlanModalOpen] = useState(false);
  const [issuesBoard, setIssuesBoard] = useState(null);
  const [issuesLoading, setIssuesLoading] = useState(false);
  const [activeIssuesRepo, setActiveIssuesRepo] = useState(null);
  const [taskBundle, setTaskBundle] = useState(null);
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [taskLoading, setTaskLoading] = useState(false);
  const [taskError, setTaskError] = useState('');
  
  // 添加调试信息，监听selectedRepo变化
  useEffect(() => {
    console.log('selectedRepo变化:', selectedRepo);
  }, [selectedRepo]);

  useEffect(() => {
    if (plan?.recommended_repos?.length) {
      setActiveIssuesRepo(plan.recommended_repos[0].repo_full_name);
      setIssuesBoard(plan.issues_board || null);
    }
  }, [plan]);
  const [activeNav, setActiveNav] = useState(() => {
    const requested = new URLSearchParams(window.location.search).get('view');
    return ['ai', 'health', 'benchmark', 'trend'].includes(requested) ? requested : 'health';
  });
  const [repositoryCatalog, setRepositoryCatalog] = useState([]);
  const [healthRanking, setHealthRanking] = useState(null);
  const [rankingStatus, setRankingStatus] = useState('loading');
  const [rankingError, setRankingError] = useState('');
  const [healthOverview, setHealthOverview] = useState(null);
  const [healthMarkdown, setHealthMarkdown] = useState('');
  const [healthLoading, setHealthLoading] = useState(false);
  const [riskLabel, setRiskLabel] = useState(null);
  const [repoSearch, setRepoSearch] = useState('microsoft/vscode');
  const [repoActionMsg, setRepoActionMsg] = useState('');
  const [repoImportStatus, setRepoImportStatus] = useState(null);
  const [etlLoading, setEtlLoading] = useState(false);
  const [refreshOneLoading, setRefreshOneLoading] = useState(false);
  const [showTrendModal, setShowTrendModal] = useState(false);
  const [activeMetric, setActiveMetric] = useState(null);
  const [trendSeries, setTrendSeries] = useState([]);
  const [trendLoading, setTrendLoading] = useState(false);
  const [trendError, setTrendError] = useState('');
  const [historyRepos, setHistoryRepos] = useState([{ id: 'hist-1', repo: 'microsoft/vscode', tag: '历史' }]);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [healthReport, setHealthReport] = useState(null);
  const [newcomerReport, setNewcomerReport] = useState(null);
  const [trendReport, setTrendReport] = useState(null);
  const listEndRef = useRef(null);
  const trendChartRef = useRef(null);
  const chatContainerRef = useRef(null);


  const filteredRepos = useMemo(() => {
    const term = repoSearch.trim().toLowerCase();
    let allRepos = [...historyRepos];
    if (!term) return allRepos;
    return allRepos.filter((c) => c.repo.toLowerCase().includes(term) || (c.tag || '').toLowerCase().includes(term));
  }, [repoSearch, historyRepos]);
  const normalizedRepoSearch = repoSearch.trim();
  const isRepoInputValid = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(normalizedRepoSearch);
  const matchedCatalogRepo = useMemo(
    () => repositoryCatalog.find((item) => item.repo.toLowerCase() === normalizedRepoSearch.toLowerCase()) || null,
    [normalizedRepoSearch, repositoryCatalog],
  );
  const isImportingRepo = repoImportStatus?.tone === 'loading';
  const isSelectedRepoInput = matchedCatalogRepo?.repo.toLowerCase() === selectedRepo.toLowerCase();
  const repoActionLabel = matchedCatalogRepo ? '切换' : '添加并分析';
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

  const currentScore = useMemo(() => {
    const raw = healthOverview?.score_health ?? healthSnapshot.score;
    if (typeof raw === 'number' && !Number.isNaN(raw)) return Math.round(raw);
    return healthSnapshot.score;
  }, [healthOverview]);

  const themeColor = useMemo(() => {
    if (currentScore < 70) return '#ef4444';
    if (currentScore < 85) return '#f59e0b';
    return '#22c55e';
  }, [currentScore]);

  const healthRadarOption = useMemo(() => {
    const indicator = [
      { name: '活跃度', max: 100 },
      { name: '响应度', max: 100 },
      { name: '抗风险', max: 100 },
      { name: '治理', max: 100 },
      { name: '安全', max: 100 },
    ];

    const values = [
      healthOverview?.score_vitality,
      healthOverview?.score_responsiveness,
      healthOverview?.score_resilience,
      healthOverview?.score_governance,
      healthOverview?.score_security,
    ].map((v, idx) => {
      if (typeof v === 'number' && !Number.isNaN(v)) return Math.round(v);
      return healthSnapshot.radar[idx].value;
    });

    return {
      tooltip: { trigger: 'item' },
      radar: {
        indicator,
        splitNumber: 4,
        radius: '70%',
        axisName: { color: '#0f172a', fontWeight: 600 },
        splitArea: {
          areaStyle: {
            color: ['#f8fafc', '#f1f5f9', '#e2e8f0', '#cbd5e1'],
          },
        },
        splitLine: { lineStyle: { color: '#94a3b8' } },
        axisLine: { lineStyle: { color: '#cbd5e1' } },
      },
      series: [
        {
          type: 'radar',
          data: [
            {
              value: values,
              name: '健康体检',
              areaStyle: { color: `${themeColor}33` },
              lineStyle: { color: themeColor, width: 2 },
              symbol: 'circle',
              symbolSize: 6,
              itemStyle: { color: themeColor, borderColor: '#ffffff', borderWidth: 2 },
            },
          ],
        },
      ],
    };
  }, [healthOverview, themeColor]);

  const coreMetrics = useMemo(
    () => [
      { key: 'openrank', label: 'OpenRank', value: healthOverview?.metric_openrank },
      { key: 'activity', label: 'Activity', value: healthOverview?.metric_activity },
      { key: 'attention', label: 'Attention', value: healthOverview?.metric_attention },
    ].map((m) => ({
      ...m,
      value: typeof m.value === 'number' && !Number.isNaN(m.value) ? Number(m.value.toFixed(2)) : null,
    })),
    [healthOverview],
  );

  const scoreToColor = useCallback((value) => {
    if (value < 70) return '#ef4444';
    if (value < 85) return '#f59e0b';
    return '#16a34a';
  }, []);

  const loadHealthOverview = useCallback(async () => {
    if (!selectedRepo) return;
    setHealthLoading(true);
    setRiskLabel(null);
    try {
      const [overviewRes, reportRes] = await Promise.all([
        fetchLatestHealthOverview(selectedRepo),
        fetchHealthReport(selectedRepo)
      ]);
      
      const payload = overviewRes?.data || overviewRes;
      setHealthOverview(payload);
      setHealthMarkdown(pickMarkdown(payload));
      setHealthReport(reportRes);
      
      const top5 = extractTop5Share(payload);
      if (top5 !== null && top5 > 80) {
        setRiskLabel(`风险预警：Top5 贡献占比 ${top5.toFixed(1)}%`);
      }
    } catch (err) {
      console.error('加载健康数据失败:', err);
      setHealthOverview(null);
      setHealthMarkdown('');
      setHealthReport(null);
    } finally {
      setHealthLoading(false);
    }
  }, [selectedRepo]);


  const dimensionSegments = useMemo(
    () => [
      { name: '活跃度', value: healthOverview?.score_vitality ?? healthSnapshot.radar[0].value, weight: 30 },
      { name: '响应度', value: healthOverview?.score_responsiveness ?? healthSnapshot.radar[1].value, weight: 25 },
      { name: '抗风险', value: healthOverview?.score_resilience ?? healthSnapshot.radar[2].value, weight: 20 },
      { name: '治理', value: healthOverview?.score_governance ?? healthSnapshot.radar[3].value, weight: 15 },
      { name: '安全', value: healthOverview?.score_security ?? healthSnapshot.radar[4].value, weight: 10 },
    ],
    [healthOverview],
  );

  const handleEnterFullscreen = useCallback(() => {
    const dom = trendChartRef.current?.ele || trendChartRef.current?.getEchartsInstance?.()?.getDom?.();
    if (dom?.requestFullscreen) {
      dom.requestFullscreen();
    }
  }, []);

  const healthGaugeOption = useMemo(() => {
    const clamped = Math.min(100, Math.max(0, currentScore));
    return {
      tooltip: {
        trigger: 'item',
        formatter: (params) => {
          const score = params.data?.score ?? '-';
          return `${params.name}<br/>得分：${score} 分<br/>权重：${params.percent}%`;
        },
      },
      series: [
        {
          type: 'pie',
          radius: ['60%', '85%'],
          center: ['50%', '50%'],
          silent: false,
          startAngle: 90,
          label: {
            show: true,
            formatter: (p) => `${p.name}\n${p.data?.score ?? '-'}分 | ${p.percent}%`,
            fontSize: 11,
            color: '#0f172a',
          },
          labelLine: { show: true, length: 8, length2: 6 },
          data: dimensionSegments.map((d) => ({
            name: d.name,
            value: d.weight,
            score: Math.max(0, Math.round(d.value || 0)),
            itemStyle: {
              color: scoreToColor(Math.max(0, Math.round(d.value || 0))),
              borderRadius: 6,
              borderColor: '#fff',
              borderWidth: 2,
            },
          })),
        },
      ],
      graphic: [
        {
          type: 'group',
          left: 'center',
          top: 'center',
          children: [
            {
              type: 'text',
              style: {
                text: `${clamped}`,
                fontSize: 42,
                fontWeight: 800,
                fill: scoreToColor(clamped),
                textAlign: 'center',
              },
              left: 'center',
              top: -10,
            },
            {
              type: 'text',
              style: {
                text: '综合健康度',
                fontSize: 14,
                fill: '#64748b',
                textAlign: 'center',
              },
              left: 'center',
              top: 30,
            },
          ],
        },
      ],
    };
  }, [currentScore, dimensionSegments, scoreToColor]);

  const trendOption = useMemo(() => {
    const dates = trendSeries.map((item) => item.dt);
    const values = trendSeries.map((item) => item.value);

    return {
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 24, top: 32, bottom: 70 },
      toolbox: {
        feature: {
          dataZoom: { yAxisIndex: 'none' },
          restore: {},
          saveAsImage: {},
          myFullscreen: {
            show: true,
            title: '全屏查看',
            icon: 'path://M4 4h8v2H6v6H4V4zm16 0h-8v2h6v6h2V4zm0 16h-8v-2h6v-6h2v8zM4 20h8v-2H6v-6H4v8z',
            onclick: handleEnterFullscreen,
          },
        },
      },
      dataZoom: [
        { type: 'slider', start: 0, end: 100, height: 14, bottom: 24 },
        { type: 'inside' },
      ],
      xAxis: {
        type: 'category',
        boundaryGap: false,
        data: dates,
        axisLabel: { rotate: 0 },
      },
      yAxis: {
        type: 'value',
        axisLabel: { formatter: (v) => v.toFixed ? v.toFixed(1) : v },
        splitLine: { lineStyle: { color: '#e2e8f0' } },
      },
      series: [
        {
          type: 'line',
          data: values,
          smooth: true,
          showSymbol: false,
          lineStyle: { color: '#2563eb', width: 3 },
          areaStyle: { color: 'rgba(37, 99, 235, 0.1)' },
        },
      ],
    };
  }, [trendSeries, handleEnterFullscreen]);

  const renderedMarkdown = useMemo(() => {
    if (!healthMarkdown) return '';
    return marked.parse(healthMarkdown, { breaks: true, gfm: true });
  }, [healthMarkdown]);

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (activeNav === 'health') {
      loadHealthOverview();
    }
  }, [activeNav, loadHealthOverview]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || sending) return;

    // 添加调试信息，确保selectedRepo被正确设置
    console.log('发送消息，当前仓库:', selectedRepo);

    const userMessage = { id: `${Date.now()}-u`, role: 'user', text: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setSending(true);

    try {
      const res = await postAgentRun({
        query: trimmed,
        selected_repo: selectedRepo,
        // 传递完整的历史消息，确保上下文正确
        messages: messages.map(msg => ({
          role: msg.role,
          content: msg.text
        })),
      });

      const reply = 
        res?.report?.text ||
        '已处理，稍后再试试。';

      setMessages((prev) => [...prev, { id: `${Date.now()}-a`, role: 'assistant', text: reply }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: `${Date.now()}-e`, role: 'assistant', text: `调用失败：${err?.message || '请稍后再试'}` },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handlePromptClick = (prompt) => {
    setInput(prompt);
  };

  const addToHistory = (repo) => {
    if (!repo) return;
    setHistoryRepos(prev => {
      // 检查是否已存在，避免重复
      if (prev.some(item => item.repo === repo)) {
        // 如果已存在，移到最前面
        return [{ id: `hist-${Date.now()}`, repo, tag: '历史' }, ...prev.filter(item => item.repo !== repo)];
      }
      // 否则添加到最前面，最多保留10条
      return [{ id: `hist-${Date.now()}`, repo, tag: '历史' }, ...prev.slice(0, 9)];
    });
  };


  const selectGlobalRepo = async (repo) => {
    const next = repo?.trim();
    if (!next || !/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(next)) {
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
      setRepoSearch(known.repo);
      setRepoImportStatus(null);
      addToHistory(known.repo);
      return true;
    }
    setRepoImportStatus({ tone: 'loading', text: '正在验证仓库并创建全量采集任务…' });
    try {
      let job = await importRepository(next);
      for (let attempt = 0; attempt < 120 && ['queued', 'running'].includes(job.status); attempt += 1) {
        setRepoImportStatus({ tone: 'loading', text: `${job.stage || '排队中'} · ${Math.round((job.progress || 0) * 100)}%` });
        await new Promise((resolve) => window.setTimeout(resolve, 1500));
        job = await fetchImportJob(job.job_id);
      }
      if (job.status !== 'succeeded') throw new Error(job.error || '仓库接入失败');
      const response = await fetchRepositoryCatalog();
      setRepositoryCatalog(response?.data || []);
      const canonical = job.result?.repo || job.repo || next;
      setSelectedRepo(canonical);
      setRepoSearch(canonical);
      addToHistory(canonical);
      setRepoImportStatus({ tone: job.stage === 'degraded_ready' ? 'warn' : 'success', text: job.stage === 'degraded_ready' ? '已降级接入：无 OpenDigger 历史' : '全量月度历史已接入' });
      return true;
    } catch (error) {
      setRepoImportStatus({ tone: 'error', text: error?.message || '仓库接入失败' });
      return false;
    }
  };
  const handleNavClick = (key) => {
    setActiveNav(key);
    const url = new URL(window.location.href);
    url.searchParams.set('view', key);
    window.history.replaceState({}, '', url);
  };

  const handleRefreshData = async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      await refreshMonthlyRepository(selectedRepo);
      await loadHealthRanking();
      setMessages((prev) => [
        ...prev,
        { id: `${Date.now()}-sys`, role: 'assistant', text: '已创建月度数据同步任务，可在仓库接入状态中查看进度。' },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: `${Date.now()}-err`, role: 'assistant', text: `更新失败：${err?.message || '请稍后再试'}` },
      ]);
    } finally {
      setRefreshing(false);
    }
  };

  const currentRepoInput = useMemo(() => repoSearch.trim() || selectedRepo, [repoSearch, selectedRepo]);

  const handleEtlRepo = useCallback(async () => {
    const repo = currentRepoInput;
    if (!repo) {
      setRepoActionMsg('请输入或选择仓库');
      return;
    }
    setEtlLoading(true);
    setRepoActionMsg('');
    try {
      const res = await bootstrapHealth(repo);
      setRepoActionMsg(`已创建全量历史任务：${res?.repo || repo}`);
      setSelectedRepo(repo);
    } catch (err) {
      setRepoActionMsg(err?.message || '拉取失败');
    } finally {
      setEtlLoading(false);
    }
  }, [currentRepoInput]);

  const handleRefreshRepo = useCallback(async () => {
    const repo = currentRepoInput;
    if (!repo) {
      setRepoActionMsg('请输入或选择仓库');
      return;
    }
    setRefreshOneLoading(true);
    setRepoActionMsg('');
    try {
      const res = await refreshHealth(repo);
      const dtValue = res?.data?.dt || res?.data?.date || 'today';
      setRepoActionMsg(`已刷新 ${repo} - ${dtValue}`);
      setSelectedRepo(repo);
    } catch (err) {
      setRepoActionMsg(err?.message || '刷新失败');
    } finally {
      setRefreshOneLoading(false);
    }
  }, [currentRepoInput]);

  const loadTrend = useCallback(
    async (metric) => {
      if (!selectedRepo || !metric) return;
      setTrendLoading(true);
      setTrendError('');
      setTrendSeries([]);
      try {
        const res = await fetchTrend(selectedRepo, metric.key);
        const rawList = res?.points || res?.data || res?.items || res || [];
        const list = Array.isArray(rawList) ? rawList : [];

        const normalized = list
          .filter((item) => item && item.dt !== undefined && item.value !== undefined)
          .map((item) => ({
            dt: item.dt,
            value: (() => {
              const raw = typeof item.value === 'number' ? item.value : parseFloat(item.value);
              if (Number.isNaN(raw)) return raw;
              return Number(raw.toFixed(2));
            })(),
          }))
          .filter((item) => !Number.isNaN(item.value));

        const sorted = normalized.sort((a, b) => new Date(a.dt).getTime() - new Date(b.dt).getTime());
        setTrendSeries(sorted);
      } catch (err) {
        setTrendError(err?.message || '趋势数据获取失败');
      } finally {
        setTrendLoading(false);
      }
    },
    [selectedRepo],
  );

  const loadTrendReport = useCallback(async () => {
    if (!selectedRepo) return;
    setTrendLoading(true);
    setTrendError('');
    try {
      const reportRes = await fetchTrendReport(selectedRepo);
      setTrendReport(reportRes);
    } catch (err) {
      setTrendError(err?.message || '趋势报告加载失败');
      setTrendReport(null);
    } finally {
      setTrendLoading(false);
    }
  }, [selectedRepo]);

  useEffect(() => {
    if (activeNav === 'trend') {
      loadTrendReport();
    }
  }, [activeNav, loadTrendReport]);

  const handleGeneratePlan = useCallback(async () => {
    setPlanLoading(true);
    setPlanError('');
    try {
      const [planRes, reportRes] = await Promise.all([
        postNewcomerPlan({
          domain,
          stack,
          time_per_week: timePerWeek,
        }),
        fetchNewcomerReport(domain, stack, timePerWeek)
      ]);
      
      setPlan(planRes);
      setNewcomerReport(reportRes);
      setIssuesBoard(planRes?.issues_board || null);
      const firstRepo = planRes?.recommended_repos?.[0]?.repo_full_name;
      setActiveIssuesRepo(firstRepo || null);
      setActiveTaskTab('good_first_issue');
      setPlanModalOpen(true);
      return planRes;
    } catch (err) {
      setPlan(null);
      setNewcomerReport(null);
      setPlanError(err?.message || '生成失败，请稍后再试');
      return null;
    } finally {
      setPlanLoading(false);
    }
  }, [domain, stack, timePerWeek]);

  const handleSwitchIssuesRepo = useCallback(
    async (repoName, readiness = 60) => {
      if (!repoName) return;
      setIssuesLoading(true);
      setActiveIssuesRepo(repoName);
      try {
        const res = await fetchNewcomerIssues(repoName, readiness);
        setIssuesBoard(res);
      } catch (err) {
        setPlanError(err?.message || '任务看板加载失败');
      } finally {
        setIssuesLoading(false);
      }
    },
    [],
  );

  const handleShowRoute = useCallback(async () => {
    if (!plan) {
      const res = await handleGeneratePlan();
      if (!res) return;
    }
    setPlanModalOpen(true);
  }, [handleGeneratePlan, plan]);

  async function handleClaimTask(task) {
    if (!task) return;
    setTaskLoading(true);
    setTaskError('');
    try {
      const res = await postTaskBundle({
        repo_full_name: task.repo_full_name,
        issue_identifier: task.issue_number || task.url || task.title,
      });
      setTaskBundle(res);
      setTaskModalOpen(true);
    } catch (err) {
      setTaskError(err?.message || '领取失败，请稍后再试');
    } finally {
      setTaskLoading(false);
    }
  }



  const handleCopyTaskBundle = useCallback(async () => {
    if (!taskBundle?.copyable_checklist) return;
    try {
      await navigator.clipboard.writeText(taskBundle.copyable_checklist);
    } catch (err) {
      setTaskError(err?.message || '复制失败');
    }
  }, [taskBundle]);


  const planSummary = useMemo(() => {
    if (!plan?.recommended_repos?.length) return '';
    const top = plan.recommended_repos[0];
    const reasons = top.reasons || [];
    const trend = typeof top.trend_delta === 'number' ? `${top.trend_delta >= 0 ? '+' : ''}${top.trend_delta}%` : '';
    const readiness = top.readiness_score !== undefined ? Math.round(top.readiness_score) : undefined;
    const fit = top.fit_score !== undefined ? Math.round(top.fit_score) : undefined;
    const timeline = plan.timeline || [];

    return [
      '## 推荐仓库',
      `- 仓库：${top.repo_full_name || top.name || ''}`,
      `- 匹配度（Fit）：${fit ?? '--'}% ｜ 新手就绪度：${readiness ?? '--'}%` + (trend ? ` ｜ 近30天趋势：${trend}` : ''),
      top.difficulty ? `- 上手难度：${top.difficulty}` : null,
      '',
      '## 推荐理由',
      ...reasons.slice(0, 5).map((r) => `- ${r}`),
      '',
      '## 贡献路径',
      ...timeline.map((step) => `- ${step.title}: ${(step.commands || []).join(' ｜ ')}`),
      '',
      '## 复制命令',
      plan.copyable_checklist ? plan.copyable_checklist.split('\n').map((l) => l) : [],
    ]
      .flat()
      .filter(Boolean)
      .join('\n');
  }, [plan]);

  const handleMetricClick = (metric) => {
    setActiveMetric(metric);
    setShowTrendModal(true);
    loadTrend(metric);
  };


  const handleCloseTrend = () => {
    setShowTrendModal(false);
    setTrendError('');
  };

  // 全屏切换函数
  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  const renderPageContent = () => {
    if (activeNav === 'ai') return null;

    if (activeNav === 'health') {
      return (
        <RepositoryGovernanceDashboard
          initialRepo={selectedRepo}
          repositories={repositoryCatalog}
          onSelectRepo={selectGlobalRepo}
          onOpenAI={() => handleNavClick('ai')}
          repositoryActionStatus={repoImportStatus}
        />
      );
    }

    if (activeNav === 'benchmark') {
      const interestAreas = [
        { label: 'Web前端', value: 'frontend' },
        { label: '后端/企业应用', value: 'backend_enterprise' },
        { label: '移动开发', value: 'mobile' },
        { label: '云原生/基础设施', value: 'cloud_infra' },
        { label: 'AI/深度学习', value: 'ai_ml' },
        { label: '安全/合规', value: 'security' },
        { label: '开源生态分析', value: 'oss_analytics' },
        { label: '文档', value: 'docs' },
        { label: '翻译', value: 'i18n' },
      ];
      const skillStacks = [
        { label: 'JavaScript/TypeScript', value: 'javascript' },
        { label: 'Python', value: 'python' },
        { label: 'Go', value: 'go' },
        { label: 'Java', value: 'java' },
        { label: 'Rust', value: 'rust' },
        { label: 'TypeScript (TS)', value: 'typescript' },
        { label: 'Node.js / Express', value: 'nodejs' },
        { label: 'React', value: 'react' },
        { label: 'Vue', value: 'vue' },
        { label: 'Angular', value: 'angular' },
        { label: 'PHP / Laravel', value: 'php' },
        { label: 'C# / .NET', value: 'csharp' },
        { label: 'C/C++', value: 'cpp' },
        { label: 'Kotlin', value: 'kotlin' },
        { label: 'Swift', value: 'swift' },
        { label: 'Dart / Flutter', value: 'flutter' },
        { label: 'SQL / 数据库', value: 'sql' },
      ];
      const timeCommits = [
        { label: '1-2h/周', value: '1-2h' },
        { label: '3-5h/周', value: '3-5h' },
        { label: '6-10h/周', value: '6-10h' },
        { label: '10h+/周', value: '10+h' },
      ];

      const fallbackProjects = [
        { repo_full_name: 'microsoft/vscode', fit_score: 92, readiness_score: 88, difficulty: 'Easy', responsiveness: 12, activity: 98, trend_delta: 12, reasons: ['领域匹配：Web前端', '首响较快：12h'] },
        { repo_full_name: 'facebook/react', fit_score: 90, readiness_score: 80, difficulty: 'Medium', responsiveness: 18, activity: 96, trend_delta: 8, reasons: ['生态活跃', '新手任务充足'] },
        { repo_full_name: 'vuejs/core', fit_score: 88, readiness_score: 82, difficulty: 'Easy', responsiveness: 16, activity: 94, trend_delta: 15, reasons: ['响应积极', '健康度稳定'] },
        { repo_full_name: 'python/cpython', fit_score: 85, readiness_score: 76, difficulty: 'Medium', responsiveness: 20, activity: 90, trend_delta: 5, reasons: ['社区成熟', '任务丰富'] },
      ];

      const rawCards = plan?.recommended_repos?.length ? plan.recommended_repos : fallbackProjects;
      const cards = rawCards.map((item, idx) => ({
        id: idx,
        name: item.repo_full_name,
        url: item.url || `https://github.com/${item.repo_full_name}`,
        fit: Math.round(item.fit_score ?? item.match_score ?? 0),
        readiness: Math.round(item.readiness_score ?? 0),
        difficulty: item.difficulty || 'Medium',
        responsiveness: item.responsiveness !== undefined && item.responsiveness !== null ? `${Math.round(item.responsiveness)}h` : '--',
        activity: item.activity !== undefined && item.activity !== null ? Math.round(item.activity) : '--',
        trend: typeof item.trend_delta === 'number' ? `${item.trend_delta >= 0 ? '+' : ''}${Math.round(item.trend_delta)}%` : '--',
        description: item.description || '点击查看仓库详情',
        reasons: item.reasons || [],
      }));

      const fallbackTasks = {
        good_first_issue: [
          { title: '修复文档中的拼写错误', repo_full_name: 'microsoft/vscode', difficulty: 'Easy', url: '#' },
        ],
        help_wanted: [
          { title: '添加新的测试用例', repo_full_name: 'facebook/react', difficulty: 'Medium', url: '#' },
        ],
        docs: [
          { title: '更新中文文档', repo_full_name: 'vuejs/core', difficulty: 'Easy', url: '#' },
        ],
        i18n: [
          { title: '翻译 README 到日语', repo_full_name: 'python/cpython', difficulty: 'Easy', url: '#' },
        ],
      };

      const tasksSource = issuesBoard || plan?.issues_board || fallbackTasks;
      const taskTabs = [
        { key: 'good_first_issue', label: 'Good First Issue' },
        { key: 'help_wanted', label: 'Help Wanted' },
        { key: 'docs', label: '文档类任务' },
        { key: 'i18n', label: '翻译类任务' },
      ];
    

      return (
        <div className="newcomer-wrapper">
          {/* 入门向导 Hero */}
          <section className="newcomer-hero">
            <div className="newcomer-hero-content">
              <h1>启航入门 · 贡献导航</h1>
              <p>从“我是谁/我会什么/我想参与什么”出发，给新人一条可执行的贡献路径。</p>
            </div>
            
            {/* 三步入门向导 */}
            <div className="onboarding-steps">
              <div className="step-card">
                <div className="step-number">1</div>
                <div className="step-title">选择兴趣领域</div>
                <select
                  className="step-select"
                  value={domain}
                  onChange={(e) => {
                    setDomain(e.target.value);
                    setPlan(null);
                    setPlanModalOpen(false);
                  }}
                >
                  {interestAreas.map((area) => (
                    <option key={area.value} value={area.value}>{area.label}</option>
                  ))}
                </select>
              </div>
              
              <div className="step-card">
                <div className="step-number">2</div>
                <div className="step-title">选择技能栈</div>
                <select
                  className="step-select"
                  value={stack}
                  onChange={(e) => {
                    setStack(e.target.value);
                    setPlan(null);
                    setPlanModalOpen(false);
                  }}
                >
                  {skillStacks.map((skill) => (
                    <option key={skill.value} value={skill.value}>{skill.label}</option>
                  ))}
                </select>
              </div>
              
              <div className="step-card">
                <div className="step-number">3</div>
                <div className="step-title">每周可投入时间</div>
                <select
                  className="step-select"
                  value={timePerWeek}
                  onChange={(e) => {
                    setTimePerWeek(e.target.value);
                    setPlan(null);
                    setPlanModalOpen(false);
                  }}
                >
                  {timeCommits.map((time) => (
                    <option key={time.value} value={time.value}>{time.label}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* 关键 CTA */}
            <div className="hero-cta-group">
              <button className="primary-btn large" onClick={handleShowRoute} disabled={planLoading}>
                {planLoading ? '生成中...' : plan ? '查看项目路线' : '生成项目路线'}
              </button>
            </div>
            {planError && <div className="error-row compact">{planError}</div>}
          </section>
          
          {/* 项目推荐卡片区 */}
          <section className="newcomer-section">
            <div className="section-head">
              <h2>项目推荐</h2>
              <p>根据你的选择，为你推荐匹配度最高的开源项目</p>
            </div>
            
            <div className="project-cards">
              {cards.map((project) => (
                <div key={project.id} className="project-card">
                  <div className="project-header">
                    <div className="project-title">{project.name}</div>
                    <div className="match-badge">匹配度 {project.fit}%</div>
                  </div>
                  <div className="project-description">{project.description}</div>
                  <div className="project-metrics">
                    <div className="metric-item">
                      <span className="metric-label">新手就绪度</span>
                      <span className="metric-value">{project.readiness}%</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">上手难度</span>
                      <span className={`metric-value ${project.difficulty.toLowerCase()}`}>{project.difficulty}</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">维护者响应</span>
                      <span className="metric-value">{project.responsiveness}</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">活跃度</span>
                      <span className="metric-value">{project.activity}%</span>
                    </div>
                    <div className="metric-item">
                      <span className="metric-label">近30天趋势</span>
                      <span className="metric-value positive">{project.trend}</span>
                    </div>
                  </div>
                  {project.reasons?.length ? (
                    <details className="why-block">
                      <summary>为什么推荐</summary>
                      <ul>
                        {project.reasons.slice(0, 5).map((r, idx) => (
                          <li key={`${project.id}-reason-${idx}`}>{r}</li>
                        ))}
                      </ul>
                    </details>
                  ) : null}
                  <div className="project-cta">
                    <button className="project-btn" onClick={() => handleSwitchIssuesRepo(project.name, project.readiness)}>
                      加载任务
                    </button>
                    <button className="project-btn" onClick={() => project.url && window.open(project.url, '_blank', 'noopener')}>
                      查看项目
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* 新手任务看板 */}
          <section className="newcomer-section">
            <div className="section-head">
              <h2>新手任务看板</h2>
              <p>从简单任务开始，迈出你的开源贡献第一步 {activeIssuesRepo ? `（当前：${activeIssuesRepo}）` : ''}</p>
            </div>
            
            <div className="task-board">
              <div className="task-tabs">
                {taskTabs.map((tab) => (
                  <button
                    key={tab.key}
                    className={`task-tab ${activeTaskTab === tab.key ? 'active' : ''}`}
                    onClick={() => setActiveTaskTab(tab.key)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
              <div className="task-list">
                {issuesLoading && <div className="loading-text">任务加载中...</div>}
                {(tasksSource[activeTaskTab] || []).map((task, idx) => (
                  <div key={`${task.title}-${idx}`} className="task-item">
                    <div className="task-type-badge">{task.repo_full_name}</div>
                    <div className="task-content">
                      <div className="task-title">{task.title}</div>
                      <div className="task-repo">{(task.labels || []).slice(0, 3).join(' / ')}</div>
                      <div className="task-meta">
                        <span className={`difficulty ${(task.difficulty || 'Medium').toLowerCase()}`}>{task.difficulty || 'Medium'}</span>
                        {task.updated_from_now ? <span className="task-updated">{task.updated_from_now}</span> : null}
                      </div>
                    </div>
                    <div className="task-actions">
                      <button className="task-btn" onClick={() => handleClaimTask(task)} disabled={taskLoading}>
                        领取任务
                      </button>
                    </div>
                  </div>
                ))}
                {!planLoading && !issuesLoading && !(tasksSource[activeTaskTab] || []).length && (
                  <div className="loading-text">暂无任务</div>
                )}
              </div>
            </div>
          </section>
          
          {planModalOpen && (
                  <div className="trend-modal-overlay" onClick={() => setPlanModalOpen(false)}>
                    <div className="trend-modal" onClick={(e) => e.stopPropagation()}>
                      <div className="trend-modal-head">
                        <div>
                          <div className="eyebrow">AI 项目路线</div>
                          <h3>推荐原因 & 行动步骤</h3>
                        </div>
                        <button className="ghost-btn" onClick={() => setPlanModalOpen(false)}>关闭</button>
                      </div>
                      {newcomerReport?.report_json ? (
                        <div className="plan-modal-body">
                          <div className="multi-module-report">
                            {/* 摘要卡片 */}
                            <div className="report-summary-card">
                              <h3>摘要</h3>
                              <ul className="summary-bullets">
                                {newcomerReport.report_json.summary_bullets.map((bullet, idx) => (
                                  <li key={idx}>{bullet}</li>
                                ))}
                              </ul>
                            </div>
                            
                            {/* 详细部分 */}
                            <div className="report-sections">
                              {newcomerReport.report_json.sections.map((section, idx) => (
                                <div key={idx} className="report-section-card">
                                  <h3>{section.title}</h3>
                                  <div className="section-content">
                                    {section.content_md}
                                  </div>
                                  {section.evidence && section.evidence.length > 0 && (
                                    <div className="section-evidence">
                                      <h4>证据</h4>
                                      <ul>
                                        {section.evidence.map((evidence, eIdx) => (
                                          <li key={eIdx}>
                                            {evidence.key}: {evidence.value} {evidence.dt && `(截至 ${evidence.dt})`}
                                          </li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                            
                            {/* 行动建议 */}
                            {newcomerReport.report_json.actions && newcomerReport.report_json.actions.length > 0 && (
                              <div className="report-actions-card">
                                <h3>行动建议</h3>
                                {newcomerReport.report_json.actions.map((action, idx) => (
                                  <div key={idx} className="action-item">
                                    <div className="action-header">
                                      <span className={`priority-badge ${action.priority.toLowerCase()}`}>{action.priority}</span>
                                      <h4>{action.title}</h4>
                                    </div>
                                    <ul className="action-steps">
                                      {action.steps.map((step, sIdx) => (
                                        <li key={sIdx}>{step}</li>
                                      ))}
                                    </ul>
                                    {action.metrics_to_watch && action.metrics_to_watch.length > 0 && (
                                      <div className="metrics-to-watch">
                                        <span>监控指标：</span>
                                        {action.metrics_to_watch.join(', ')}
                                      </div>
                                    )}
                                  </div>
                                ))}
                              </div>
                            )}
                            
                            {/* 监控指标 */}
                            {newcomerReport.report_json.monitor && newcomerReport.report_json.monitor.length > 0 && (
                              <div className="report-monitor-card">
                                <h3>监控指标</h3>
                                <ul className="monitor-list">
                                  {newcomerReport.report_json.monitor.map((metric, idx) => (
                                    <li key={idx}>{metric}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            
                            {/* 警告和数据缺口 */}
                            {(newcomerReport.report_json.warnings && newcomerReport.report_json.warnings.length > 0) || 
                             (newcomerReport.report_json.data_gaps && newcomerReport.report_json.data_gaps.length > 0) && (
                              <div className="report-warnings-card">
                                {newcomerReport.report_json.warnings && newcomerReport.report_json.warnings.length > 0 && (
                                  <>
                                    <h3>警告</h3>
                                    <ul className="warnings-list">
                                      {newcomerReport.report_json.warnings.map((warning, idx) => (
                                        <li key={idx}>{warning}</li>
                                      ))}
                                    </ul>
                                  </>
                                )}
                                {newcomerReport.report_json.data_gaps && newcomerReport.report_json.data_gaps.length > 0 && (
                                  <>
                                    <h3>数据缺口</h3>
                                    <ul className="gaps-list">
                                      {newcomerReport.report_json.data_gaps.map((gap, idx) => (
                                        <li key={idx}>{gap}</li>
                                      ))}
                                    </ul>
                                  </>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      ) : newcomerReport?.report_markdown ? (
                        <div className="plan-modal-body markdown-body">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {newcomerReport.report_markdown}
                          </ReactMarkdown>
                        </div>
                      ) : planSummary ? (
                        <div className="plan-modal-body markdown-body">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {planSummary}
                          </ReactMarkdown>
                        </div>
                      ) : (
                        <div className="loading-text">暂无路线，请先生成。</div>
                      )}
                    </div>
                  </div>
                )}

          {taskModalOpen && (
            <div className="trend-modal-overlay" onClick={() => setTaskModalOpen(false)}>
              <div className="trend-modal" onClick={(e) => e.stopPropagation()}>
                <div className="trend-modal-head">
                  <div>
                    <div className="eyebrow">任务领取</div>
                    <h3>{taskBundle?.issue?.title || '任务步骤'}</h3>
                  </div>
                  <button className="ghost-btn" onClick={() => setTaskModalOpen(false)}>关闭</button>
                </div>
                {taskError && <div className="error-row">{taskError}</div>}
                <div className="plan-modal-body">
                  {(taskBundle?.steps || []).map((step, idx) => (
                    <div key={`bundle-${idx}`} className="timeline-row">
                      <div className="timeline-title">{step.title}</div>
                      <div className="timeline-list">
                        {(step.commands || []).map((cmd, cIdx) => (
                          <div key={`bundle-cmd-${idx}-${cIdx}`} className="timeline-row">{cmd}</div>
                        ))}
                        {step.note ? <div className="timeline-note">{step.note}</div> : null}
                      </div>
                    </div>
                  ))}
                  {!taskBundle?.steps?.length && <div className="loading-text">暂无步骤</div>}
                </div>
                <div className="modal-footnote">
                  <button className="primary-btn" onClick={handleCopyTaskBundle} disabled={!taskBundle?.copyable_checklist}>
                    复制命令清单
                  </button>
                  {taskBundle?.issue?.url ? (
                    <a className="project-btn" href={taskBundle.issue.url} target="_blank" rel="noreferrer">查看 Issue</a>
                  ) : null}
                </div>
              </div>
            </div>
          )}
        </div>
      );
    }

    if (activeNav === 'trend') {
      return (
        <div className="analysis-wrapper">
          {/* 使用专门的 TrendMonitor 组件显示图表数据 */}
          <TrendMonitor repo={selectedRepo} />
          
          {/* 显示 AI 分析报告 */}
          <section className="analysis-card markdown-card">
            <div className="analysis-head">
              <div>
                <div className="eyebrow">AI 分析报告</div>
                <h2>趋势监控洞察</h2>
              </div>
            </div>
            {trendLoading ? (
              <div className="loading-text">报告加载中...</div>
            ) : trendReport?.report_json ? (
              <div className="multi-module-report">
                {/* 摘要卡片 */}
                <div className="report-summary-card">
                  <h3>摘要</h3>
                  <ul className="summary-bullets">
                    {trendReport.report_json.summary_bullets.map((bullet, idx) => (
                      <li key={idx}>{bullet}</li>
                    ))}
                  </ul>
                </div>
                
                {/* 详细部分 */}
                <div className="report-sections">
                  {trendReport.report_json.sections.map((section, idx) => (
                    <div key={idx} className="report-section-card">
                      <h3>{section.title}</h3>
                      <div className="section-content">
                        {section.content_md}
                      </div>
                      {section.evidence && section.evidence.length > 0 && (
                        <div className="section-evidence">
                          <h4>证据</h4>
                          <ul>
                            {section.evidence.map((evidence, eIdx) => (
                              <li key={eIdx}>
                                {evidence.key}: {evidence.value} {evidence.dt && `(截至 ${evidence.dt})`}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                
                {/* 行动建议 */}
                {trendReport.report_json.actions && trendReport.report_json.actions.length > 0 && (
                  <div className="report-actions-card">
                    <h3>行动建议</h3>
                    {trendReport.report_json.actions.map((action, idx) => (
                      <div key={idx} className="action-item">
                        <div className="action-header">
                          <span className={`priority-badge ${action.priority.toLowerCase()}`}>{action.priority}</span>
                          <h4>{action.title}</h4>
                        </div>
                        <ul className="action-steps">
                          {action.steps.map((step, sIdx) => (
                            <li key={sIdx}>{step}</li>
                          ))}
                        </ul>
                        {action.metrics_to_watch && action.metrics_to_watch.length > 0 && (
                          <div className="metrics-to-watch">
                            <span>监控指标：</span>
                            {action.metrics_to_watch.join(', ')}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
                
                {/* 监控指标 */}
                {trendReport.report_json.monitor && trendReport.report_json.monitor.length > 0 && (
                  <div className="report-monitor-card">
                    <h3>监控指标</h3>
                    <ul className="monitor-list">
                      {trendReport.report_json.monitor.map((metric, idx) => (
                        <li key={idx}>{metric}</li>
                      ))}
                    </ul>
                  </div>
                )}
                
                {/* 警告和数据缺口 */}
                {(trendReport.report_json.warnings && trendReport.report_json.warnings.length > 0) || 
                 (trendReport.report_json.data_gaps && trendReport.report_json.data_gaps.length > 0) && (
                  <div className="report-warnings-card">
                    {trendReport.report_json.warnings && trendReport.report_json.warnings.length > 0 && (
                      <>
                        <h3>警告</h3>
                        <ul className="warnings-list">
                          {trendReport.report_json.warnings.map((warning, idx) => (
                            <li key={idx}>{warning}</li>
                          ))}
                        </ul>
                      </>
                    )}
                    {trendReport.report_json.data_gaps && trendReport.report_json.data_gaps.length > 0 && (
                      <>
                        <h3>数据缺口</h3>
                        <ul className="gaps-list">
                          {trendReport.report_json.data_gaps.map((gap, idx) => (
                            <li key={idx}>{gap}</li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="mini-list">
                {alertList.map((text, idx) => (
                  <div key={idx} className="list-row">• {text.title}</div>
                ))}
              </div>
            )}
          </section>
        </div>
      );
    }

    if (activeNav === 'actions') {
      return (
        <div className="analysis-wrapper">
          <section className="analysis-card">
            <div className="analysis-head">
              <div>
                <div className="eyebrow">行动中心</div>
                <h2>治理清单</h2>
              </div>
            </div>
            <div className="mini-list">
              {actionTasks.map((a) => (
                <div key={a.title} className="list-row">
                  <div className="list-row-title">{a.title}</div>
                  <div className="list-row-meta">{a.impact} · 难度 {a.effort}</div>
                </div>
              ))}
            </div>
          </section>
        </div>
      );
    }

    if (activeNav === 'alerts') {
      return (
        <div className="analysis-wrapper">
          <section className="analysis-card">
            <div className="analysis-head">
              <div>
                <div className="eyebrow">风险预警</div>
                <h2>近期预警</h2>
              </div>
            </div>
            <div className="mini-list">
              {alertList.map((a) => (
                <div key={a.title} className={`alert-item ${a.level}`}>
                  <div>{a.title}</div>
                  <div className="alert-time">{a.time}</div>
                </div>
              ))}
            </div>
          </section>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="app-shell">

      <div className={`content-grid ${activeNav === 'health' ? 'health-workspace' : ''}`}>
        {activeNav === 'health' && <HealthRankingRail
          payload={healthRanking}
          status={rankingStatus}
          error={rankingError}
          selectedRepo={selectedRepo}
          onSelect={selectGlobalRepo}
          onRetry={loadHealthRanking}
        />}

        <main className={`chat-column ${activeNav === 'health' ? 'health-column health-workspace-main' : ''}`}>
          {activeNav === 'ai' ? (
            <>
              {/* 聊天主区域 - 限制宽度 + 居中 */}
              <div ref={chatContainerRef} className={`chat-container ${isFullscreen ? 'fullscreen' : ''}`}>
                {/* 顶部标题栏 - 始终显示 */}
                <div className="chat-hero-modern">
                  <div className="chat-hero-header">
                    <div className="chat-hero-content">
                      <div className="eyebrow">AI Chat · 主工作区</div>
                      <h1>用对话完成体检、对标、治理和预警</h1>
                      <p>输入问题或选择提示，Agent 会调用后端 /agent/run 读取真实数据再生成报告。</p>
                    </div>
                    {/* 右上角当前仓库和全屏按钮 */}
                    <div className="hero-actions">
                      {/* 当前仓库 */}
                      <div className="current-repo-badge">
                        <span className="repo-label">当前仓库:</span>
                        <span className="repo-value">{selectedRepo}</span>
                      </div>
                      {/* 全屏切换按钮 */}
                      <button 
                        className="fullscreen-toggle-btn"
                        onClick={toggleFullscreen}
                        title={isFullscreen ? '退出全屏' : '全屏'}
                      >
                        {isFullscreen ? '⬜' : '⛶'}
                      </button>
                    </div>
                  </div>
                  {/* 快捷提示词 */}
                  <div className="quick-prompts-inline">
                    {quickPrompts.map((p) => (
                      <button key={p} className="prompt-chip-modern" onClick={() => handlePromptClick(p)}>
                        {p}
                      </button>
                    ))}
                  </div>
                </div>

                {/* 消息列表 */}
                <div className="chat-window-modern">
                  {messages.map((msg) => (
                    <div key={msg.id} className={`message-bubble ${msg.role === 'user' ? 'message-user' : 'message-assistant'}`}>
                      {/* 头像 */}
                      <div className={`message-avatar ${msg.role === 'user' ? 'avatar-user' : 'avatar-assistant'}`}>
                        {msg.role === 'assistant' ? '🤖' : '👤'}
                      </div>
                      
                      {/* 消息内容 */}
                      <div className="message-content-wrapper">
                        <div className="message-role-label">{msg.role === 'assistant' ? 'OpenSage' : '你'}</div>
                        <div className={`message-content ${msg.role === 'assistant' ? 'content-assistant' : 'content-user'}`}>
                          {msg.role === 'assistant' ? (
                            <div className="markdown-content">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {msg.text}
                              </ReactMarkdown>
                            </div>
                          ) : (
                            <div className="text-content">{msg.text}</div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                  {sending && (
                    <div className="message-bubble message-assistant">
                      <div className="message-avatar avatar-assistant">🤖</div>
                      <div className="message-content-wrapper">
                        <div className="message-role-label">opensage</div>
                        <div className="message-content content-assistant">
                          <div className="typing-indicator">
                            <span></span>
                            <span></span>
                            <span></span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                  <div ref={listEndRef} />
                </div>

                {/* 底部输入区 - 自适应高度 */}
                <div className="composer-modern">
                  <div className="composer-wrapper">
                    <textarea
                      value={input}
                      onChange={(e) => {
                        setInput(e.target.value);
                        // 自动调整高度，限制最大高度
                        e.target.style.height = 'auto';
                        e.target.style.height = `${Math.min(e.target.scrollHeight, 120)}px`;
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && !e.shiftKey) {
                          e.preventDefault();
                          handleSend();
                        }
                      }}
                      placeholder="问我：体检一下仓库、给出治理建议或生成风险预警..."
                      className="composer-input"
                      rows={1}
                    />
                    <button 
                      className="composer-send-btn" 
                      onClick={handleSend} 
                      disabled={sending || !input.trim()}
                      title="发送 (Enter)"
                    >
                      {sending ? (
                        <span className="sending-spinner">⏳</span>
                      ) : (
                        <span>➤</span>
                      )}
                    </button>
                  </div>
                  <div className="composer-footer">
                    <span className="composer-hint">支持 Markdown 输入 · 按 Enter 发送，Shift+Enter 换行</span>
                  </div>
                </div>
              </div>
            </>
          ) : (
            renderPageContent()
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
