import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { fetchNewcomerIssues, postNewcomerPlan } from '../../service/api';
import {
  DIFFICULTY_COLORS,
  DIFFICULTY_LABELS,
  OPPORTUNITY_THRESHOLDS,
  TREND_META,
  adaptNewcomerProjects,
  escapeHtml,
  filterNewcomerProjects,
  formatTrend,
  getBubbleRadius,
  layoutOpportunityNodes,
  resolveCustomDataItem,
  selectDefaultProject,
} from './newcomerOpportunityAdapters';
import './newcomerOpportunityMap.css';

const DOMAIN_OPTIONS = [
  { value: 'ai_ml', label: 'AI应用' },
  { value: 'deep_learning', label: '深度学习' },
  { value: 'time_series', label: '时序分析' },
  { value: 'databases', label: '数据库' },
  { value: 'visualization', label: '前端可视化' },
  { value: 'data_engineering', label: '数据工程' },
  { value: 'mlops', label: 'MLOps' },
  { value: 'developer_tools', label: '开发者工具' },
  { value: 'frontend', label: '前端工程' },
  { value: 'oss_analytics', label: '数据可视化' },
  { value: 'cloud_infra', label: '云原生' },
  { value: 'backend_enterprise', label: '后端开发' },
  { value: 'security', label: '安全/合规' },
  { value: 'docs', label: '文档' },
  { value: 'i18n', label: '国际化' },
];

const SKILL_OPTIONS = [
  { value: 'python', label: 'Python' },
  { value: 'typescript', label: 'TypeScript' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'rust', label: 'Rust' },
  { value: 'go', label: 'Go' },
  { value: 'java', label: 'Java' },
  { value: 'cpp', label: 'C++' },
  { value: 'vue', label: 'Vue' },
  { value: 'react', label: 'React' },
  { value: 'nodejs', label: 'Node.js' },
];

const DIFFICULTY_OPTIONS = [
  { value: 'all', label: '全部' },
  { value: 'easy', label: '容易' },
  { value: 'medium', label: '适中' },
  { value: 'hard', label: '挑战' },
];

const TASK_OPTIONS = [
  { value: 0, label: '全部' },
  { value: 1, label: '≥1' },
  { value: 5, label: '≥5' },
  { value: 10, label: '≥10' },
  { value: 20, label: '≥20' },
];

const TASK_CATEGORY_META = [
  { key: 'good_first_issue', label: 'Good first issue' },
  { key: 'help_wanted', label: 'Help wanted' },
  { key: 'docs', label: '文档任务' },
  { key: 'i18n', label: '国际化任务' },
];

// 用户可在完整评分域内调整可见范围，初始值保持横轴 30–100、纵轴 50–100。
const AXIS_MIN = 0;
const AXIS_MAX = 100;
const AXIS_STEP = 10;
const AXIS_MIN_GAP = 10;
const DEFAULT_X_RANGE = Object.freeze([30, 100]);
const DEFAULT_Y_RANGE = Object.freeze([50, 100]);

function safeChartPixel(chart, coordinate, value) {
  try {
    const point = chart?.convertToPixel(coordinate, value);
    return Array.isArray(point) && point.length >= 2 && point.every((item) => Number.isFinite(item)) ? point : null;
  } catch {
    return null;
  }
}
function MultiSelectFilter({ label, options, values, onChange }) {
  const selectedLabels = options.filter((option) => values.includes(option.value)).map((option) => option.label);
  const toggle = (value) => {
    onChange(values.includes(value) ? values.filter((item) => item !== value) : [...values, value]);
  };
  return (
    <div className="newcomer-filter-field newcomer-filter-multi-field">
      <span className="newcomer-filter-label">{label}</span>
      <details className="newcomer-filter-multi">
        <summary>{selectedLabels.length ? selectedLabels.join('、') : '全部'}</summary>
        <div className="newcomer-filter-menu">
          <label className="newcomer-filter-all">
            <input type="checkbox" checked={!values.length} onChange={() => onChange([])} />
            <span>全部</span>
          </label>
          {options.map((option) => (
            <label key={option.value}>
              <input type="checkbox" checked={values.includes(option.value)} onChange={() => toggle(option.value)} />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      </details>
    </div>
  );
}

function AxisRangeFilter({ label, value, onChange }) {
  const [lower, upper] = value;
  const updateLower = (event) => {
    const next = Math.min(Number(event.target.value), upper - AXIS_MIN_GAP);
    onChange([next, upper]);
  };
  const updateUpper = (event) => {
    const next = Math.max(Number(event.target.value), lower + AXIS_MIN_GAP);
    onChange([lower, next]);
  };
  return (
    <div className="newcomer-axis-range">
      <div className="newcomer-axis-range-head">
        <span>{label}</span>
        <output>{lower}–{upper}</output>
      </div>
      <div
        className="newcomer-axis-range-track"
        style={{ '--range-start': `${lower}%`, '--range-end': `${upper}%` }}
      >
        <input
          aria-label={`${label}最小值`}
          type="range"
          min={AXIS_MIN}
          max={AXIS_MAX - AXIS_MIN_GAP}
          step={AXIS_STEP}
          value={lower}
          onChange={updateLower}
        />
        <input
          aria-label={`${label}最大值`}
          type="range"
          min={AXIS_MIN + AXIS_MIN_GAP}
          max={AXIS_MAX}
          step={AXIS_STEP}
          value={upper}
          onChange={updateUpper}
        />
      </div>
    </div>
  );
}

function buildOpportunityAreas(xRange, yRange) {
  const [xMin, xMax] = xRange;
  const [yMin, yMax] = yRange;
  const areas = [
    ['潜力项目', xMin, Math.max(yMin, 70), Math.min(xMax, 60), yMax, 'rgba(214,154,50,.07)'],
    ['优先参与', Math.max(xMin, 60), Math.max(yMin, 70), xMax, yMax, 'rgba(47,147,133,.08)'],
    ['暂不推荐', xMin, yMin, Math.min(xMax, 60), Math.min(yMax, 70), 'rgba(184,73,53,.045)'],
    ['容易上手', Math.max(xMin, 60), yMin, xMax, Math.min(yMax, 70), 'rgba(214,154,50,.045)'],
  ];
  return areas
    .filter(([, x0, y0, x1, y1]) => x0 < x1 && y0 < y1)
    .map(([name, x0, y0, x1, y1, color]) => ([
      { name, xAxis: x0, yAxis: y0, itemStyle: { color } },
      { xAxis: x1, yAxis: y1 },
    ]));
}

function formatNumber(value, suffix = '') {
  return value == null || !Number.isFinite(Number(value)) ? '暂无数据' : `${Math.round(Number(value))}${suffix}`;
}

function projectStatus(project) {
  if (!project) return '等待选择项目';
  if (project.readiness >= OPPORTUNITY_THRESHOLDS.readiness && project.match >= OPPORTUNITY_THRESHOLDS.match) return '优先参与区';
  if (project.match >= OPPORTUNITY_THRESHOLDS.match) return '潜力项目区';
  if (project.readiness >= OPPORTUNITY_THRESHOLDS.readiness) return '容易上手区';
  return '暂不推荐区';
}

function projectStatusTag(project) {
  if (!project) return '';
  const trend = project.trendDirection === 'up' ? '趋势上升' : project.trendDirection === 'down' ? '趋势回落' : '趋势稳定';
  if (project.readiness >= 60 && project.match >= 70) return `优先参与 · ${trend}`;
  if (project.match >= 70) return '潜力项目 · 就绪待改善';
  if (project.readiness >= 60) return '容易上手 · 匹配一般';
  return '暂不推荐';
}

function projectTooltip(project) {
  const taskCount = project.taskCount == null ? '任务数据不足' : `${project.taskCount} 个`;
  const health = project.healthScore == null ? '积累中' : `${Math.round(project.healthScore)} / 100`;
  return [
    `<strong>${escapeHtml(project.repository)}</strong>`,
    `用户匹配度：${formatNumber(project.match, '%')}`,
    `新手就绪度：${formatNumber(project.readiness, '%')}`,
    `新人任务：${escapeHtml(taskCount)}`,
    `难度：${DIFFICULTY_LABELS[project.difficulty] || '未知'}`,
    `维护者响应：${formatNumber(project.responsiveness, '小时')}`,
    `近30天趋势：${escapeHtml(formatTrend(project.trendDelta, project.trendDirection))}`,
    `健康数据：${escapeHtml(health)}`,
    `原始坐标：(${formatNumber(project.readiness)}, ${formatNumber(project.match)})`,
  ].join('<br/>');
}

function buildObservation(project, projects) {
  if (!project) return '';
  const taskValues = projects.map((item) => item.taskCount).filter((value) => Number.isFinite(value));
  const taskMedian = taskValues.length ? [...taskValues].sort((a, b) => a - b)[Math.floor(taskValues.length / 2)] : null;
  if (project.trendDirection === 'down' && taskMedian != null && project.taskCount >= taskMedian) return '近期热度回落，但任务供给仍较充足。';
  if (project.trendDirection === 'up' && project.healthScore == null) return '项目增长较快，健康数据仍在积累。';
  if (project.responsiveness != null) {
    const responses = projects.map((item) => item.responsiveness).filter((value) => Number.isFinite(value));
    const median = responses.length ? [...responses].sort((a, b) => a - b)[Math.floor(responses.length / 2)] : null;
    if (median != null && project.responsiveness <= median) return '维护者响应速度优于当前候选中位数。';
  }
  if (project.readiness >= 60 && project.match < 70) return '新人承接条件良好，但与当前技能匹配有限。';
  return '当前项目的任务、文档与活跃度证据正在持续积累。';
}

function getDistributionNote(projects) {
  if (!projects.length) return null;
  const highMatchCount = projects.filter((project) => project.match >= OPPORTUNITY_THRESHOLDS.match).length;
  const priorityCount = projects.filter((project) => project.match >= OPPORTUNITY_THRESHOLDS.match && project.readiness >= OPPORTUNITY_THRESHOLDS.readiness).length;
  if (highMatchCount / projects.length <= 0.6) return null;
  return { candidateCount: projects.length, priorityCount, highMatchCount };
}

export default function NewcomerOpportunityMap({ onSelectRepo }) {
  const [domains, setDomains] = useState(['ai_ml']);
  const [skills, setSkills] = useState(['python', 'typescript']);
  const [appliedProfile, setAppliedProfile] = useState({
    domains: ['ai_ml'],
    skills: ['python', 'typescript'],
  });
  const [difficulty, setDifficulty] = useState('all');
  const [minimumTasks, setMinimumTasks] = useState(0);
  const [recentOnly, setRecentOnly] = useState(false);
  const [xRange, setXRange] = useState([...DEFAULT_X_RANGE]);
  const [yRange, setYRange] = useState([...DEFAULT_Y_RANGE]);
  const [projects, setProjects] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [hoveredId, setHoveredId] = useState(null);
  const [layoutById, setLayoutById] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [chartInstance, setChartInstance] = useState(null);
  const [connector, setConnector] = useState(null);
  const [taskModal, setTaskModal] = useState({ open: false, repo: '', loading: false, error: '', board: null });
  const requestId = useRef(0);
  const zoomSyncTimer = useRef(null);
  const bodyRef = useRef(null);
  const chartWrapRef = useRef(null);
  const detailRef = useRef(null);
  const rootRef = useRef(null);

  const loadProjects = useCallback(async (requestDomains, requestSkills) => {
    const currentRequest = ++requestId.current;
    setLoading(true);
    setError('');
    try {
      const response = await postNewcomerPlan({
        domains: requestDomains,
        stacks: requestSkills,
        time_per_week: '3-5h',
      });
      if (currentRequest !== requestId.current) return;
      setProjects(adaptNewcomerProjects(response?.recommended_repos || []));
    } catch (loadError) {
      if (currentRequest !== requestId.current) return;
      setProjects([]);
      setError(loadError?.message || '新人项目机会数据加载失败');
    } finally {
      if (currentRequest === requestId.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProjects(appliedProfile.domains, appliedProfile.skills);
  }, [appliedProfile, loadProjects]);

  const candidateProjects = useMemo(
    () => filterNewcomerProjects(projects, { difficulty, minimumTasks, recentOnly }),
    [projects, difficulty, minimumTasks, recentOnly],
  );

  const filteredProjects = useMemo(
    () => candidateProjects.filter((project) => (
      project.readiness >= xRange[0]
      && project.readiness <= xRange[1]
      && project.match >= yRange[0]
      && project.match <= yRange[1]
    )),
    [candidateProjects, xRange, yRange],
  );

  const selectedProject = useMemo(
    () => filteredProjects.find((project) => project.repository === selectedId) || null,
    [filteredProjects, selectedId],
  );

  useEffect(() => {
    const next = selectedProject || selectDefaultProject(filteredProjects, minimumTasks);
    const nextId = next?.repository || null;
    if (nextId !== selectedId) setSelectedId(nextId);
  }, [filteredProjects, minimumTasks, selectedId, selectedProject]);

  const chooseProject = useCallback((project, switchRepository = true) => {
    if (!project) return;
    setSelectedId(project.repository);
    if (switchRepository && onSelectRepo) void Promise.resolve(onSelectRepo(project.repository)).catch(() => undefined);
  }, [onSelectRepo]);

  const openTaskModal = useCallback(() => {
    if (!selectedProject) return;
    const repo = selectedProject.repository;
    setTaskModal({ open: true, repo, loading: true, error: '', board: null });
    void fetchNewcomerIssues(repo, selectedProject.readiness ?? 60)
      .then((board) => setTaskModal((current) => (
        current.open && current.repo === repo
          ? { ...current, loading: false, board: board || {} }
          : current
      )))
      .catch((loadError) => setTaskModal((current) => (
        current.open && current.repo === repo
          ? { ...current, loading: false, error: loadError?.message || '新手任务加载失败' }
          : current
      )));
  }, [selectedProject]);

  const closeTaskModal = useCallback(() => {
    setTaskModal((current) => (current.open ? { ...current, open: false } : current));
  }, []);

  useEffect(() => {
    if (!taskModal.open) return undefined;
    const handleKeyDown = (event) => {
      if (event.key === 'Escape') closeTaskModal();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [closeTaskModal, taskModal.open]);

  const taskGroups = useMemo(
    () => TASK_CATEGORY_META.map((category) => ({
      ...category,
      items: Array.isArray(taskModal.board?.[category.key]) ? taskModal.board[category.key] : [],
    })),
    [taskModal.board],
  );
  const taskTotal = taskGroups.reduce((total, group) => total + group.items.length, 0);

  const scheduleAxisSync = useCallback(() => {
    if (!chartInstance) return;
    if (zoomSyncTimer.current) window.clearTimeout(zoomSyncTimer.current);
    zoomSyncTimer.current = window.setTimeout(() => {
      const zooms = chartInstance.getOption()?.dataZoom || [];
      const xZoom = zooms.find((zoom) => zoom.id === 'newcomer-x-range');
      const yZoom = zooms.find((zoom) => zoom.id === 'newcomer-y-range');
      const readRange = (zoom) => {
        const start = Number(zoom?.start);
        const end = Number(zoom?.end);
        if (!Number.isFinite(start) || !Number.isFinite(end)) return null;
        return [start, end].map((percent) => (
          Math.round((AXIS_MIN + (AXIS_MAX - AXIS_MIN) * percent / 100) / AXIS_STEP) * AXIS_STEP
        ));
      };
      const nextX = readRange(xZoom);
      const nextY = readRange(yZoom);
      if (nextX) setXRange((current) => (current[0] === nextX[0] && current[1] === nextX[1] ? current : nextX));
      if (nextY) setYRange((current) => (current[0] === nextY[0] && current[1] === nextY[1] ? current : nextY));
      zoomSyncTimer.current = null;
    }, 100);
  }, [chartInstance]);

  useEffect(() => () => {
    if (zoomSyncTimer.current) window.clearTimeout(zoomSyncTimer.current);
  }, []);

  const chartEvents = useMemo(() => ({
    click: (params) => chooseProject(params.data?.project),
    mouseover: (params) => setHoveredId(params.data?.project?.repository || null),
    mouseout: () => setHoveredId(null),
    datazoom: scheduleAxisSync,
  }), [chooseProject, scheduleAxisSync]);

  const option = useMemo(() => {
    const reducedMotion = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const [xMin, xMax] = xRange;
    const [yMin, yMax] = yRange;
    const markLineData = [
      ...(OPPORTUNITY_THRESHOLDS.readiness >= xMin && OPPORTUNITY_THRESHOLDS.readiness <= xMax ? [{ xAxis: OPPORTUNITY_THRESHOLDS.readiness }] : []),
      ...(OPPORTUNITY_THRESHOLDS.match >= yMin && OPPORTUNITY_THRESHOLDS.match <= yMax ? [{ yAxis: OPPORTUNITY_THRESHOLDS.match }] : []),
    ];
    const markAreaData = buildOpportunityAreas(xRange, yRange);
    const data = candidateProjects.map((project) => ({
      id: project.repository,
      name: project.repository,
      value: [project.readiness, project.match, project.taskCount],
      project,
    }));
    const rawLabels = layoutById;
    return {
      animation: !reducedMotion,
      animationDuration: reducedMotion ? 0 : 260,
      animationDurationUpdate: reducedMotion ? 0 : 180,
      animationEasingUpdate: 'cubicOut',
      grid: { left: 108, right: 34, top: 92, bottom: 100, containLabel: false },
      graphic: [{
        type: 'text',
        left: 'center',
        bottom: 4,
        silent: true,
        style: {
          text: `新手就绪度 ${xMin}–${xMax} →`,
          fill: '#173b32',
          font: '500 13px "Noto Sans SC", "PingFang SC", sans-serif',
        },
      }],
      dataZoom: [
        {
          id: 'newcomer-x-range',
          type: 'slider',
          xAxisIndex: 0,
          startValue: xMin,
          endValue: xMax,
          rangeMode: ['value', 'value'],
          minValueSpan: AXIS_MIN_GAP,
          filterMode: 'filter',
          realtime: true,
          throttle: 50,
          brushSelect: false,
          showDataShadow: false,
          showDetail: false,
          left: 108,
          right: 34,
          bottom: 30,
          height: 18,
          borderColor: 'transparent',
          backgroundColor: 'rgba(23,59,50,.08)',
          fillerColor: 'rgba(47,147,133,.24)',
          handleSize: 16,
          handleStyle: { color: '#173b32', borderColor: '#f8f5ec', borderWidth: 2 },
          moveHandleSize: 0,
          textStyle: { color: '#52615a', fontSize: 10 },
        },
        {
          id: 'newcomer-y-range',
          type: 'slider',
          yAxisIndex: 0,
          orient: 'vertical',
          startValue: yMin,
          endValue: yMax,
          rangeMode: ['value', 'value'],
          minValueSpan: AXIS_MIN_GAP,
          filterMode: 'filter',
          realtime: true,
          throttle: 50,
          brushSelect: false,
          showDataShadow: false,
          showDetail: false,
          left: 18,
          top: 92,
          bottom: 100,
          width: 18,
          borderColor: 'transparent',
          backgroundColor: 'rgba(23,59,50,.08)',
          fillerColor: 'rgba(47,147,133,.24)',
          handleSize: 16,
          handleStyle: { color: '#173b32', borderColor: '#f8f5ec', borderWidth: 2 },
          moveHandleSize: 0,
          textStyle: { color: '#52615a', fontSize: 10 },
        },
      ],
      tooltip: {
        trigger: 'item',
        confine: true,
        backgroundColor: '#f8f5ec',
        borderColor: '#173b32',
        borderWidth: 1,
        borderRadius: 2,
        textStyle: { color: '#202823', fontSize: 12 },
        formatter: (params) => params.data?.project ? projectTooltip(params.data.project) : '',
      },
      xAxis: {
        type: 'value', min: AXIS_MIN, max: AXIS_MAX, interval: AXIS_STEP,
        axisLine: { lineStyle: { color: '#173b32', width: 1 } },
        axisLabel: { color: '#52615a', fontSize: 12, fontWeight: 500 },
        splitLine: { lineStyle: { color: 'rgba(23,59,50,.10)', type: 'dashed', width: 1 } },
      },
      yAxis: {
        type: 'value', min: AXIS_MIN, max: AXIS_MAX, interval: AXIS_STEP,
        name: '用户匹配度 ↑', nameLocation: 'middle', nameGap: 50, nameRotate: 90,
        nameTextStyle: { color: '#173b32', fontSize: 15, fontWeight: 500 },
        axisLine: { lineStyle: { color: '#173b32', width: 1 } },
        axisLabel: { color: '#52615a', fontSize: 12, fontWeight: 500 },
        splitLine: { lineStyle: { color: 'rgba(23,59,50,.10)', type: 'dashed', width: 1 } },
      },
      series: [
        {
          id: 'newcomer-quadrants', type: 'scatter', silent: true, data: [], z: 0,
          markLine: {
            silent: true, symbol: 'none',
            lineStyle: { color: 'rgba(23,59,50,.65)', type: 'dashed', width: 1 },
            label: { show: false },
            data: markLineData,
          },
          markArea: {
            silent: true,
            label: { show: true, color: '#315044', fontSize: 14, fontWeight: 500, position: 'insideTopLeft', distance: 16 },
            data: markAreaData,
          },
        },
        {
          id: 'newcomer-project-nodes', type: 'custom', z: 4, data,
          renderItem: (params, api) => {
            const project = resolveCustomDataItem(data, params)?.project;
            if (!project) return null;
            const rawPoint = api.coord([api.value(0), api.value(1)]);
            if (!Array.isArray(rawPoint) || rawPoint.length < 2 || rawPoint.some((item) => !Number.isFinite(item))) return null;
            const layout = rawLabels[project.repository] || {};
            const x = rawPoint[0] + Number(layout.offsetX || 0);
            const y = rawPoint[1] + Number(layout.offsetY || 0);
            const radius = getBubbleRadius(project.taskCount);
            const selected = project.repository === selectedId;
            const emerging = project.isEmerging;
            const opacity = hoveredId && project.repository !== hoveredId ? 0.55 : 1;
            const children = [];
            if (layout.displaced) {
              children.push({ type: 'line', shape: { x1: rawPoint[0], y1: rawPoint[1], x2: x, y2: y }, style: { stroke: 'rgba(23,59,50,.22)', lineWidth: 1 } });
              children.push({ type: 'circle', shape: { cx: rawPoint[0], cy: rawPoint[1], r: 2 }, style: { fill: '#173b32', opacity: 0.6 } });
            }
            if (emerging) children.push({ type: 'circle', shape: { cx: x, cy: y, r: radius + 5 }, style: { fill: 'transparent', stroke: DIFFICULTY_COLORS[project.difficulty], lineWidth: 1.2, lineDash: [4, 4], opacity } });
            if (selected) {
              children.push({ type: 'circle', shape: { cx: x, cy: y, r: radius + 6 }, style: { fill: 'transparent', stroke: '#476fbd', lineWidth: 2, opacity } });
              children.push({ type: 'circle', shape: { cx: x, cy: y, r: radius + 10 }, style: { fill: 'transparent', stroke: '#173b32', lineWidth: 1.5, opacity } });
            }
            children.push({ type: 'circle', shape: { cx: x, cy: y, r: radius }, style: { fill: DIFFICULTY_COLORS[project.difficulty], stroke: '#f8f5ec', lineWidth: 1.5, opacity } });
            if (emerging) children.push({ type: 'text', style: { x: x + radius * 0.64, y: y - radius * 0.85, text: '★', fill: '#d69a32', font: '12px serif', opacity } });
            if (selected) children.push({ type: 'rect', shape: { x: x + radius + 10, y: y + radius + 6, width: 112, height: 24, r: 3 }, style: { fill: 'rgba(47,147,133,.88)', opacity } });
            if (selected) children.push({ type: 'text', style: { x: x + radius + 66, y: y + radius + 18, text: projectStatusTag(project), fill: '#f8f5ec', font: '12px "Noto Sans SC", sans-serif', textAlign: 'center', textVerticalAlign: 'middle', opacity } });
            return { type: 'group', children, silent: false };
          },
        },
      ],
    };
  }, [candidateProjects, hoveredId, layoutById, selectedId, xRange, yRange]);

  useEffect(() => {
    if (!chartInstance || !filteredProjects.length) {
      setLayoutById({});
      return undefined;
    }
    const coordinate = { xAxisIndex: 0, yAxisIndex: 0 };
    const topLeft = safeChartPixel(chartInstance, coordinate, [xRange[0], yRange[1]]);
    const bottomRight = safeChartPixel(chartInstance, coordinate, [xRange[1], yRange[0]]);
    const thresholdPoint = safeChartPixel(chartInstance, coordinate, [
      Math.max(xRange[0], Math.min(xRange[1], OPPORTUNITY_THRESHOLDS.readiness)),
      Math.max(yRange[0], Math.min(yRange[1], OPPORTUNITY_THRESHOLDS.match)),
    ]);
    if (!topLeft || !bottomRight || !thresholdPoint) {
      setLayoutById({});
      return undefined;
    }
    const reservedBoxes = [
      { x: topLeft[0] + 12, y: topLeft[1] + 8, width: 96, height: 24 },
      { x: thresholdPoint[0] + 12, y: topLeft[1] + 8, width: 96, height: 24 },
      { x: topLeft[0] + 12, y: thresholdPoint[1] + 8, width: 96, height: 24 },
      { x: thresholdPoint[0] + 12, y: thresholdPoint[1] + 8, width: 96, height: 24 },
    ];
    const nodes = filteredProjects
      .map((project) => {
        const point = safeChartPixel(chartInstance, coordinate, [project.readiness, project.match]);
        if (!point) return null;
        const trendArrow = project.trendDirection ? TREND_META[project.trendDirection]?.arrow : '';
        const label = trendArrow ? `${project.repository} ${trendArrow}` : project.repository;
        return { id: project.repository, label, rawPixelX: point[0], rawPixelY: point[1], radius: getBubbleRadius(project.taskCount), selected: project.repository === selectedId };
      })
      .filter(Boolean);
    if (!nodes.length) {
      setLayoutById({});
      return undefined;
    }
    const laidOut = layoutOpportunityNodes(nodes, {
      maxDisplacement: 36,
      iterations: 24,
      bounds: { left: topLeft[0], top: topLeft[1], right: bottomRight[0], bottom: bottomRight[1] },
      reservedBoxes,
    });
    setLayoutById(Object.fromEntries(laidOut.map((node) => [node.id, node])));
    return undefined;
  }, [chartInstance, filteredProjects, selectedId, xRange, yRange]);

  const updateConnector = useCallback(() => {
    if (!chartInstance || !selectedProject || !bodyRef.current || !chartWrapRef.current || !detailRef.current || window.innerWidth < 850) {
      setConnector(null);
      return;
    }
    const point = safeChartPixel(chartInstance, { xAxisIndex: 0, yAxisIndex: 0 }, [selectedProject.readiness, selectedProject.match]);
    const layout = layoutById[selectedProject.repository];
    if (!Array.isArray(point) || point.some((value) => !Number.isFinite(value))) return;
    const bodyRect = bodyRef.current.getBoundingClientRect();
    const chartRect = chartWrapRef.current.getBoundingClientRect();
    const detailRect = detailRef.current.getBoundingClientRect();
    const displayX = point[0] + Number(layout?.offsetX || 0) + getBubbleRadius(selectedProject.taskCount);
    const displayY = point[1] + Number(layout?.offsetY || 0);
    const x1 = chartRect.left - bodyRect.left + displayX;
    const y1 = chartRect.top - bodyRect.top + displayY;
    const edgeX = detailRect.left - bodyRect.left;
    setConnector({ width: bodyRect.width, height: bodyRect.height, x1, y1, edgeX });
  }, [chartInstance, layoutById, selectedProject]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(updateConnector);
    return () => window.cancelAnimationFrame(frame);
  }, [updateConnector, option]);

  useEffect(() => {
    const target = bodyRef.current;
    if (!target || typeof ResizeObserver === 'undefined') return undefined;
    let frame = 0;
    const observer = new ResizeObserver(() => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        chartInstance?.resize();
        updateConnector();
      });
    });
    observer.observe(target);
    return () => { window.cancelAnimationFrame(frame); observer.disconnect(); };
  }, [chartInstance, updateConnector]);

  useEffect(() => {
    const onFullscreen = () => window.requestAnimationFrame(() => { chartInstance?.resize(); updateConnector(); });
    document.addEventListener('fullscreenchange', onFullscreen);
    return () => document.removeEventListener('fullscreenchange', onFullscreen);
  }, [chartInstance, updateConnector]);

  const enterFullscreen = () => { if (rootRef.current?.requestFullscreen) void rootRef.current.requestFullscreen(); };
  const generateMap = () => {
    setAppliedProfile({
      domains: [...domains],
      skills: [...skills],
    });
  };
  const resetAxisRanges = () => {
    setXRange([...DEFAULT_X_RANGE]);
    setYRange([...DEFAULT_Y_RANGE]);
    chartInstance?.dispatchAction({
      type: 'dataZoom',
      dataZoomId: 'newcomer-x-range',
      startValue: DEFAULT_X_RANGE[0],
      endValue: DEFAULT_X_RANGE[1],
    });
    chartInstance?.dispatchAction({
      type: 'dataZoom',
      dataZoomId: 'newcomer-y-range',
      startValue: DEFAULT_Y_RANGE[0],
      endValue: DEFAULT_Y_RANGE[1],
    });
  };
  const exportPng = () => {
    if (!chartInstance) return;
    const dataUrl = chartInstance.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#f4f0e5' });
    const link = document.createElement('a');
    link.href = dataUrl;
    link.download = 'newcomer-project-opportunity-atlas.png';
    link.click();
  };
  const moveSelection = (direction) => {
    if (!filteredProjects.length) return;
    const currentIndex = Math.max(0, filteredProjects.findIndex((project) => project.repository === selectedId));
    chooseProject(filteredProjects[(currentIndex + direction + filteredProjects.length) % filteredProjects.length]);
  };

  const distributionNote = getDistributionNote(filteredProjects);
  const observation = buildObservation(selectedProject, filteredProjects);

  return (
    <section ref={rootRef} className="newcomer-opportunity-map" aria-label="开源新人项目机会地图" onKeyDown={(event) => {
      if (event.key === 'ArrowLeft') { event.preventDefault(); moveSelection(-1); }
      if (event.key === 'ArrowRight') { event.preventDefault(); moveSelection(1); }
    }} tabIndex={0}>
      <header className="newcomer-map-header">
        <div className="newcomer-map-title">
          <h2>开源新人项目机会地图</h2>
          <span>NEWCOMER PROJECT OPPORTUNITY ATLAS</span>
        </div>
        <div className="newcomer-map-controls" aria-label="新人项目筛选">
          <MultiSelectFilter label="兴趣方向" options={DOMAIN_OPTIONS} values={domains} onChange={setDomains} />
          <MultiSelectFilter label="已有技能" options={SKILL_OPTIONS} values={skills} onChange={setSkills} />
          <label className="newcomer-filter-field"><span className="newcomer-filter-label">难度</span><select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>{DIFFICULTY_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          <label className="newcomer-filter-field"><span className="newcomer-filter-label">最少任务数</span><select value={minimumTasks} onChange={(event) => setMinimumTasks(Number(event.target.value))}>{TASK_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
          <label className="newcomer-recent-filter"><input type="checkbox" checked={recentOnly} onChange={(event) => setRecentOnly(event.target.checked)} />仅看近期活跃</label>
          <span className="newcomer-map-hint" title="健康评分缺失不会淘汰新项目">ⓘ 新锐项目不因健康分积累中而被排除</span>
        </div>
        <div className="newcomer-map-actions">
          <button className="newcomer-generate-button" type="button" onClick={generateMap} disabled={loading}>{loading ? '生成中…' : '生成地图'}</button>
          <button type="button" onClick={enterFullscreen} title="机会地图全屏">全屏</button>
          <button type="button" onClick={exportPng} title="导出机会地图 PNG">导出</button>
        </div>
      </header>

      <div className="newcomer-map-body" ref={bodyRef}>
        <div className="newcomer-map-chart-wrap" ref={chartWrapRef}>
          <div className="newcomer-axis-toolbar" aria-label="地图坐标显示范围">
            <div className="newcomer-axis-toolbar-title">
              <strong>显示范围</strong>
              <span>拖动端点实时调整地图</span>
            </div>
            <AxisRangeFilter label="横轴 · 新手就绪度" value={xRange} onChange={setXRange} />
            <AxisRangeFilter label="纵轴 · 用户匹配度" value={yRange} onChange={setYRange} />
            <button
              type="button"
              onClick={resetAxisRanges}
              disabled={xRange[0] === DEFAULT_X_RANGE[0] && xRange[1] === DEFAULT_X_RANGE[1] && yRange[0] === DEFAULT_Y_RANGE[0] && yRange[1] === DEFAULT_Y_RANGE[1]}
            >
              恢复默认
            </button>
          </div>
          <div className="newcomer-map-chart-canvas">
            <button
              className="newcomer-axis-reset"
              type="button"
              onClick={resetAxisRanges}
              disabled={xRange[0] === DEFAULT_X_RANGE[0] && xRange[1] === DEFAULT_X_RANGE[1] && yRange[0] === DEFAULT_Y_RANGE[0] && yRange[1] === DEFAULT_Y_RANGE[1]}
            >
              恢复默认范围
            </button>
            {loading ? <div className="newcomer-map-state newcomer-map-skeleton">正在读取真实新人项目数据…</div> : error ? <div className="newcomer-map-state"><strong>{error}</strong><button type="button" onClick={() => void loadProjects(appliedProfile.domains, appliedProfile.skills)}>重新加载</button></div> : (
              <ReactECharts
                option={option}
                notMerge={false}
                replaceMerge={['series']}
                lazyUpdate
                onChartReady={setChartInstance}
                onEvents={chartEvents}
                style={{ width: '100%', height: '520px' }}
                opts={{ renderer: 'canvas' }}
                aria-label="用户匹配度与新手就绪度四象限气泡图"
              />
            )}
            {!loading && !error && !filteredProjects.length && <div className="newcomer-map-empty-overlay">当前范围暂无符合条件的项目<br /><small>请拖动范围端点，或放宽任务数、难度和近期活跃条件。</small></div>}

          </div>
          <div className="newcomer-map-legend" aria-label="机会地图图例">
            <div><strong>难度</strong><span><i style={{ background: DIFFICULTY_COLORS.easy }} />容易</span><span><i style={{ background: DIFFICULTY_COLORS.medium }} />适中</span><span><i style={{ background: DIFFICULTY_COLORS.hard }} />挑战</span></div>
            <div><strong>趋势</strong><span className="legend-trend-up">↗ 上升</span><span>→ 稳定</span><span className="legend-trend-down">↘ 下降</span></div>
            <div><strong>气泡大小</strong><span className="bubble-size-sample"><i />40+</span><span className="bubble-size-sample"><i />20–39</span><span className="bubble-size-sample"><i />5–19</span></div>
            <div><strong>新锐热门</strong><span className="emerging-legend"><i />虚线环 + ★</span></div>
          </div>
           {distributionNote && <div className="newcomer-distribution-note"><span aria-hidden="true">ⓘ</span><div>当前筛选下，多数候选项目集中于高匹配区<br /><strong>{distributionNote.candidateCount}个候选 · {distributionNote.priorityCount}个优先参与</strong></div></div>}
        </div>
        <aside className="newcomer-map-detail" ref={detailRef} aria-live="polite">
          {selectedProject ? <>
            <div className="newcomer-detail-kicker">当前选中 · {projectStatus(selectedProject)}</div>
            <h3>{selectedProject.repository}</h3>
            <div className="newcomer-detail-tags"><span>{selectedProject.matchedDomains?.[0] || '开源项目'}</span><span>{selectedProject.matchedStacks?.[0] || '多技术栈'}</span>{selectedProject.isEmerging && <span>新锐热门</span>}</div>
            <dl>
              <div><dt>匹配度</dt><dd>{formatNumber(selectedProject.match, '%')}</dd></div>
              <div><dt>新手就绪度</dt><dd>{formatNumber(selectedProject.readiness, '%')}</dd></div>
              <div><dt>可领取任务</dt><dd>{selectedProject.taskCount == null ? '任务数据不足' : selectedProject.taskCount}</dd></div>
              <div><dt>难度</dt><dd>{DIFFICULTY_LABELS[selectedProject.difficulty]}</dd></div>
              <div><dt>维护者响应</dt><dd>{formatNumber(selectedProject.responsiveness, 'h')}</dd></div>
              <div><dt>健康数据</dt><dd>{selectedProject.healthScore == null ? '积累中' : `${Math.round(selectedProject.healthScore)} / 100`}</dd></div>
              <div><dt>近30天趋势</dt><dd className={selectedProject.trendDirection ? `trend-${selectedProject.trendDirection}` : ''}>{formatTrend(selectedProject.trendDelta, selectedProject.trendDirection)}</dd></div>
            </dl>
            {observation && <div className="newcomer-detail-observation">{observation}</div>}
            <div className="newcomer-detail-reasons"><strong>推荐依据</strong><ul>{(selectedProject.reasons.length ? selectedProject.reasons : ['暂无可解释推荐依据']).slice(0, 4).map((reason) => <li key={reason}>{reason}</li>)}</ul></div>
            <div className="newcomer-detail-actions"><a href={selectedProject.url} target="_blank" rel="noreferrer">↗ 查看仓库</a><button type="button" onClick={() => chooseProject(selectedProject)}>切换为当前仓库</button><button type="button" onClick={openTaskModal}>查看新手任务</button></div>
          </> : <div className="newcomer-detail-empty">选择一个项目查看新人参与证据。</div>}

        </aside>
        {connector && <svg className="newcomer-map-connector" aria-hidden="true" viewBox={`0 0 ${connector.width} ${connector.height}`}><path d={`M ${connector.x1} ${connector.y1} L ${connector.edgeX} ${connector.y1}`} /><circle cx={connector.edgeX} cy={connector.y1} r="3" /></svg>}
      </div>

      {taskModal.open && (
        <div className="newcomer-task-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) closeTaskModal(); }}>
          <section className="newcomer-task-modal" role="dialog" aria-modal="true" aria-labelledby="newcomer-task-modal-title">
            <header className="newcomer-task-modal-header">
              <div>
                <span className="newcomer-task-modal-kicker">当前仓库 · 新手任务</span>
                <h3 id="newcomer-task-modal-title">{taskModal.repo}</h3>
              </div>
              <button type="button" className="newcomer-task-modal-close" onClick={closeTaskModal} aria-label="关闭新手任务弹窗" title="关闭">×</button>
            </header>
            {taskModal.loading ? <div className="newcomer-task-modal-state">正在读取该仓库的新手任务…</div> : taskModal.error ? (
              <div className="newcomer-task-modal-state newcomer-task-modal-error"><strong>{taskModal.error}</strong><button type="button" onClick={openTaskModal}>重新加载</button></div>
            ) : taskTotal === 0 ? <div className="newcomer-task-modal-state">当前仓库暂无新手任务数据。</div> : (
              <div className="newcomer-task-groups">
                {taskGroups.filter((group) => group.items.length).map((group) => (
                  <section key={group.key} className="newcomer-task-group">
                    <div className="newcomer-task-group-heading"><h4>{group.label}</h4><span>{group.items.length} 项</span></div>
                    <ul>
                      {group.items.map((task, index) => (
                        <li key={task.url || task.issue_number || task.title || index}>
                          <div className="newcomer-task-item-main">
                            {task.url ? <a href={task.url} target="_blank" rel="noreferrer">{task.title || '未命名任务'}</a> : <strong>{task.title || '未命名任务'}</strong>}
                            {task.issue_number != null && <span className="newcomer-task-issue">#{task.issue_number}</span>}
                          </div>
                          <div className="newcomer-task-item-meta">
                            <span>{task.difficulty || '难度未标注'}</span>
                            {task.updated_from_now && <span>{task.updated_from_now}</span>}
                            {Array.isArray(task.labels) && task.labels.length > 0 && <span>{task.labels.slice(0, 3).join(' · ')}</span>}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </section>
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </section>
  );
}