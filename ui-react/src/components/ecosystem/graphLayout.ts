import { buildDensityContours } from './communityDensity';

const POSITION_CACHE = new Map();
const DEFAULT_PLOT_SIZE = Object.freeze({ width: 920, height: 520 });
const NORMALIZED_ANCHORS = Object.freeze({
  root: { x: 0.52, y: 0.46 },
  core: { x: 0.27, y: 0.23 },
  active: { x: 0.27, y: 0.66 },
  lifecycle: { x: 0.76, y: 0.62 },
  selected: { x: 0.59, y: 0.46 },
  related: [
    { x: 0.87, y: 0.25 },
    { x: 0.9, y: 0.48 },
    { x: 0.87, y: 0.72 },
  ],
});

export const COMMUNITY_STYLE = Object.freeze({
  core: { fill: '#5879A5', stroke: '#5879A5', label: '核心维护者社区\nCORE MAINTAINERS' },
  active: { fill: '#60927D', stroke: '#60927D', label: '活跃贡献者社区\nACTIVE CONTRIBUTORS' },
  lifecycle: { fill: '#D18A69', stroke: '#D18A69', label: '新晋与流失风险社区\nCHURN RISK COMMUNITY' },
});

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function stableHash(id) {
  let hash = 2166136261;
  for (const character of String(id)) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return Math.abs(hash);
}

export function createPlotRect(size = DEFAULT_PLOT_SIZE) {
  const measuredWidth = Number(size?.width) || DEFAULT_PLOT_SIZE.width;
  const measuredHeight = Number(size?.height) || DEFAULT_PLOT_SIZE.height;
  const width = clamp(measuredWidth - 76, 680, 1180);
  const height = clamp(measuredHeight - 46, 380, 620);
  return {
    x: -width / 2,
    y: -height / 2,
    width,
    height,
  };
}

function plotPoint(rect, normalized) {
  return {
    x: rect.x + normalized.x * rect.width,
    y: -(rect.y + normalized.y * rect.height),
  };
}

export function getNarrativeAnchors(size = DEFAULT_PLOT_SIZE) {
  const rect = createPlotRect(size);
  return {
    rect,
    root: plotPoint(rect, NORMALIZED_ANCHORS.root),
    core: plotPoint(rect, NORMALIZED_ANCHORS.core),
    active: plotPoint(rect, NORMALIZED_ANCHORS.active),
    lifecycle: plotPoint(rect, NORMALIZED_ANCHORS.lifecycle),
    selected: plotPoint(rect, NORMALIZED_ANCHORS.selected),
    related: NORMALIZED_ANCHORS.related.map((anchor) => plotPoint(rect, anchor)),
  };
}

export const NARRATIVE_ANCHORS = Object.freeze(getNarrativeAnchors(DEFAULT_PLOT_SIZE));

export function seededPosition(id, parent = null) {
  if (POSITION_CACHE.has(id)) return { ...POSITION_CACHE.get(id) };
  const hash = stableHash(id);
  const angle = (hash % 360) * Math.PI / 180;
  const radius = 48 + (hash % 64);
  const base = {
    x: Number(parent?.x || 0) + Math.cos(angle) * radius,
    y: Number(parent?.y || 0) + Math.sin(angle) * radius,
    z: 0,
  };
  POSITION_CACHE.set(id, base);
  return { ...base };
}

export function communityKey(node) {
  if (node.role === 'core') return 'core';
  if (node.role === 'active' || node.role === 'inactive') return 'active';
  return 'lifecycle';
}

function withFixedPosition(node, position, z = 0) {
  return {
    ...node,
    ...position,
    z,
    fx: position.x,
    fy: position.y,
    fz: z,
  };
}

function nodeRadius(node, minScore, maxScore) {
  const value = Number(node.contribution_score);
  if (!Number.isFinite(value) || value <= 0) return 15;
  const minRoot = Math.sqrt(Math.max(0, minScore));
  const maxRoot = Math.sqrt(Math.max(0, maxScore));
  const normalized = maxRoot === minRoot ? 0.5 : clamp((Math.sqrt(value) - minRoot) / Math.max(0.001, maxRoot - minRoot), 0, 1);
  return 15 + normalized * 17;
}

function communityExtent(key, rect) {
  if (key === 'core') return { x: rect.width * 0.115, y: rect.height * 0.12 };
  if (key === 'active') return { x: rect.width * 0.17, y: rect.height * 0.2 };
  return { x: rect.width * 0.145, y: rect.height * 0.18 };
}

function lobeOffset(key, hash, rect) {
  if (key === 'active') {
    const lobes = [
      { x: -rect.width * 0.045, y: rect.height * 0.025 },
      { x: rect.width * 0.048, y: rect.height * 0.035 },
      { x: rect.width * 0.005, y: -rect.height * 0.065 },
    ];
    return lobes[hash % lobes.length];
  }
  if (key === 'lifecycle') {
    const lobes = [
      { x: -rect.width * 0.028, y: rect.height * 0.035 },
      { x: rect.width * 0.04, y: -rect.height * 0.04 },
    ];
    return lobes[hash % lobes.length];
  }
  return { x: 0, y: 0 };
}

function placeCommunity(members, key, center, rect) {
  if (!members.length) return new Map();
  const values = members.map((node) => Number(node.contribution_score)).filter((value) => Number.isFinite(value) && value > 0);
  const minScore = values.length ? Math.min(...values) : 0;
  const maxScore = values.length ? Math.max(...values) : 1;
  const extent = communityExtent(key, rect);
  const placed = [];
  const positions = new Map();

  members.forEach((node, index) => {
    const hash = stableHash(node.id);
    const rankProgress = members.length <= 1 ? 0 : index / (members.length - 1);
    const angle = ((hash % 360) + index * 137.508) * Math.PI / 180;
    const radial = 0.2 + rankProgress * 0.72 + ((hash >> 8) % 13) / 100;
    const lobe = lobeOffset(key, hash, rect);
    const radius = nodeRadius(node, minScore, maxScore);
    let x = center.x + lobe.x + Math.cos(angle) * extent.x * radial;
    let y = center.y + lobe.y + Math.sin(angle) * extent.y * radial;

    for (let iteration = 0; iteration < 28; iteration += 1) {
      let moved = false;
      for (const other of placed) {
        const dx = x - other.x;
        const dy = y - other.y;
        const distance = Math.hypot(dx, dy);
        const minimumDistance = radius + other.radius + 8;
        if (distance >= minimumDistance) continue;
        const fallbackAngle = ((hash + iteration * 47) % 360) * Math.PI / 180;
        const unitX = distance > 0.01 ? dx / distance : Math.cos(fallbackAngle);
        const unitY = distance > 0.01 ? dy / distance : Math.sin(fallbackAngle);
        const push = (minimumDistance - distance) * 0.62 + 1;
        x += unitX * push;
        y += unitY * push;
        moved = true;
      }
      x = clamp(x, center.x - extent.x, center.x + extent.x);
      y = clamp(y, center.y - extent.y, center.y + extent.y);
      if (!moved) break;
    }

    const position = { x, y, z: 0 };
    placed.push({ x, y, radius });
    positions.set(node.id, position);
  });
  return positions;
}

export function prepareNarrativePositions(nodes, selectedId = null, plotSize = DEFAULT_PLOT_SIZE) {
  const anchors = getNarrativeAnchors(plotSize);
  const communities = new Map([['core', []], ['active', []], ['lifecycle', []]]);
  for (const node of nodes) {
    if (node.type === 'contributor' && node.id !== selectedId) communities.get(communityKey(node)).push(node);
  }
  for (const members of communities.values()) {
    members.sort((a, b) => Number(b.contribution_score || 0) - Number(a.contribution_score || 0) || String(a.id).localeCompare(String(b.id)));
  }

  const communityPositions = new Map();
  for (const [key, members] of communities) {
    for (const [id, position] of placeCommunity(members, key, anchors[key], anchors.rect)) {
      communityPositions.set(id, position);
    }
  }

  const related = nodes
    .filter((node) => node.type === 'repository' && !node.is_root && node.parent_id === selectedId)
    .sort((a, b) => Number(b.association_strength || 0) - Number(a.association_strength || 0));

  return nodes.map((node) => {
    if (node.userPinned && Number.isFinite(Number(node.x)) && Number.isFinite(Number(node.y))) {
      return withFixedPosition(node, { x: Number(node.x), y: Number(node.y) }, Number(node.z || 0));
    }
    if (node.is_root) return withFixedPosition(node, anchors.root);
    if (node.id === selectedId) return withFixedPosition(node, anchors.selected);
    const relatedIndex = related.findIndex((item) => item.id === node.id);
    if (relatedIndex >= 0) return withFixedPosition(node, anchors.related[relatedIndex] || anchors.related.at(-1));
    if (node.type === 'repository') return withFixedPosition(node, seededPosition(node.id, anchors.root));
    return withFixedPosition(node, communityPositions.get(node.id) || anchors[communityKey(node)]);
  });
}

function densityBandwidth(members) {
  const xs = members.map((node) => Number(node.x ?? node.fx ?? 0));
  const ys = members.map((node) => Number(node.y ?? node.fy ?? 0));
  const extent = Math.max(
    Math.max(...xs) - Math.min(...xs),
    Math.max(...ys) - Math.min(...ys),
  );
  const base = members.length <= 3 ? 42 : members.length <= 7 ? 36 : 30;
  return clamp(base + extent * 0.025, 28, 52);
}

export function buildCommunityZones(nodes, selectedId = null, focusCommunity = null) {
  return ['core', 'active', 'lifecycle'].flatMap((key) => {
    const members = nodes.filter((node) => node.type === 'contributor' && node.id !== selectedId && communityKey(node) === key);
    if (!members.length) return [];
    const style = COMMUNITY_STYLE[key];
    const weightedTotal = members.reduce((sum, node) => sum + Math.max(1, Math.sqrt(Number(node.contribution_score) || 0)), 0);
    const center = {
      x: members.reduce((sum, node) => sum + Number(node.x ?? node.fx ?? 0) * Math.max(1, Math.sqrt(Number(node.contribution_score) || 0)), 0) / weightedTotal,
      y: members.reduce((sum, node) => sum + Number(node.y ?? node.fy ?? 0) * Math.max(1, Math.sqrt(Number(node.contribution_score) || 0)), 0) / weightedTotal,
    };
    const samples = members.map((node) => ({
      x: Number(node.x ?? node.fx ?? 0) - center.x,
      y: Number(node.y ?? node.fy ?? 0) - center.y,
      weight: Number(node.contribution_score || 0),
    }));
    const thresholdCount = key === 'active' ? 10 : 8;
    const density = buildDensityContours(samples, {
      bandwidth: densityBandwidth(members),
      thresholdCount,
    });
    const radiusX = Math.max(Math.abs(density.bounds.minX), Math.abs(density.bounds.maxX));
    const radiusY = Math.max(Math.abs(density.bounds.minY), Math.abs(density.bounds.maxY));
    const communityState = focusCommunity ? (focusCommunity === key ? 'focused' : 'dimmed') : 'default';
    const id = 'community-zone:' + key;
    return [{
      id,
      label: style.label,
      size: Math.max(radiusX, radiusY),
      fill: style.fill,
      fx: center.x,
      fy: center.y,
      fz: -4,
      data: {
        id,
        type: 'community-zone',
        visualType: 'community-zone',
        community: key,
        communityState,
        label: style.label,
        fill: style.fill,
        stroke: style.stroke,
        radiusX,
        radiusY,
        samples,
        contours: density.levels,
        densityBounds: density.bounds,
        bandwidth: density.bandwidth,
        memberCount: members.length,
        x: center.x,
        y: center.y,
        z: -4,
      },
    }];
  });
}

export function prepareForcePositions(nodes, _nodeMap = null, plotSize = DEFAULT_PLOT_SIZE) {
  return prepareNarrativePositions(nodes, null, plotSize);
}

export const CUSTOM_LAYOUT_OVERRIDES = Object.freeze({
  getNodePosition: (id, { graph, drags }) => {
    const dragged = drags?.[id]?.position;
    if (dragged) return dragged;
    const attributes = graph.getNodeAttributes(id);
    return {
      x: Number(attributes.fx ?? attributes.data?.x ?? 0),
      y: Number(attributes.fy ?? attributes.data?.y ?? 0),
      z: Number(attributes.fz ?? attributes.data?.z ?? 0),
    };
  },
});

export const FORCE_LAYOUT_OVERRIDES = CUSTOM_LAYOUT_OVERRIDES;
