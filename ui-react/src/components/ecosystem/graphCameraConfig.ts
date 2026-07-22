export const GRAPH_CAMERA = Object.freeze({ transition: true });

export function applyGraphCameraPreset(graphRef, nodeIds = []) {
  const visibleNodeIds = Array.isArray(nodeIds) ? nodeIds.filter(Boolean) : [];
  const apply = () => {
    if (!graphRef.current) return;
    if (visibleNodeIds.length) {
      graphRef.current.fitNodesInView(visibleNodeIds, { animated: true, fitOnlyIfNodesNotInView: false });
      return;
    }
    graphRef.current.fitNodesInView();
  };
  apply();
  window.requestAnimationFrame(apply);
  window.setTimeout(apply, 420);
  window.setTimeout(apply, 1400);
}
