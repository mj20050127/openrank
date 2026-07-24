import type { ECharts } from 'echarts';
import { ATLAS_THEME, HEALTH_SCALE } from './metricConfig.ts';

export const atlasTooltip = {
  backgroundColor: ATLAS_THEME.tooltip,
  borderColor: ATLAS_THEME.ink,
  borderWidth: 1,
  padding: [9, 11],
  textStyle: {
    color: ATLAS_THEME.text,
    fontSize: 12,
    fontFamily: '"IBM Plex Mono", "SFMono-Regular", Consolas, monospace',
  },
  extraCssText: 'border-radius:2px;box-shadow:0 6px 14px rgba(23,59,50,.12);',
};

export function formatNumber(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(Number(value))) return '暂无数据';
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: digits }).format(Number(value));
}

export function healthColor(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return ATLAS_THEME.neutral;
  const normalized = Math.max(-1, Math.min(1, value));
  const position = (normalized + 1) * 2;
  const lower = Math.min(3, Math.floor(position));
  const ratio = position - lower;
  const parse = (color: string) => [1, 3, 5].map((index) => Number.parseInt(color.slice(index, index + 2), 16));
  const left = parse(HEALTH_SCALE[lower]);
  const right = parse(HEALTH_SCALE[lower + 1]);
  const channel = (index: number) => Math.round(left[index] + (right[index] - left[index]) * ratio).toString(16).padStart(2, '0');
  return `#${channel(0)}${channel(1)}${channel(2)}`;
}

export function exportChartPng(instance: ECharts | null, title: string, source: string, period: string): void {
  if (!instance) return;
  instance.setOption({
    graphic: [
      {
        id: 'export-title',
        type: 'text',
        left: 18,
        top: 8,
        silent: true,
        style: { text: title, fill: ATLAS_THEME.ink, font: '600 16px Georgia, serif' },
      },
      {
        id: 'export-source',
        type: 'text',
        right: 18,
        bottom: 5,
        silent: true,
        style: { text: `数据来源：${source}　观察周期：${period}`, fill: ATLAS_THEME.muted, font: '10px Consolas, monospace' },
      },
    ],
  });
  const href = instance.getDataURL({ pixelRatio: 2, backgroundColor: ATLAS_THEME.panel });
  instance.setOption({ graphic: [
    { id: 'export-title', $action: 'remove' },
    { id: 'export-source', $action: 'remove' },
  ] } as never);
  const link = document.createElement('a');
  link.href = href;
  link.download = `${title}.png`;
  link.click();
}
