import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { GraphCanvas, useSelection } from 'reagraph';
import { Vector3 } from 'three';
import { fetchEcosystemExpansion, fetchEcosystemGraph } from '../../service/api';
import EcosystemGraphControls from './EcosystemGraphControlsV2';
import { FlatReagraphNode } from './EcosystemGraphNodes';
import EcosystemTooltip from './EcosystemTooltip';
import { applyGraphCameraPreset } from './graphCameraConfig';
import { buildStructureEdges, buildVisualEdges, buildVisualNodes } from './graphVisualAdapter';
import { buildCommunityZones, communityKey, createPlotRect, CUSTOM_LAYOUT_OVERRIDES, getStructureJunctionPositions, prepareForcePositions, prepareNarrativePositions, prepareStructurePositions, seededPosition } from './graphLayout';
import { lightTechnologyTheme } from './lightTechnologyTheme';
import EcosystemLegend from './EcosystemLegend';
import NetworkEncodingLegend from './NetworkEncodingLegend';
import EcosystemNodePanel from './EcosystemNodePanelV2';
import EcosystemTimeline from './EcosystemTimelineV2';
import {
  endpointId,
  GRAPH_LIMITS,
} from './graphVisualConfig';
import './ecosystem.css';

const DEFAULT_FILTERS = { role: 'all', minimum: 0, labelsOnly: false };
const ATLAS_COLUMNS = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10'];
const ATLAS_ROWS = ['A', 'B', 'C', 'D', 'E', 'F'];

function recentActivityDate(node) {
  const value = node?.last_active_at
    || node?.last_active_date
    || node?.recent_active_at
    || node?.latest_active_month
    || node?.last_activity
    || null;
  return value ? String(value).slice(0, 10) : null;
}

function narrativeAnnotations(nodes, viewportWidth, contributorIndexes) {
  const limit = viewportWidth >= 1440 ? 3 : viewportWidth >= 1200 ? 2 : 0;
  if (!limit) return new Map();
  const contributors = nodes
    .filter((node) => node.type === 'contributor' && Number(node.contribution_score) > 0)
    .sort((left, right) => Number(right.contribution_score) - Number(left.contribution_score));
  const total = contributors.reduce((sum, node) => sum + Number(node.contribution_score || 0), 0);
  const selected = [];
  const add = (node) => {
    if (node && !selected.some((item) => item.id === node.id) && selected.length < limit) selected.push(node);
  };
  add(contributors.find((node) => communityKey(node) === 'core'));
  add(contributors.find((node) => communityKey(node) === 'active'));
  add(contributors.find((node) => communityKey(node) === 'lifecycle'));
  contributors.forEach(add);

  return new Map(selected.map((node, index) => {
    const community = communityKey(node);
    const contribution = Number(node.contribution_score || 0);
    const commits = Number(node.commits);
    const explicitShare = Number(node.contribution_share);
    const share = Number.isFinite(explicitShare)
      ? (explicitShare <= 1 ? explicitShare * 100 : explicitShare)
      : total > 0 ? (contribution / total) * 100 : null;
    return [node.id, {
      index: contributorIndexes.get(node.id) || index + 2,
      login: String(node.login || node.label || node.id),
      commits: Number.isFinite(commits) && commits > 0 ? commits.toLocaleString('zh-CN') : null,
      contribution: Number.isFinite(contribution) && contribution > 0 ? contribution.toLocaleString('zh-CN') : null,
      share: Number.isFinite(share) ? share.toFixed(1) : null,
      date: recentActivityDate(node),
      side: community === 'active' ? 'left' : 'right',
      lane: community === 'core' ? 0.7 : community === 'active' ? -0.7 : -0.25,
    }];
  }));
}

function mergePayload(current, payload, parentNode) {
  const currentNodes = new Map(current.nodes.map((node) => [node.id, node]));
  const currentLinks = new Map(current.links.map((link) => [link.id, link]));
  const addedNodeIds = [];
  const addedLinkIds = [];

  for (const incoming of payload.nodes || []) {
    const existing = currentNodes.get(incoming.id);
    if (existing) {
      const merged = { ...existing, ...incoming };
      for (const coordinate of ['x', 'y', 'z', 'fx', 'fy', 'fz', 'vx', 'vy', 'vz']) {
        if (coordinate in existing) merged[coordinate] = existing[coordinate];
      }
      currentNodes.set(incoming.id, merged);
      continue;
    }
    const next = { ...incoming };
    if (next.is_root) {
      next.x = -70; next.y = 0; next.z = 0;
      next.fx = -70; next.fy = 0; next.fz = 0;
    } else {
      const parent = currentNodes.get(next.parent_id) || parentNode;
      const position = seededPosition(next.id, parent);
      next.x = position.x;
      next.y = position.y;
      next.z = 0;
    }
    currentNodes.set(next.id, next);
    addedNodeIds.push(next.id);
  }

  for (const incoming of payload.links || []) {
    if (currentLinks.has(incoming.id)) continue;
    currentLinks.set(incoming.id, { ...incoming, source: endpointId(incoming.source), target: endpointId(incoming.target) });
    addedLinkIds.push(incoming.id);
  }
  return {
    data: { nodes: [...currentNodes.values()], links: [...currentLinks.values()] },
    addedNodeIds,
    addedLinkIds,
  };
}


export default function EcosystemGraph3D({
  rootRepo,
  records,
  healthScore,
  focusMonth,
  onSetRoot,
  onMonthFocus,
  selectedNodeId,
  onSelectedNodeIdChange,
  hoveredNodeId,
  onHoveredNodeIdChange,
  onContributorsChange,
}) {
  const graphRef = useRef(null);
  const panelRef = useRef(null);
  const graphViewportRef = useRef(null);
  const baseGraphRef = useRef({ nodes: [], links: [] });
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [meta, setMeta] = useState(null);
  const [selectionPulse, setSelectionPulse] = useState(0);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [expanding, setExpanding] = useState(false);
  const [, setHistory] = useState([]);
  const [mode, setMode] = useState('structure');
  const [locked, setLocked] = useState(false);
  const hoverTimerRef = useRef(null);
  const [loadingNodeId, setLoadingNodeId] = useState(null);
  const [collapsingIds, setCollapsingIds] = useState(new Set());
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [layoutRevision, setLayoutRevision] = useState(0);
  const [viewportWidth, setViewportWidth] = useState(() => typeof window === 'undefined' ? 1440 : window.innerWidth);
  const [cameraViewport, setCameraViewport] = useState(null);
  const [plotSize, setPlotSize] = useState({ width: 920, height: 520 });

  useEffect(() => {
    const handleResize = () => setViewportWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    const element = graphViewportRef.current;
    if (!element || typeof ResizeObserver === 'undefined') return undefined;
    let frame = 0;
    const measure = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        const width = Math.round(element.clientWidth);
        const height = Math.round(element.clientHeight);
        if (width > 0 && height > 0) setPlotSize((current) => current.width === width && current.height === height ? current : { width, height });
      });
    };
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    measure();
    return () => {
      window.cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, []);
  const healthMonths = useMemo(
    () => [...new Set((records || []).map((record) => String(record.dt).slice(0, 7)))].sort(),
    [records],
  );
  const [snapshotMonth, setSnapshotMonth] = useState(null);

  useEffect(() => {
    const requested = focusMonth && healthMonths.includes(focusMonth) ? focusMonth : healthMonths.at(-1);
    setSnapshotMonth(requested || null);
  }, [rootRepo, healthMonths, focusMonth]);

  const snapshotHealth = useMemo(() => {
    const authoritative = healthScore === null || healthScore === undefined || healthScore === ''
      ? Number.NaN
      : Number(healthScore);
    if (Number.isFinite(authoritative)) return Math.max(0, Math.min(100, authoritative));
    if (!snapshotMonth) return null;
    const record = [...(records || [])].reverse().find((item) => String(item.dt || '').startsWith(snapshotMonth));
    const fallback = Number(record?.scores?.health);
    return Number.isFinite(fallback) ? Math.max(0, Math.min(100, fallback)) : null;
  }, [healthScore, records, snapshotMonth]);


  useEffect(() => {
    if (!rootRepo || !snapshotMonth) {
      setGraphData({ nodes: [], links: [] });
      return undefined;
    }
    const controller = new AbortController();
    setStatus('loading');
    setError('');
    setNotice('');
    onSelectedNodeIdChange?.(null);
    onHoveredNodeIdChange?.(null);
    setHistory([]);
    const point = snapshotMonth + '-01';
    void fetchEcosystemGraph({
      rootRepo,
      start: point,
      end: point,
      contributorLimit: GRAPH_LIMITS.contributors,
      signal: controller.signal,
    }).then((payload) => {
      const merged = mergePayload({ nodes: [], links: [] }, payload, null);
      merged.data.nodes = prepareForcePositions(merged.data.nodes, new Map(merged.data.nodes.map((node) => [node.id, node])));
      baseGraphRef.current = structuredClone(merged.data);
      setGraphData(merged.data);
      setMeta(payload.meta || null);
      setMode('structure');
      setLocked(false);
      setStatus(payload.nodes?.length ? 'ready' : 'empty');
      if (payload.meta?.github_error) setNotice('GitHub 分项计数暂不可用；缺少贡献度的节点使用最小尺寸。');
      window.setTimeout(() => applyGraphCameraPreset(graphRef, merged.data.nodes.map((node) => node.id)), 160);
    }).catch((reason) => {
      if (reason.name === 'AbortError') return;
      setGraphData({ nodes: [], links: [] });
      setMeta(null);
      setError(reason.message || '生态网络加载失败');
      setStatus('error');
    });
    return () => controller.abort();
  }, [rootRepo, snapshotMonth, onSelectedNodeIdChange, onHoveredNodeIdChange]);


  const nodeById = useMemo(() => new Map(graphData.nodes.map((node) => [node.id, node])), [graphData.nodes]);
  const selected = selectedNodeId ? nodeById.get(selectedNodeId) || null : null;
  const hovered = hoveredNodeId ? nodeById.get(hoveredNodeId) || null : null;
  const currentSelectedId = selected?.id || null;

  useEffect(() => {
    onContributorsChange?.({
      month: snapshotMonth,
      nodes: status === 'ready' ? graphData.nodes.filter((node) => node.type === 'contributor') : [],
      status,
    });
  }, [graphData.nodes, snapshotMonth, status, onContributorsChange]);

  const neighborIdsFor = useCallback((node) => {
    if (!node) return new Set();
    const values = new Set([node.id]);
    for (const link of graphData.links) {
      const source = endpointId(link.source);
      const target = endpointId(link.target);
      if (source === node.id) values.add(target);
      if (target === node.id) values.add(source);
    }
    return values;
  }, [graphData.links]);

  const adjacentIds = useMemo(() => neighborIdsFor(selected), [selected, neighborIdsFor]);
  const hoveredAdjacentIds = useMemo(() => neighborIdsFor(hovered), [hovered, neighborIdsFor]);
  const interactionFocusIds = useMemo(
    () => selected ? adjacentIds : hovered ? hoveredAdjacentIds : new Set(),
    [selected, adjacentIds, hovered, hoveredAdjacentIds],
  );

  const visibleData = useMemo(() => {
    const allowed = new Set();
    const labelIds = new Set(
      [...graphData.nodes].filter((node) => node.type === 'contributor')
        .sort((a, b) => Number(b.contribution_score || 0) - Number(a.contribution_score || 0))
        .slice(0, 6).map((node) => node.id),
    );
    for (const node of graphData.nodes) {
      if (node.type === 'repository' || node.is_root) {
        allowed.add(node.id);
        continue;
      }
      const roleMatches = filters.role === 'all' || node.role === filters.role;
      const strengthMatches = Number(node.contribution_score || 0) >= filters.minimum;
      const labelMatches = !filters.labelsOnly || labelIds.has(node.id);
      if (roleMatches && strengthMatches && labelMatches) allowed.add(node.id);
    }
    const neighborhood = mode === 'path' && selected ? adjacentIds : null;
    const links = graphData.links.filter((link) => {
      const source = endpointId(link.source);
      const target = endpointId(link.target);
      return allowed.has(source) && allowed.has(target) && (!neighborhood || (neighborhood.has(source) && neighborhood.has(target)));
    });
    const connected = new Set(links.flatMap((link) => [endpointId(link.source), endpointId(link.target)]));
    const nodes = graphData.nodes.filter((node) => (!neighborhood || neighborhood.has(node.id)) && (node.is_root || (allowed.has(node.id) && (node.type === 'contributor' || connected.has(node.id)))));
    return { nodes, links };
  }, [graphData, filters, mode, selected, adjacentIds]);

  const contributionRange = useMemo(() => {
    const values = visibleData.nodes
      .filter((node) => node.type === 'contributor')
      .map((node) => Number(node.contribution_score || node.association_strength || 0))
      .filter((value) => Number.isFinite(value) && value > 0);
    return { min: values.length ? Math.min(...values) : 0, max: values.length ? Math.max(...values) : 1 };
  }, [visibleData.nodes]);
  const maxContribution = contributionRange.max;
  const maxLinkStrength = useMemo(
    () => Math.max(1, ...visibleData.links.map((link) => Number(link.weight ?? link.strength ?? link.contribution_score ?? link.association_strength ?? 0))),
    [visibleData.links],
  );

  const topContributorIds = useMemo(() => new Set(
    [...graphData.nodes]
      .filter((node) => node.type === 'contributor' && Number.isFinite(Number(node.contribution_score)))
      .sort((a, b) => Number(b.contribution_score) - Number(a.contribution_score))
      .slice(0, 6)
      .map((node) => node.id),
  ), [graphData.nodes]);

  const contributorIndexes = useMemo(() => new Map(
    visibleData.nodes
      .filter((node) => node.type === 'contributor')
      .sort((left, right) => Number(right.contribution_score || 0) - Number(left.contribution_score || 0) || String(left.id).localeCompare(String(right.id)))
      .map((node, index) => [node.id, index + 2]),
  ), [visibleData.nodes]);

  const annotationMap = useMemo(
    () => narrativeAnnotations(visibleData.nodes, viewportWidth, contributorIndexes),
    [visibleData.nodes, viewportWidth, contributorIndexes],
  );

  const reagraphData = useMemo(() => {
    const selectedContributorId = selected?.type === 'contributor' ? selected.id : null;
    const expandedContributorId = selectedContributorId && visibleData.nodes.some((node) => node.parent_id === selectedContributorId)
      ? selectedContributorId
      : null;
    const layoutNodes = mode === 'structure'
      ? prepareStructurePositions(visibleData.nodes, expandedContributorId, plotSize)
      : prepareNarrativePositions(visibleData.nodes, expandedContributorId, plotSize);
    const positionedNodes = snapshotHealth == null
      ? layoutNodes
      : layoutNodes.map((node) => node.is_root ? {
        ...node,
        health_score: snapshotHealth,
        health_status: undefined,
        healthStatus: undefined,
      } : node);
    const positionedNodeById = new Map(positionedNodes.map((node) => [node.id, node]));
    const focusNode = selected?.type === 'contributor' ? selected : hovered?.type === 'contributor' ? hovered : null;
    const focusCommunity = focusNode ? communityKey(focusNode) : null;
    const nodes = buildVisualNodes(positionedNodes, {
      minScore: contributionRange.min,
      maxScore: maxContribution,
      topContributorIds,
      contributorIndexes,
      annotations: annotationMap,
      selectedId: selectedContributorId,
      bundleExpandedRoutes: mode === 'structure',
      focusIds: interactionFocusIds,
      hoveredId: hovered?.id,
      selectionPulse,
      loadingNodeId,
      collapsingIds,
    });
    const zones = buildCommunityZones(positionedNodes, null, focusCommunity, { compact: mode === 'structure' });
    const edgeBundle = mode === 'structure'
      ? buildStructureEdges(visibleData.links, maxLinkStrength, {
        selectedContributorId,
        hoveredId: hovered?.id,
        nodeById: positionedNodeById,
        junctionPositions: getStructureJunctionPositions(plotSize),
      })
      : buildVisualEdges(visibleData.links, maxLinkStrength, {
        selectedIds: selectedContributorId ? adjacentIds : hovered ? hoveredAdjacentIds : new Set(),
        hoveredId: hovered?.id,
        nodeById: positionedNodeById,
        muted: mode === 'community',
      });
    return {
      nodes: [...zones, ...nodes, ...(edgeBundle.routingNodes || [])],
      edges: edgeBundle.edges,
      zones,
      positionedNodes,
      realNodeIds: nodes.map((node) => node.id),
    };
  }, [visibleData, mode, plotSize, snapshotHealth, contributionRange.min, maxContribution, maxLinkStrength, topContributorIds, contributorIndexes, annotationMap, selected, hovered, selectionPulse, loadingNodeId, collapsingIds, adjacentIds, hoveredAdjacentIds, interactionFocusIds]);
  const fitNodeIds = useMemo(() => visibleData.nodes.map((node) => node.id), [visibleData.nodes]);

  useEffect(() => {
    if (status !== 'ready' || !fitNodeIds.length) return undefined;
    const timer = window.setTimeout(() => {
      applyGraphCameraPreset(graphRef, fitNodeIds);
    }, 180);
    return () => window.clearTimeout(timer);
  }, [status, mode, snapshotMonth, filters.role, filters.minimum, filters.labelsOnly, layoutRevision, fitNodeIds]);
  useEffect(() => {
    if (status !== 'ready') {
      setCameraViewport(null);
      return undefined;
    }
    let controls = null;
    let frame = 0;
    const syncViewport = () => {
      window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(() => {
        const camera = controls?._camera;
        const viewportElement = graphViewportRef.current;
        if (!camera || !viewportElement) return;
        const target = controls.getTarget(new Vector3(), false);
        const aspect = Math.max(0.1, viewportElement.clientWidth / Math.max(1, viewportElement.clientHeight));
        let height;
        let width;
        if (camera.isOrthographicCamera) {
          width = Math.abs(camera.right - camera.left) / Math.max(0.001, camera.zoom || 1);
          height = Math.abs(camera.top - camera.bottom) / Math.max(0.001, camera.zoom || 1);
        } else {
          height = 2 * Math.max(1, controls.distance) * Math.tan(((camera.fov || 50) * Math.PI) / 360) / Math.max(0.001, camera.zoom || 1);
          width = height * aspect;
        }
        setCameraViewport({
          x: target.x - width / 2,
          y: target.y - height / 2,
          width,
          height,
        });
      });
    };
    const timer = window.setTimeout(() => {
      controls = graphRef.current?.getControls?.() || null;
      controls?.addEventListener?.('update', syncViewport);
      controls?.addEventListener?.('rest', syncViewport);
      syncViewport();
    }, 220);
    return () => {
      window.clearTimeout(timer);
      window.cancelAnimationFrame(frame);
      controls?.removeEventListener?.('update', syncViewport);
      controls?.removeEventListener?.('rest', syncViewport);
    };
  }, [status, rootRepo, snapshotMonth, layoutRevision]);

  const miniMapData = useMemo(() => {
    const zones = reagraphData.zones || [];
    const boundsPoints = [];
    const paths = [];
    for (const zone of zones) {
      const zoneX = Number(zone.data.x || 0);
      const zoneY = Number(zone.data.y || 0);
      const levels = zone.data.contours || [];
      const selectedLevels = levels.filter((_, index) => index === 0 || index === Math.floor((levels.length - 1) / 2) || index === levels.length - 1);
      for (const level of selectedLevels) {
        const commands = [];
        for (const segment of level.segments || []) {
          const start = [zoneX + segment[0][0], zoneY + segment[0][1]];
          const end = [zoneX + segment[1][0], zoneY + segment[1][1]];
          boundsPoints.push(start, end);
          commands.push('M ' + start[0] + ' ' + start[1] + ' L ' + end[0] + ' ' + end[1]);
        }
        if (commands.length) paths.push({ id: zone.id + ':' + level.ratio, d: commands.join(' '), color: zone.data.stroke });
      }
    }
    const roleColors = { core: '#42679A', active: '#34765F', new: '#B48332', inactive: '#66756E', risk: '#BD6047' };
    const nodePoints = (reagraphData.positionedNodes || []).flatMap((node) => {
      const x = Number(node.x ?? node.fx);
      const y = Number(node.y ?? node.fy);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return [];
      boundsPoints.push([x, y]);
      return [{ id: node.id, x, y, radius: node.is_root ? 5 : node.type === 'repository' ? 3.5 : 2.2, color: node.is_root ? '#172A25' : node.type === 'repository' ? '#B48332' : roleColors[node.role] || '#66756E' }];
    });
    const rect = createPlotRect(plotSize);
    const minX = Math.min(rect.x, ...boundsPoints.map((point) => point[0])) - 18;
    const maxX = Math.max(rect.x + rect.width, ...boundsPoints.map((point) => point[0])) + 18;
    const minY = Math.min(rect.y, ...boundsPoints.map((point) => point[1])) - 18;
    const maxY = Math.max(rect.y + rect.height, ...boundsPoints.map((point) => point[1])) + 18;
    return {
      paths,
      nodePoints,
      viewBox: minX + ' ' + minY + ' ' + (maxX - minX) + ' ' + (maxY - minY),
      viewport: cameraViewport || {
        x: minX + (maxX - minX) * 0.06,
        y: minY + (maxY - minY) * 0.08,
        width: (maxX - minX) * 0.88,
        height: (maxY - minY) * 0.84,
      },
    };
  }, [reagraphData.zones, reagraphData.positionedNodes, cameraViewport, plotSize]);
  const handleSelectionChange = useCallback((ids) => {
    const id = ids.find((value) => nodeById.has(value));
    onSelectedNodeIdChange?.(id || null);
  }, [nodeById, onSelectedNodeIdChange]);

  const selection = useSelection({
    ref: graphRef,
    nodes: reagraphData.nodes,
    edges: reagraphData.edges,
    selections: selected ? [selected.id] : [],
    actives: [],
    focusOnSelect: false,
    type: 'single',
    pathSelectionType: 'direct',
    pathHoverType: 'direct',
    onSelection: handleSelectionChange,
  });

  const clearSelections = selection.clearSelections;
  const setSelections = selection.setSelections;

  useEffect(() => {
    setSelections(currentSelectedId ? [currentSelectedId] : []);
  }, [currentSelectedId, setSelections]);

  const expandNode = useCallback(async (node) => {
    if (!node || node.type !== 'contributor' || expanding || !snapshotMonth) return;
    if (graphData.nodes.length >= GRAPH_LIMITS.nodes || graphData.links.length >= GRAPH_LIMITS.links) {
      setNotice('已达到 40 个节点或 60 条连线的性能上限，请先收起关联仓库。');
      return;
    }
    setExpanding(true);
    setLoadingNodeId(node.id);
    setNotice('');
    const point = snapshotMonth + '-01';
    try {
      const payload = await fetchEcosystemExpansion({
        nodeType: 'contributor',
        nodeId: node.id,
        start: point,
        end: point,
        limit: GRAPH_LIMITS.contributorRepos,
        depth: Number(node.depth || 0),
        rootRepo,
      });
      const bounded = {
        ...payload,
        nodes: (payload.nodes || []).slice(0, GRAPH_LIMITS.contributorRepos),
        links: (payload.links || []).slice(0, GRAPH_LIMITS.contributorRepos),
      };
      const oldRelatedIds = new Set(graphData.nodes.filter((item) => item.type === 'repository' && !item.is_root).map((item) => item.id));
      const prunedData = {
        nodes: graphData.nodes.filter((item) => !oldRelatedIds.has(item.id)),
        links: graphData.links.filter((link) => !oldRelatedIds.has(endpointId(link.source)) && !oldRelatedIds.has(endpointId(link.target))),
      };
      const merged = mergePayload(prunedData, bounded, node);
      merged.data.nodes = prepareNarrativePositions(merged.data.nodes, node.id);
      setGraphData(merged.data);
      setLayoutRevision((revision) => revision + 1);
      setHistory([{ parentId: node.id, nodeIds: merged.addedNodeIds, linkIds: merged.addedLinkIds }]);
      if (merged.addedNodeIds.length || merged.addedLinkIds.length) {
        window.setTimeout(() => graphRef.current?.centerGraph([node.id], { centerOnlyIfNodesNotInView: false }), 120);
      } else {
        setNotice(payload.meta?.status === 'depth_limit' ? '已达到最大递归深度。' : '该节点没有新的可展开关系。');
      }
      if (payload.meta?.truncated) setNotice('展开结果已按性能限制截断。');
    } catch (reason) {
      setNotice(reason.message || '节点展开失败');
    } finally {
      setExpanding(false);
      setLoadingNodeId(null);
    }
  }, [expanding, snapshotMonth, graphData, rootRepo]);

  const handleNodeClick = useCallback((node) => {
    const data = node.data || node;
    if (data.layoutOnly) return;
    if (data.type === 'community-zone') {
      window.clearTimeout(hoverTimerRef.current);
      clearSelections();
      onSelectedNodeIdChange?.(null);
      onHoveredNodeIdChange?.(null);
      return;
    }
    setSelectionPulse(Date.now());
    selection.onNodeClick(node);
    onSelectedNodeIdChange?.(data.id);
  }, [clearSelections, selection, onSelectedNodeIdChange, onHoveredNodeIdChange]);


  const collapseSelected = useCallback((nodeToCollapse = selected) => {
    if (!nodeToCollapse || nodeToCollapse.is_root) return;
    const removed = new Set();
    let changed = true;
    while (changed) {
      changed = false;
      for (const node of graphData.nodes) {
        if (node.parent_id === nodeToCollapse.id || removed.has(node.parent_id)) {
          if (!removed.has(node.id)) { removed.add(node.id); changed = true; }
        }
      }
    }
    if (!removed.size) return;
    setCollapsingIds(removed);
    window.setTimeout(() => {
      setGraphData((current) => ({
        nodes: prepareNarrativePositions(
          current.nodes.filter((node) => !removed.has(node.id)),
          nodeToCollapse.type === 'contributor' ? nodeToCollapse.id : null,
        ),
        links: current.links.filter((link) => !removed.has(endpointId(link.source)) && !removed.has(endpointId(link.target))),
      }));
      setLayoutRevision((revision) => revision + 1);
      setHistory((items) => items.filter((item) => item.parentId !== nodeToCollapse.id));
      setCollapsingIds(new Set());
    }, 380);
  }, [selected, graphData.nodes]);


  const changeMode = useCallback((nextMode) => {
    setMode(nextMode);
    setLocked(false);
    setGraphData((current) => ({ nodes: [...current.nodes], links: [...current.links] }));
  }, []);


  const reset = useCallback(() => {
    const restored = structuredClone(baseGraphRef.current);
    restored.nodes = prepareForcePositions(restored.nodes, new Map(restored.nodes.map((item) => [item.id, item])));
    setGraphData(restored);
    clearSelections();
    onSelectedNodeIdChange?.(null);
    onHoveredNodeIdChange?.(null);
    setHistory([]);
    setFilters(DEFAULT_FILTERS);
    setMode('structure');
    setLocked(false);
    setCollapsingIds(new Set());
    setLoadingNodeId(null);
    setCameraViewport(null);
    setLayoutRevision((revision) => revision + 1);
    setNotice('');
    window.setTimeout(() => applyGraphCameraPreset(graphRef, restored.nodes.map((node) => node.id)), 100);
  }, [clearSelections, onSelectedNodeIdChange, onHoveredNodeIdChange]);

  const fullscreen = () => panelRef.current?.closest('.ecosystem-panel')?.requestFullscreen();

  const searchSelect = useCallback((node) => {
    onSelectedNodeIdChange?.(node.id);
    setSelectionPulse(Date.now());
    graphRef.current?.centerGraph([node.id], { centerOnlyIfNodesNotInView: false });
  }, [onSelectedNodeIdChange]);

  const selectedExpanded = Boolean(selected && graphData.nodes.some((node) => node.parent_id === selected.id));
  const selectedPathIds = useMemo(() => {
    if (!selected || selected.type !== 'contributor') return [];
    const root = graphData.nodes.find((node) => node.is_root);
    const related = graphData.nodes.filter((node) => node.parent_id === selected.id).map((node) => node.id);
    return [root?.id, selected.id, ...related].filter(Boolean);
  }, [selected, graphData.nodes]);

  useEffect(() => {
    if (selectedPathIds.length < 3) return undefined;
    const timer = window.setTimeout(() => {
      graphRef.current?.fitNodesInView(selectedPathIds, { fitOnlyIfNodesNotInView: true, animated: true });
    }, 280);
    return () => window.clearTimeout(timer);
  }, [selectedPathIds]);

  useEffect(() => {
    if (!selected || selected.type !== 'contributor') return undefined;
    const timer = window.setTimeout(() => {
      graphRef.current?.centerGraph([selected.id], { centerOnlyIfNodesNotInView: false });
    }, 120);
    return () => window.clearTimeout(timer);
  }, [selected]);

  const changeMonth = useCallback((month) => {
    setSnapshotMonth(month);
    onMonthFocus?.(month);
  }, [onMonthFocus]);

  return <section className="gov-panel ecosystem-panel">
    <div className="ecosystem-heading">
      <div className="ecosystem-title-block">

        <h2>开源生态关系图</h2>
        <p>ECOSYSTEM RELATION ATLAS · {rootRepo || '—'} · {snapshotMonth || '—'}</p>
      </div>
      <EcosystemGraphControls
        nodes={graphData.nodes}
        onSearchSelect={searchSelect}
        filters={filters}
        onFilters={setFilters}
        mode={mode}
        onMode={changeMode}
        onFit={() => applyGraphCameraPreset(graphRef, reagraphData.realNodeIds)}
        onReset={reset}
        onFullscreen={fullscreen}
      />
      <EcosystemLegend />
    </div>
    <div className={'ecosystem-stage' + (selected ? ' has-drawer' : '')}>
      <div className="ecosystem-canvas" ref={panelRef}>
        <div className="ecosystem-coordinate-guide" aria-hidden="true">
          <div className="ecosystem-coordinate-top">{ATLAS_COLUMNS.map((label) => <span key={label}>{label}</span>)}</div>
          <div className="ecosystem-coordinate-left">{ATLAS_ROWS.map((label) => <span key={label}>{label}</span>)}</div>
        </div>
        {status === 'loading' && <div className="ecosystem-overlay"><span />正在加载 {snapshotMonth} 真实贡献关系…</div>}
        {status === 'error' && <div className="ecosystem-overlay error"><strong>网络加载失败</strong><p>{error}</p></div>}
        {status === 'empty' && <div className="ecosystem-overlay"><strong>暂无 OpenDigger 贡献者明细</strong><p>该仓库仍可使用月度健康分析，但不能生成真实生态关系。</p></div>}
        <div className="ecosystem-graph-viewport" ref={graphViewportRef}>
          {status === 'ready' && <GraphCanvas
            key={rootRepo + ':' + snapshotMonth + ':' + layoutRevision}
            ref={graphRef}
            nodes={reagraphData.nodes}
            edges={reagraphData.edges}
            layoutType="custom"
            layoutOverrides={CUSTOM_LAYOUT_OVERRIDES}
            cameraMode="pan"
            animated
            theme={lightTechnologyTheme}
            labelType="none"
            edgeInterpolation="curved"
            edgeArrowPosition="none"
            aggregateEdges={false}
            selections={selection.selections}
            actives={selection.actives}
            draggable={mode !== 'structure' && !locked}
            minZoom={0.55}
            maxZoom={4}
            glOptions={{ preserveDrawingBuffer: true, alpha: true, antialias: true }}
            renderNode={(props) => <FlatReagraphNode {...props} />}
            onNodeClick={handleNodeClick}
            onNodePointerOver={(node) => {
              if (node.data.layoutOnly || node.data.type === 'community-zone') return;
              selection.onNodePointerOver(node);
              window.clearTimeout(hoverTimerRef.current);
              hoverTimerRef.current = window.setTimeout(() => onHoveredNodeIdChange?.(node.data.id), 120);
            }}
            onNodePointerOut={(node) => {
              if (node.data.layoutOnly || node.data.type === 'community-zone') return;
              selection.onNodePointerOut(node);
              window.clearTimeout(hoverTimerRef.current);
              hoverTimerRef.current = window.setTimeout(() => onHoveredNodeIdChange?.(null), 120);
            }}
            onNodeDragged={(node) => {
              setGraphData((current) => ({
                nodes: current.nodes.map((item) => item.id === node.id ? {
                  ...item,
                  x: node.position.x,
                  y: node.position.y,
                  z: Math.max(-28, Math.min(28, node.position.z)),
                  userPinned: true,
                } : item),
                links: current.links,
              }));
            }}
            onCanvasClick={(event) => {
              window.clearTimeout(hoverTimerRef.current);
              selection.onCanvasClick(event);
              onHoveredNodeIdChange?.(null);
            }}
          />}
        </div>
        <EcosystemTooltip node={hovered} />
        {status === 'ready' && <NetworkEncodingLegend />}
        {status === 'ready' && <div className="ecosystem-mini-map" aria-label="社区分布小地图">
          <div className="mini-map-field"><svg viewBox={miniMapData.viewBox} preserveAspectRatio="xMidYMid meet" aria-hidden="true">
            {miniMapData.paths.map((path) => <path key={path.id} d={path.d} stroke={path.color} />)}
            {miniMapData.nodePoints.map((point) => <circle key={point.id} cx={point.x} cy={point.y} r={point.radius} fill={point.color} />)}
            <rect className="mini-map-viewport" {...miniMapData.viewport} />
          </svg></div>
          <small>ATLAS OVERVIEW · LIVE VIEW</small>
        </div>}
        <div className="ecosystem-timeline-dock">
          <EcosystemTimeline months={healthMonths} value={snapshotMonth} onChange={changeMonth} disabled={status === 'loading'} events={meta?.events || []} />
        </div>
      </div>
      {selected && <EcosystemNodePanel node={selected} month={snapshotMonth} expanded={selectedExpanded} onExpand={expandNode} onCollapse={collapseSelected} onSetRoot={onSetRoot} expanding={expanding} onClose={() => {
        window.clearTimeout(hoverTimerRef.current);
        onSelectedNodeIdChange?.(null);
        onHoveredNodeIdChange?.(null);
      }} />}
    </div>
    {notice && <div className="ecosystem-notice">{notice}</div>}
  </section>;
}










