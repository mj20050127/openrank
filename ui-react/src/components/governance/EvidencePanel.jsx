import { DIMENSIONS, METRICS, valueFor } from '../../utils/governanceConfig';

function format(value, key) {
  if (value == null || Number.isNaN(Number(value))) return '暂无数据';
  const unit = METRICS[key]?.unit || '';
  return String(new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)) + unit;
}

function riskLevel(value, key) {
  if (value == null) return { label: '数据缺失', tone: 'neutral' };
  const config = METRICS[key] || {};
  if (config.threshold == null || config.betterWhen === 'neutral') return { label: '观察中', tone: 'neutral' };
  const violated = config.betterWhen === 'higher' ? value < config.threshold : value > config.threshold;
  return violated ? { label: '需要关注', tone: 'risk' } : { label: '处于安全区', tone: 'good' };
}

function actionFor(dimension, metric, value) {
  const config = METRICS[metric] || {};
  const risk = riskLevel(value, metric);
  if (risk.tone === 'risk') {
    return {
      priority: metric.includes('response') || metric.includes('resolution') ? 'P0' : 'P1',
      title: metric.includes('response') || metric.includes('resolution') ? '建立响应 SLA 与轮值机制' : '降低关键治理风险',
      detail: '将「' + config.label + '」调整至 ' + (config.betterWhen === 'lower' ? '不高于 ' : '不低于 ') + config.threshold + (config.unit || '') + '。',
      period: metric.includes('response') ? '本周' : '本周期',
    };
  }
  return {
    priority: 'P2',
    title: '持续监测' + (DIMENSIONS[dimension]?.label || '健康') + '维度',
    detail: '保持「' + config.label + '」的当前改善趋势，并在下个观测周期复核。',
    period: '下个观测周期',
  };
}

export function EvidencePanel({ records, dimension, evidence }) {
  const latest = records.at(-1);
  const primary = evidence?.metric || DIMENSIONS[dimension]?.metrics?.[0] || 'score_health';
  const value = evidence?.value ?? valueFor(latest, primary);
  const previous = records.at(-2);
  const previousValue = valueFor(previous, primary);
  const change = value != null && previousValue != null ? value - previousValue : null;
  const risk = riskLevel(value, primary);
  const action = actionFor(dimension, primary, value);

  return <aside className="evidence-panel">
    <div className="section-heading"><div><span className="eyebrow">治理证据</span><h2>从异常到行动</h2></div><span className={'risk-pill ' + risk.tone}>{risk.label}</span></div>
    <div className="evidence-focus"><span>当前焦点</span><strong>{METRICS[primary]?.label || primary}</strong><p>{DIMENSIONS[dimension]?.description || '综合健康分由五维模型加权计算。'}</p></div>
    <dl className="evidence-list">
      <div><dt>数据日期</dt><dd>{evidence?.record?.dt || latest?.dt || '暂无数据'}</dd></div>
      <div><dt>当前值</dt><dd>{format(value, primary)}</dd></div>
      <div><dt>周期变化</dt><dd>{change == null ? '暂无同期数据' : (change > 0 ? '+' : '') + format(change, primary)}</dd></div>
      <div><dt>数据来源</dt><dd>{METRICS[primary]?.source || '健康评分模型'}</dd></div>
      <div><dt>治理阈值</dt><dd>{METRICS[primary]?.threshold == null ? '未设阈值' : String(METRICS[primary].threshold) + (METRICS[primary].unit || '')}</dd></div>
    </dl>
    <div className="ai-brief"><span>AI 简短解释</span><p>{risk.tone === 'risk' ? '该指标已触及治理阈值，可能拉低' + (DIMENSIONS[dimension]?.label || '整体健康') + '。建议先确认异常月份是否伴随协作积压或贡献者集中。' : '当前没有触发硬性阈值。请结合趋势图中的异常标记，关注相邻周期是否出现持续变化。'}</p></div>
    <div className="action-card"><div><span className={'priority ' + action.priority.toLowerCase()}>{action.priority}</span><strong>{action.title}</strong></div><p>{action.detail}</p><small>建议周期：{action.period} · 预期影响：{DIMENSIONS[dimension]?.label || '综合健康'}</small></div>
  </aside>;
}