export const CONTRIBUTION_WEIGHTS = Object.freeze({
  commits: 1,
  pull_requests: 3,
  reviews: 2,
  issues: 1,
});

export const NODE_COLORS = Object.freeze({
  root: '#3978F6',
  repository: '#6675E8',
  core: '#7768E8',
  active: '#17A6A4',
  new: '#26B879',
  risk: '#EF6969',
  inactive: '#91A4B7',
});

export const ROLE_LABELS = Object.freeze({
  core: '核心贡献者',
  active: '活跃贡献者',
  new: '新贡献者',
  risk: '流失风险',
  inactive: '不活跃贡献者',
});

export const GRAPH_LIMITS = Object.freeze({
  nodes: 40,
  links: 60,
  depth: 1,
  contributorRepos: 3,
  repositoryContributors: 0,
});

export const ORBIT_RADII = Object.freeze({
  core: 52,
  active: 78,
  new: 104,
  risk: 104,
  inactive: 112,
  repository: 140,
  expandedContributor: 174,
});

export function endpointId(endpoint) {
  return typeof endpoint === 'object' ? endpoint?.id : endpoint;
}

export function nodeColor(node) {
  if (node.is_root) return NODE_COLORS.root;
  if (node.type === 'repository') return NODE_COLORS.repository;
  return NODE_COLORS[node.role] || NODE_COLORS.inactive;
}

export function nodeRadius(node, maxContribution) {
  if (node.is_root) return 9.5;
  if (node.type === 'repository') {
    const value = Number(node.association_strength ?? node.health_score);
    if (!Number.isFinite(value) || value <= 0) return 6.5;
    const normalized = Math.sqrt(Math.log1p(value) / Math.log1p(Math.max(value, maxContribution, 1)));
    return Math.min(9, Math.max(6.5, 6.5 + 2.5 * normalized));
  }
  const value = Number(node.contribution_score);
  if (!Number.isFinite(value) || value <= 0 || maxContribution <= 0) return 4.6;
  const normalized = Math.sqrt(Math.log1p(value) / Math.log1p(Math.max(1, maxContribution)));
  return Math.min(8.5, Math.max(4.6, 4.6 + 3.9 * normalized));
}

export function edgeWidth(link, maxStrength, selected = false) {
  if (selected) return 2.05;
  const value = Number(link.weight ?? link.contribution_score ?? link.association_strength ?? 0);
  if (!Number.isFinite(value) || value <= 0 || maxStrength <= 0) return 0.9;
  const normalized = Math.log1p(value) / Math.log1p(Math.max(1, maxStrength));
  return Math.min(1.4, Math.max(0.8, 0.8 + 0.6 * normalized));
}

function hashValue(id) {
  let hash = 2166136261;
  for (let index = 0; index < id.length; index += 1) {
    hash ^= id.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return Math.abs(hash);
}

export function deterministicOffset(id, distance = 30) {
  const hash = hashValue(id);
  const theta = (hash % 360) * (Math.PI / 180);
  const phi = (((hash >> 8) % 120) + 30) * (Math.PI / 180);
  return {
    x: distance * Math.sin(phi) * Math.cos(theta),
    y: distance * Math.sin(phi) * Math.sin(theta),
    z: distance * Math.cos(phi),
  };
}

export function orbitRadius(node) {
  if (node.is_root) return 0;
  if (node.type === 'repository') return ORBIT_RADII.repository + Math.max(0, Number(node.depth || 2) - 2) * 34;
  if (Number(node.depth || 1) >= 3) return ORBIT_RADII.expandedContributor;
  return ORBIT_RADII[node.role] || ORBIT_RADII.inactive;
}

export function orbitDepth(node) {
  if (node.is_root) return 0;
  if (node.type === 'repository') return Math.min(24, 14 + Math.max(0, Number(node.depth || 2) - 2) * 8);
  if (Number(node.depth || 1) >= 3) return 28;
  return { core: -6, active: 0, new: 6, risk: 8, inactive: 10 }[node.role] ?? 4;
}

export function orbitalPosition(node, siblingIndex = 0, siblingCount = 1) {
  if (node.is_root) return { x: 0, y: 0, z: 0 };
  const radius = orbitRadius(node);
  const hash = hashValue(node.id);
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));
  const theta = siblingIndex * goldenAngle + (hash % 31) * 0.032;
  const radialJitter = siblingCount > 8 ? ((hash >> 7) % 9) - 4 : 0;
  return {
    x: (radius + radialJitter) * Math.cos(theta),
    y: (radius + radialJitter) * Math.sin(theta),
    z: orbitDepth(node) + (((hash >> 11) % 7) - 3) * 0.7,
  };
}

export function linkDistance(link, nodesById) {
  const source = nodesById.get(endpointId(link.source));
  const target = nodesById.get(endpointId(link.target));
  const outerDepth = Math.max(Number(source?.depth || 0), Number(target?.depth || 0));
  if (outerDepth <= 1) return 66;
  if (outerDepth === 2) return 96;
  return 116;
}

export function formatMetric(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '数据缺失';
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: digits }).format(Number(value));
}