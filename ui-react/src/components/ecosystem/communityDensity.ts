export type DensitySample = {
  x: number;
  y: number;
  weight?: number;
};

export type DensitySegment = [[number, number], [number, number]];

export type DensityContourLevel = {
  ratio: number;
  opacity: number;
  lineWidth: number;
  segments: DensitySegment[];
};

export type DensityContourResult = {
  bounds: { minX: number; minY: number; maxX: number; maxY: number };
  bandwidth: number;
  levels: DensityContourLevel[];
};

export type DensityContourOptions = {
  bandwidth?: number;
  thresholdCount?: number;
};

const GRID_COLUMNS = 56;
const GRID_ROWS = 44;

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function interpolate(a: number, b: number, threshold: number) {
  if (Math.abs(b - a) < 1e-8) return 0.5;
  return clamp((threshold - a) / (b - a), 0, 1);
}

function cellSegments(
  x: number,
  y: number,
  width: number,
  height: number,
  values: [number, number, number, number],
  threshold: number,
): DensitySegment[] {
  const [topLeft, topRight, bottomRight, bottomLeft] = values;
  const mask = (topLeft >= threshold ? 8 : 0)
    | (topRight >= threshold ? 4 : 0)
    | (bottomRight >= threshold ? 2 : 0)
    | (bottomLeft >= threshold ? 1 : 0);
  if (mask === 0 || mask === 15) return [];

  const edge = {
    top: [x + width * interpolate(topLeft, topRight, threshold), y] as [number, number],
    right: [x + width, y + height * interpolate(topRight, bottomRight, threshold)] as [number, number],
    bottom: [x + width * interpolate(bottomLeft, bottomRight, threshold), y + height] as [number, number],
    left: [x, y + height * interpolate(topLeft, bottomLeft, threshold)] as [number, number],
  };
  const pairs: Record<number, Array<[keyof typeof edge, keyof typeof edge]>> = {
    1: [['left', 'bottom']],
    2: [['bottom', 'right']],
    3: [['left', 'right']],
    4: [['top', 'right']],
    5: [['top', 'left'], ['bottom', 'right']],
    6: [['top', 'bottom']],
    7: [['top', 'left']],
    8: [['left', 'top']],
    9: [['top', 'bottom']],
    10: [['left', 'bottom'], ['top', 'right']],
    11: [['top', 'right']],
    12: [['left', 'right']],
    13: [['bottom', 'right']],
    14: [['left', 'bottom']],
  };
  return (pairs[mask] || []).map(([start, end]) => [edge[start], edge[end]]);
}

function ratiosFor(count: number) {
  return Array.from({ length: count }, (_, index) => {
    const progress = count <= 1 ? 0 : index / (count - 1);
    return 0.08 + progress * 0.7;
  });
}

export function buildDensityContours(samples: DensitySample[], options: DensityContourOptions = {}): DensityContourResult {
  const safeSamples = samples.filter((sample) => Number.isFinite(sample.x) && Number.isFinite(sample.y));
  if (!safeSamples.length) {
    return {
      bounds: { minX: 0, minY: 0, maxX: 0, maxY: 0 },
      bandwidth: clamp(Number(options.bandwidth) || 34, 28, 52),
      levels: [],
    };
  }

  const minSampleX = Math.min(...safeSamples.map((sample) => sample.x));
  const maxSampleX = Math.max(...safeSamples.map((sample) => sample.x));
  const minSampleY = Math.min(...safeSamples.map((sample) => sample.y));
  const maxSampleY = Math.max(...safeSamples.map((sample) => sample.y));
  const bandwidth = clamp(Number(options.bandwidth) || 34, 28, 52);
  const padding = bandwidth * 2.35;
  const bounds = {
    minX: minSampleX - padding,
    minY: minSampleY - padding,
    maxX: maxSampleX + padding,
    maxY: maxSampleY + padding,
  };
  const cellWidth = (bounds.maxX - bounds.minX) / (GRID_COLUMNS - 1);
  const cellHeight = (bounds.maxY - bounds.minY) / (GRID_ROWS - 1);
  const maxWeight = Math.max(1, ...safeSamples.map((sample) => Math.max(0, Number(sample.weight) || 0)));
  const grid = Array.from({ length: GRID_ROWS }, (_, row) => Array.from({ length: GRID_COLUMNS }, (_, column) => {
    const pointX = bounds.minX + column * cellWidth;
    const pointY = bounds.minY + row * cellHeight;
    return safeSamples.reduce((density, sample) => {
      const weight = 0.55 + 0.45 * Math.sqrt(Math.max(0, Number(sample.weight) || 0) / maxWeight);
      const distanceSquared = (pointX - sample.x) ** 2 + (pointY - sample.y) ** 2;
      return density + weight * Math.exp(-distanceSquared / (2 * bandwidth ** 2));
    }, 0);
  }));
  const peak = Math.max(...grid.flat());
  const ratios = ratiosFor(clamp(Math.round(Number(options.thresholdCount) || 8), 7, 11));

  const levels = ratios.map((ratio, levelIndex) => {
    const threshold = peak * ratio;
    const segments: DensitySegment[] = [];
    for (let row = 0; row < GRID_ROWS - 1; row += 1) {
      for (let column = 0; column < GRID_COLUMNS - 1; column += 1) {
        segments.push(...cellSegments(
          bounds.minX + column * cellWidth,
          bounds.minY + row * cellHeight,
          cellWidth,
          cellHeight,
          [grid[row][column], grid[row][column + 1], grid[row + 1][column + 1], grid[row + 1][column]],
          threshold,
        ));
      }
    }
    const progress = ratios.length <= 1 ? 0 : levelIndex / (ratios.length - 1);
    return {
      ratio,
      opacity: 0.18 + progress * 0.18,
      lineWidth: 0.75 + progress * 0.45,
      segments,
    };
  });

  return { bounds, bandwidth, levels };
}
