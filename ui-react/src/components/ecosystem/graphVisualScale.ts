export const VISUAL_SIZE_RANGE = Object.freeze({
  contributor: [15, 32],
  rootRepository: [52, 52],
  repository: [15, 19],
});

export function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

export function logScore(score, maxScore) {
  const value = Number(score);
  const maximum = Number(maxScore);
  if (!Number.isFinite(value) || value <= 0 || !Number.isFinite(maximum) || maximum <= 0) return 0;
  return clamp(Math.log1p(value) / Math.log1p(Math.max(value, maximum)), 0, 1);
}

export function contributionStrength(score, minScore, maxScore) {
  const value = Number(score);
  if (!Number.isFinite(value) || value <= 0) return 0;
  const minRoot = Math.sqrt(Math.max(0, Number(minScore) || 0));
  const maxRoot = Math.sqrt(Math.max(0, Number(maxScore) || 0));
  if (maxRoot === minRoot) return 0.5;
  return clamp((Math.sqrt(value) - minRoot) / Math.max(0.0001, maxRoot - minRoot), 0, 1);
}

export function contributorVisualSize(score, minScore, maxScore) {
  const [min, max] = VISUAL_SIZE_RANGE.contributor;
  const value = Number(score);
  if (!Number.isFinite(value) || value <= 0) return min;
  const normalized = contributionStrength(value, minScore, maxScore);
  return Number((min + (max - min) * normalized).toFixed(2));
}

export function repositoryVisualSize(score, isRoot = false) {
  if (isRoot) return VISUAL_SIZE_RANGE.rootRepository[0];
  const value = Number(score);
  const normalized = Number.isFinite(value) && value > 0 ? clamp(Math.log10(value + 1) / 5, 0, 1) : 0;
  const [min, max] = VISUAL_SIZE_RANGE.repository;
  return Number((min + (max - min) * normalized).toFixed(2));
}

export function edgeVisualSize(weight, maxWeight, active = false) {
  const value = Number(weight);
  const maximum = Number(maxWeight);
  const normalized = Number.isFinite(value) && value > 0 && maximum > 0
    ? clamp(Math.sqrt(value / Math.max(value, maximum)), 0, 1)
    : 0;
  const base = 0.75 + normalized * 2.15;
  return Number(clamp(active ? base * 1.25 : base, 0.75, 3.63).toFixed(2));
}

export function edgeVisualOpacity(weight, maxWeight, active = false) {
  if (active) return 0.88;
  const value = Number(weight);
  const maximum = Number(maxWeight);
  const normalized = Number.isFinite(value) && value > 0 && maximum > 0
    ? clamp(Math.sqrt(value / Math.max(value, maximum)), 0, 1)
    : 0;
  return Number((0.15 + normalized * 0.43).toFixed(3));
}
