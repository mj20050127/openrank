export const OPPORTUNITY_THRESHOLDS = Object.freeze({
  readiness: 60,
  match: 70,
});

export const DIFFICULTY_COLORS = Object.freeze({
  easy: '#2f9385',
  medium: '#d69a32',
  hard: '#d56f50',
});

export const DIFFICULTY_LABELS = Object.freeze({ easy: '容易', medium: '适中', hard: '挑战' });

export const TREND_META = Object.freeze({
  up: { arrow: '↗', label: '上升', color: '#476fbd' },
  stable: { arrow: '→', label: '稳定', color: '#173b32' },
  down: { arrow: '↘', label: '下降', color: '#b84935' },
});

const DAY_MS = 24 * 60 * 60 * 1000;

export function clamp(value, min = 0, max = 100) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  return Math.max(min, Math.min(max, numeric));
}

export function getBubbleRadius(taskCount) {
  const numeric = Number(taskCount);
  const base = Number.isFinite(numeric) ? Math.max(numeric, 1) : 1;
  return Math.max(14, Math.min(32, 10 + Math.sqrt(base) * 3));
}

export function normalizeDifficulty(value) {
  const normalized = String(value || '').trim().toLowerCase();
  if (normalized === 'easy' || normalized === '容易') return 'easy';
  if (normalized === 'hard' || normalized === '挑战' || normalized === '困难') return 'hard';
  if (normalized === 'medium' || normalized === '适中') return 'medium';
  return 'medium';
}

export function normalizeTrend(value) {
  if (value == null || value === '') return null;
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return null;
  const percent = Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
  if (percent >= 5) return 'up';
  if (percent <= -5) return 'down';
  return 'stable';
}

export function countUniqueTasks(tasks) {
  if (!Array.isArray(tasks)) return null;
  const seen = new Set();
  tasks.forEach((task, index) => {
    const key = task?.id ?? task?.issue_id ?? task?.issue_number ?? task?.number ?? task?.url ?? `${task?.repository || ''}:${task?.title || index}`;
    if (key != null && String(key).trim()) seen.add(String(key));
  });
  return seen.size;
}

export function getTaskCount(stats) {
  if (!stats || typeof stats !== 'object') return null;
  const keys = ['good_first', 'help_wanted', 'docs', 'i18n'];
  const values = keys.map((key) => Number(stats[key])).filter(Number.isFinite);
  if (!values.length) return null;
  return values.reduce((sum, value) => sum + Math.max(0, value), 0);
}

function asStringList(value) {
  if (!Array.isArray(value)) return [];
  return value.filter((item) => typeof item === 'string' && item.trim()).map((item) => item.trim());
}

function asDate(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

function hasRecentActivity(raw) {
  if (typeof raw.is_recently_active === 'boolean') return raw.is_recently_active;
  if (typeof raw.recently_active === 'boolean') return raw.recently_active;
  const activityDate = asDate(raw.last_activity_at || raw.lastActivityAt || raw.pushed_at);
  if (activityDate) {
    const age = Date.now() - activityDate.getTime();
    return age >= 0 && age <= 90 * DAY_MS;
  }
  const activity = Number(raw.activity);
  return Number.isFinite(activity) && activity > 0;
}

function buildReason(raw, taskCount) {
  const reasons = Array.isArray(raw.reasons)
    ? raw.reasons.filter((reason) => typeof reason === 'string' && reason.trim())
    : [];
  if (reasons.length) return reasons.slice(0, 4);
  const matchedDomains = asStringList(raw.matched_domains || raw.matchedDomains);
  const matchedStacks = asStringList(raw.matched_stacks || raw.matchedStacks);
  const result = [];
  if (matchedDomains.length) result.push(`命中方向：${matchedDomains.join('、')}`);
  if (matchedStacks.length) result.push(`命中技能：${matchedStacks.join('、')}`);
  if (taskCount != null) result.push(`当前有 ${taskCount} 个可领取新人任务`);
  if (raw.responsiveness != null && Number.isFinite(Number(raw.responsiveness))) {
    result.push(`维护者响应中位数约 ${Math.round(Number(raw.responsiveness))} 小时`);
  }
  return result.slice(0, 4);
}

export function resolveCustomDataItem(data, params) {
  if (params?.data) return params.data;
  const index = Number.isInteger(params?.dataIndexInside)
    ? params.dataIndexInside
    : params?.dataIndex;
  return Number.isInteger(index) && Array.isArray(data) ? data[index] || null : null;
}
export function adaptNewcomerProjects(rawProjects) {
  if (!Array.isArray(rawProjects)) return [];
  return rawProjects
    .map((raw, index) => {
      const repository = raw?.repo_full_name || raw?.repository || raw?.name;
      if (!repository) return null;
      const taskCount = Array.isArray(raw.newcomer_tasks) ? countUniqueTasks(raw.newcomer_tasks) : getTaskCount(raw.stats);
      const trendDelta = raw.trend_delta == null ? null : Number(raw.trend_delta);
      const healthScore = clamp(raw.health_score ?? raw.healthScore);
      const readiness = clamp(raw.readiness_score ?? raw.newcomer_readiness);
      const match = clamp(raw.match_score ?? raw.user_match ?? raw.fit_score);
      return {
        repository,
        url: raw.url || `https://github.com/${repository}`,
        description: raw.description || '',
        rank: Number.isFinite(Number(raw.rank)) ? Number(raw.rank) : index + 1,
        domains: asStringList(raw.domains),
        stacks: asStringList(raw.stacks),
        matchedDomains: asStringList(raw.matched_domains || raw.matchedDomains),
        matchedStacks: asStringList(raw.matched_stacks || raw.matchedStacks),
        taskCount,
        taskStats: raw.stats && typeof raw.stats === 'object' ? { ...raw.stats } : null,
        readiness,
        match,
        difficulty: normalizeDifficulty(raw.difficulty),
        responsiveness: raw.responsiveness == null ? null : Number(raw.responsiveness),
        activity: raw.activity == null ? null : Number(raw.activity),
        trendDelta: Number.isFinite(trendDelta) ? trendDelta : null,
        trendDirection: normalizeTrend(trendDelta),
        healthScore,
        healthScoreStatus: raw.health_score_status || raw.healthScoreStatus || (healthScore == null ? 'accumulating' : 'available'),
        documentationScore: clamp(raw.documentation_score ?? raw.documentationScore),
        recentActivityScore: clamp(raw.recent_activity_score ?? raw.recentActivityScore),
        recentlyActive: hasRecentActivity(raw),
        isEmerging: raw.is_emerging === true || raw.isEmerging === true,
        evidenceCoverage: clamp(raw.evidence_coverage ?? raw.evidenceCoverage),
        reasons: buildReason(raw, taskCount),
        raw,
      };
    })
    .filter(Boolean);
}

export function filterNewcomerProjects(projects, filters) {
  const selectedDomains = filters?.domains || [];
  const selectedSkills = filters?.skills || [];
  const selectedDifficulty = filters?.difficulty || 'all';
  const minimumTasks = Number(filters?.minimumTasks ?? 0);
  const recentOnly = Boolean(filters?.recentOnly);
  return projects.filter((project) => {
    const projectDomains = [...project.domains, ...project.matchedDomains].map((item) => item.toLowerCase());
    const projectSkills = [...project.stacks, ...project.matchedStacks].map((item) => item.toLowerCase());
    if (selectedDomains.length && !selectedDomains.some((domain) => projectDomains.includes(domain.toLowerCase()))) return false;
    if (selectedSkills.length && !selectedSkills.some((skill) => projectSkills.includes(skill.toLowerCase()))) return false;
    if (selectedDifficulty !== 'all' && project.difficulty !== selectedDifficulty) return false;
    if (minimumTasks > 0 && (project.taskCount == null || project.taskCount < minimumTasks)) return false;
    if (recentOnly && !project.recentlyActive) return false;
    return project.readiness != null && project.match != null;
  });
}

export function selectDefaultProject(projects, minimumTasks = 5) {
  if (!projects.length) return null;
  const ranked = [...projects].sort((a, b) => {
    const isPriority = (project) => project.readiness >= OPPORTUNITY_THRESHOLDS.readiness
      && project.match >= OPPORTUNITY_THRESHOLDS.match
      && (project.taskCount ?? 0) >= minimumTasks
      && project.recentlyActive;
    return Number(isPriority(b)) - Number(isPriority(a))
      || b.match - a.match
      || b.readiness - a.readiness
      || (b.taskCount ?? -1) - (a.taskCount ?? -1);
  });
  return ranked[0];
}

export function formatTrend(delta, direction) {
  if (delta == null || !direction || !TREND_META[direction]) return '趋势数据不足';
  const numeric = Number(delta);
  const percent = Math.abs(numeric) <= 1 ? numeric * 100 : numeric;
  return `${TREND_META[direction].arrow} ${percent >= 0 ? '+' : ''}${Math.round(percent)}%`;
}

export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}
export function layoutOpportunityNodes(nodes, options = {}) {
  const maxDisplacement = Number(options.maxDisplacement ?? 36);
  const iterations = Number(options.iterations ?? 24);
  const padding = Number(options.padding ?? 10);
  const bounds = options.bounds || null;
  const working = (nodes || []).map((node, index) => ({
    ...node,
    index,
    displayX: Number(node.rawPixelX) || 0,
    displayY: Number(node.rawPixelY) || 0,
    radius: Number(node.radius) || 14,
    selected: Boolean(node.selected),
  }));

  for (let iteration = 0; iteration < iterations; iteration += 1) {
    for (let first = 0; first < working.length; first += 1) {
      for (let second = first + 1; second < working.length; second += 1) {
        const a = working[first];
        const b = working[second];
        let dx = b.displayX - a.displayX;
        let dy = b.displayY - a.displayY;
        let distance = Math.sqrt(dx * dx + dy * dy);
        if (distance < 0.001) {
          const direction = ((a.index + 1) * 17 + (b.index + 1) * 31) % 2 ? 1 : -1;
          dx = direction;
          dy = direction * 0.37;
          distance = Math.sqrt(dx * dx + dy * dy);
        }
        const minimumDistance = a.radius + b.radius + padding;
        if (distance >= minimumDistance) continue;
        const overlap = minimumDistance - distance;
        const unitX = dx / distance;
        const unitY = dy / distance;
        const aWeight = a.selected ? 0.25 : 0.5;
        const bWeight = b.selected ? 0.25 : 0.5;
        const totalWeight = aWeight + bWeight;
        a.displayX -= unitX * overlap * (aWeight / totalWeight);
        a.displayY -= unitY * overlap * (aWeight / totalWeight);
        b.displayX += unitX * overlap * (bWeight / totalWeight);
        b.displayY += unitY * overlap * (bWeight / totalWeight);
      }
    }
    for (const node of working) {
      node.displayX += (node.rawPixelX - node.displayX) * 0.08;
      node.displayY += (node.rawPixelY - node.displayY) * 0.08;
      const deltaX = node.displayX - node.rawPixelX;
      const deltaY = node.displayY - node.rawPixelY;
      const displacement = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
      if (displacement > maxDisplacement) {
        const ratio = maxDisplacement / displacement;
        node.displayX = node.rawPixelX + deltaX * ratio;
        node.displayY = node.rawPixelY + deltaY * ratio;
      }
      if (bounds) {
        node.displayX = Math.max(bounds.left + node.radius, Math.min(bounds.right - node.radius, node.displayX));
        node.displayY = Math.max(bounds.top + node.radius, Math.min(bounds.bottom - node.radius, node.displayY));
      }
    }
  }

  const labelGap = Number(options.labelGap ?? 5);
  const occupiedLabels = [];
  const reservedLabels = [
    ...(Array.isArray(options.reservedBoxes) ? options.reservedBoxes : []),
    ...working
      .filter((node) => node.selected)
      .map((node) => ({
        x: node.displayX + node.radius + 10,
        y: node.displayY + node.radius + 6,
        width: 112,
        height: 24,
      })),
  ];
  const rectanglesOverlap = (first, second, gap = 0) => (
    first.x < second.x + second.width + gap
    && first.x + first.width + gap > second.x
    && first.y < second.y + second.height + gap
    && first.y + first.height + gap > second.y
  );
  const clampCandidate = (candidate) => {
    if (!bounds) return candidate;
    const maxX = Math.max(bounds.left, bounds.right - candidate.width);
    const maxY = Math.max(bounds.top, bounds.bottom - candidate.height);
    return {
      ...candidate,
      x: Math.max(bounds.left, Math.min(maxX, candidate.x)),
      y: Math.max(bounds.top, Math.min(maxY, candidate.y)),
    };
  };
  const getPosition = (candidate, node) => {
    const centerX = candidate.x + candidate.width / 2;
    const centerY = candidate.y + candidate.height / 2;
    if (centerX <= node.displayX - node.radius) return 'left';
    if (centerX >= node.displayX + node.radius) return 'right';
    return centerY < node.displayY ? 'top' : 'bottom';
  };

  const placementByIndex = new Map();
  const placementOrder = [...working].sort((first, second) => (
    Number(second.selected) - Number(first.selected) || first.index - second.index
  ));

  for (const node of placementOrder) {
    const offsetX = node.displayX - node.rawPixelX;
    const offsetY = node.displayY - node.rawPixelY;
    const labelWidth = Math.min(260, Math.max(88, String(node.label || node.id || '').length * 7.8 + 12));
    const labelHeight = node.selected ? 20 : 18;
    const candidates = [];
    const addCandidate = (x, y) => {
      const candidate = clampCandidate({
        x,
        y,
        width: labelWidth,
        height: labelHeight,
      });
      const centerX = candidate.x + candidate.width / 2;
      const centerY = candidate.y + candidate.height / 2;
      candidates.push({
        ...candidate,
        position: getPosition(candidate, node),
        leaderLength: Math.hypot(centerX - node.displayX, centerY - node.displayY),
      });
    };

    const verticalOffsets = [0, -22, 22, -44, 44, -66, 66, -88, 88, -110, 110, -132, 132];
    verticalOffsets.forEach((verticalOffset) => {
      addCandidate(
        node.displayX + node.radius + 10,
        node.displayY + verticalOffset - labelHeight / 2,
      );
      addCandidate(
        node.displayX - node.radius - 10 - labelWidth,
        node.displayY + verticalOffset - labelHeight / 2,
      );
    });

    const horizontalOffsets = [0, -44, 44, -88, 88, -132, 132];
    horizontalOffsets.forEach((horizontalOffset) => {
      addCandidate(
        node.displayX + horizontalOffset - labelWidth / 2,
        node.displayY - node.radius - 10 - labelHeight,
      );
      addCandidate(
        node.displayX + horizontalOffset - labelWidth / 2,
        node.displayY + node.radius + 10,
      );
    });

    if (bounds) {
      const railStep = labelHeight + labelGap;
      for (let y = bounds.top; y <= bounds.bottom - labelHeight; y += railStep) {
        addCandidate(bounds.left + 4, y);
        addCandidate(bounds.right - labelWidth - 4, y);
      }
    }

    const obstacles = [...reservedLabels, ...occupiedLabels];
    const chosen = candidates
      .map((candidate) => {
        const labelOverlap = obstacles.reduce(
          (total, other) => total + Number(rectanglesOverlap(candidate, other, labelGap)),
          0,
        );
        const bubbleOverlap = working.reduce((total, other) => {
          const closestX = Math.max(candidate.x, Math.min(other.displayX, candidate.x + candidate.width));
          const closestY = Math.max(candidate.y, Math.min(other.displayY, candidate.y + candidate.height));
          const distance = Math.hypot(closestX - other.displayX, closestY - other.displayY);
          return total + Number(distance < other.radius + 3);
        }, 0);
        return {
          ...candidate,
          cost: labelOverlap * 100000 + bubbleOverlap * 1000 + candidate.leaderLength,
        };
      })
      .sort((first, second) => first.cost - second.cost)[0];

    occupiedLabels.push(chosen);
    placementByIndex.set(node.index, {
      offsetX,
      offsetY,
      displaced: Math.hypot(offsetX, offsetY) > 5,
      labelPosition: chosen.position,
      labelBox: chosen,
    });
  }

  return working.map((node) => ({
    ...node,
    displayX: node.displayX,
    displayY: node.displayY,
    ...placementByIndex.get(node.index),
  }));
}