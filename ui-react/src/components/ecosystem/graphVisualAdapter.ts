import {
  clamp,
  contributionStrength,
  contributorVisualSize,
  edgeVisualOpacity,
  edgeVisualSize,
  repositoryVisualSize,
} from './graphVisualScale';
import { communityKey } from './graphLayout';

export const VISUAL_ROLE_COLORS = Object.freeze({
  core: '#42679A',
  active: '#34765F',
  new: '#B48332',
  inactive: '#66756E',
  risk: '#BD6047',
});

function endpointId(endpoint) {
  return typeof endpoint === 'object' ? endpoint?.id : endpoint;
}

function scoreOf(node) {
  const score = Number(node.contribution_score ?? node.association_strength ?? node.health_score);
  return Number.isFinite(score) && score > 0 ? score : 0;
}

function shortLabel(node) {
  const value = String(node.login || node.repo || node.label || node.id || '?');
  if (node.type === 'contributor') return value.slice(0, 2).toUpperCase();
  return value.split('/').at(-1)?.slice(0, 4).toUpperCase() || value.slice(0, 4).toUpperCase();
}

function roleOf(node) {
  return ['core', 'active', 'new', 'risk'].includes(node?.role) ? node.role : 'inactive';
}

function blendWithPaper(hex, amount) {
  const value = String(hex).replace('#', '');
  const source = [
    Number.parseInt(value.slice(0, 2), 16),
    Number.parseInt(value.slice(2, 4), 16),
    Number.parseInt(value.slice(4, 6), 16),
  ];
  const paper = [245, 241, 231];
  return '#' + source.map((channel, index) => Math.round(paper[index] + (channel - paper[index]) * amount).toString(16).padStart(2, '0')).join('');
}

function edgeRoleColor(link, nodeById) {
  const source = nodeById.get(link.source);
  const target = nodeById.get(link.target);
  const contributor = target?.type === 'contributor' ? target : source?.type === 'contributor' ? source : null;
  return VISUAL_ROLE_COLORS[roleOf(contributor)] || '#66756E';
}

function edgeColor(link, nodeById, visualOpacity, active, isInteracting) {
  if (active) return '#172A25';
  const base = edgeRoleColor(link, nodeById);
  if (isInteracting) return blendWithPaper(base, 0.08);
  return blendWithPaper(base, Math.max(0.24, Math.min(1, visualOpacity / 0.58)));
}

export function contributorAvatarUrl(login, avatarUrl) {
  if (avatarUrl) return avatarUrl;
  const normalizedLogin = String(login || '').trim();
  if (!/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?(?:\[bot\])?$/.test(normalizedLogin)) return undefined;
  return 'https://avatars.githubusercontent.com/' + encodeURIComponent(normalizedLogin) + '?s=192';
}

export function visualTypeOf(node) {
  if (node.is_root) return 'root-repository';
  return node.type === 'repository' ? 'repository' : 'contributor';
}

export function visualClusterOf(node) {
  if (visualTypeOf(node) !== 'contributor') return undefined;
  return communityKey(node);
}

export function buildVisualNodes(nodes, {
  minScore = 0,
  maxScore = 1,
  topContributorIds = new Set(),
  contributorIndexes = new Map(),
  annotations = new Map(),
  selectedId = null,
  focusIds = new Set(),
  bundleExpandedRoutes = false,
  hoveredId = null,
  selectionPulse = 0,
  loadingNodeId = null,
  collapsingIds = new Set(),
} = {}) {
  const fallbackIndexes = new Map(
    nodes
      .filter((node) => node.type === 'contributor')
      .sort((left, right) => Number(right.contribution_score || 0) - Number(left.contribution_score || 0) || String(left.id).localeCompare(String(right.id)))
      .map((node, index) => [node.id, index + 2]),
  );
  const expandedRouteTargets = selectedId && bundleExpandedRoutes
    ? nodes
      .filter((node) => node.type === 'repository' && !node.is_root && node.parent_id === selectedId)
      .map((node) => ({
        id: node.id,
        x: Number(node.x ?? node.fx ?? 0),
        y: Number(node.y ?? node.fy ?? 0),
      }))
    : [];
  const seen = new Set();
  return nodes.filter((node) => {
    if (seen.has(node.id)) return false;
    seen.add(node.id);
    return true;
  }).map((node) => {
    const visualType = visualTypeOf(node);
    const score = scoreOf(node);
    const isTopContributor = topContributorIds.has(node.id);
    const visualSize = visualType === 'root-repository'
      ? repositoryVisualSize(score, true)
      : visualType === 'repository'
        ? repositoryVisualSize(node.stars ?? score, false)
        : contributorVisualSize(score, minScore, maxScore);
    return {
      id: node.id,
      label: node.label || node.login || node.repo,
      fill: node.is_root ? '#172A25' : visualType === 'repository' ? '#B48332' : VISUAL_ROLE_COLORS[roleOf(node)],
      size: visualSize,
      parents: node.parent_id ? [node.parent_id] : [],
      ...(Number.isFinite(Number(node.x)) ? {
        fx: Number(node.x),
        ...(Number.isFinite(Number(node.y)) ? { fy: Number(node.y) } : {}),
        fz: Number(node.z || 0),
      } : {}),
      labelVisible: false,
      data: {
        ...node,
        rawType: node.type,
        visualType,
        visualCluster: visualClusterOf(node),
        contributionScore: score,
        contributionNormalized: contributionStrength(score, minScore, maxScore),
        visualSize,
        annotation: annotations.get(node.id) || null,
        avatarUrl: visualType === 'contributor'
          ? contributorAvatarUrl(node.login, node.avatar_url || node.avatarUrl)
          : undefined,
        shortLabel: shortLabel(node),
        risk: Boolean(node.churn_risk || node.role === 'risk'),
        isTopContributor,
        researchIndex: contributorIndexes.get(node.id) || fallbackIndexes.get(node.id) || null,
        __showLabel: Boolean(node.is_root || visualType === 'repository' || isTopContributor || selectedId === node.id || hoveredId === node.id),
        __hovered: hoveredId === node.id,
        __dimmed: Boolean((selectedId || hoveredId) && !focusIds.has(node.id)),
        __relatedHighlight: Boolean(selectedId && visualType === 'repository' && !node.is_root && node.parent_id === selectedId),
        __expandedRouteTargets: selectedId === node.id
          ? expandedRouteTargets.map((target) => ({
            ...target,
            x: target.x - Number(node.x ?? node.fx ?? 0),
            y: target.y - Number(node.y ?? node.fy ?? 0),
          }))
          : [],
        __selectionPulse: selectedId === node.id ? selectionPulse : 0,
        __loading: loadingNodeId === node.id,
        __collapsing: collapsingIds.has(node.id),
      },
    };
  });
}

function mergedLinks(links) {
  const merged = new Map();
  for (const link of links || []) {
    const source = endpointId(link.source);
    const target = endpointId(link.target);
    if (!source || !target || source === target) continue;
    const relationType = link.relationship_type || link.relationType || (link.is_shared ? 'shared' : 'default');
    const key = source + '→' + target + ':' + relationType;
    const previous = merged.get(key);
    if (previous) {
      previous.weight = Number(previous.weight || 0) + Number(link.weight ?? link.strength ?? link.contribution_score ?? link.association_strength ?? 0);
      previous.count += 1;
      previous.originalEdgeIds.push(link.id || key + ':' + previous.count);
    } else {
      merged.set(key, {
        ...link,
        source,
        target,
        relationType,
        weight: Number(link.weight ?? link.strength ?? link.contribution_score ?? link.association_strength ?? 0),
        count: 1,
        originalEdgeIds: [link.id || key + ':1'],
      });
    }
  }
  return [...merged.values()];
}

export function buildVisualEdges(links, maxWeight, {
  selectedIds = new Set(),
  hoveredId = null,
  nodeById = new Map(),
  muted = false,
} = {}) {
  const edges = [];
  const isInteracting = selectedIds.size > 0 || Boolean(hoveredId);

  for (const link of mergedLinks(links)) {
    const active = (selectedIds.has(link.source) && selectedIds.has(link.target))
      || link.source === hoveredId || link.target === hoveredId;
    const visualOpacity = edgeVisualOpacity(link.weight, maxWeight, active);
    const size = edgeVisualSize(link.weight, maxWeight, active);
    const baseFill = edgeColor(link, nodeById, visualOpacity, active, isInteracting);
    const fill = muted && !active ? blendWithPaper(baseFill, 0.42) : baseFill;
    const originalId = link.source + '→' + link.target + ':' + link.relationType;
    edges.push({
      id: originalId,
      source: link.source,
      target: link.target,
      size,
      fill,
      arrowPlacement: 'none',
      data: { ...link, visualOpacity, active },
    });
  }

  return { edges, routingNodes: [] };
}
const STRUCTURE_COMMUNITY_COLORS = Object.freeze({
  core: VISUAL_ROLE_COLORS.core,
  active: VISUAL_ROLE_COLORS.active,
  lifecycle: VISUAL_ROLE_COLORS.risk,
});

export function buildStructureEdges(links, maxWeight, {
  selectedContributorId = null,
  hoveredId = null,
  nodeById = new Map(),
  junctionPositions = {},
} = {}) {
  const merged = mergedLinks(links);
  const rootNode = [...nodeById.values()].find((node) => node.is_root);
  if (!rootNode) return buildVisualEdges(links, maxWeight, { nodeById });

  const grouped = new Map([['core', []], ['active', []], ['lifecycle', []]]);
  const passthrough = [];
  for (const link of merged) {
    const sourceNode = nodeById.get(link.source);
    const targetNode = nodeById.get(link.target);
    const contributor = sourceNode?.is_root && targetNode?.type === 'contributor'
      ? targetNode
      : targetNode?.is_root && sourceNode?.type === 'contributor'
        ? sourceNode
        : null;
    if (!contributor) {
      passthrough.push(link);
      continue;
    }
    grouped.get(communityKey(contributor)).push({ link, contributor });
  }

  const focusId = selectedContributorId || hoveredId;
  const focusCommunity = focusId ? communityKey(nodeById.get(focusId) || {}) : null;
  const isInteracting = Boolean(focusId);
  const routingNodes = [];
  const routedEdges = [];
  const communityTotals = [...grouped.entries()].map(([community, members]) => ({
    community,
    total: members.reduce((sum, item) => sum + Math.max(0, Number(item.link.weight) || 0), 0),
  }));
  const maxCommunityTotal = Math.max(1, ...communityTotals.map((item) => item.total));

  for (const { community, total } of communityTotals) {
    const members = grouped.get(community);
    if (!members.length) continue;
    const position = junctionPositions[community];
    if (!position) continue;
    const color = STRUCTURE_COMMUNITY_COLORS[community];
    const junctionId = '__route_junction__' + community;
    routingNodes.push({
      id: junctionId,
      label: '',
      fill: color,
      size: 5,
      fx: position.x,
      fy: position.y,
      fz: Number(position.z || 0),
      labelVisible: false,
      data: {
        id: junctionId,
        type: 'routing-junction',
        visualType: 'routing-junction',
        layoutOnly: true,
        community,
        fill: color,
        visualSize: 5,
        x: position.x,
        y: position.y,
        z: Number(position.z || 0),
      },
    });

    const trunkBaseSize = Number(clamp(1.8 + Math.sqrt(total / maxCommunityTotal) * 1.4, 1.8, 3.2).toFixed(2));
    const trunkFocused = !isInteracting || focusCommunity === community;
    routedEdges.push({
      id: 'structure-trunk:' + rootNode.id + ':' + community,
      source: rootNode.id,
      target: junctionId,
      size: trunkFocused ? trunkBaseSize : Math.max(0.45, trunkBaseSize * 0.3),
      fill: blendWithPaper(color, trunkFocused ? 0.76 : 0.08),
      arrowPlacement: 'none',
      data: {
        kind: 'community-trunk',
        community,
        baseSize: trunkBaseSize,
        originalEdgeIds: members.flatMap((item) => item.link.originalEdgeIds || []),
      },
    });

    for (const { link, contributor } of members) {
      const baseSize = edgeVisualSize(link.weight, maxWeight, false);
      const active = !isInteracting || contributor.id === focusId;
      const visualOpacity = edgeVisualOpacity(link.weight, maxWeight, contributor.id === focusId);
      routedEdges.push({
        id: 'structure-branch:' + junctionId + ':' + contributor.id,
        source: junctionId,
        target: contributor.id,
        size: active ? baseSize : Math.max(0.25, baseSize * 0.28),
        fill: blendWithPaper(color, active ? Math.max(0.32, visualOpacity) : 0.07),
        arrowPlacement: 'none',
        data: {
          kind: 'community-branch',
          community,
          contributorId: contributor.id,
          baseSize,
          originalEdgeIds: link.originalEdgeIds || [],
        },
      });
    }
  }

  const focusPathIds = focusId
    ? new Set([
      focusId,
      ...[...nodeById.values()]
        .filter((node) => node.type === 'repository' && !node.is_root && node.parent_id === focusId)
        .map((node) => node.id),
    ])
    : new Set();
  const expandedPathLinks = focusId
    ? passthrough.filter((link) => focusPathIds.has(link.source) && focusPathIds.has(link.target))
    : [];
  const expandedPathKeys = new Set(expandedPathLinks.map((link) => link.source + '→' + link.target + ':' + link.relationType));
  const passthroughBundle = buildVisualEdges(
    passthrough.filter((link) => !expandedPathKeys.has(link.source + '→' + link.target + ':' + link.relationType)),
    maxWeight,
    {
      selectedIds: focusPathIds,
      hoveredId: selectedContributorId ? null : hoveredId,
      nodeById,
    },
  );
  return { edges: [...routedEdges, ...passthroughBundle.edges], routingNodes };
}
