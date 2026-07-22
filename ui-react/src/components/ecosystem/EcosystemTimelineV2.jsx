import { useEffect, useMemo, useState } from 'react';

const EVENT_META = {
  release: { label: '版本发布', symbol: '●' },
  security: { label: '安全公告', symbol: '◇' },
  governance: { label: '治理变更', symbol: '◆' },
  contributor: { label: '成员变化', symbol: '▲' },
  other: { label: '生态事件', symbol: '■' },
};

function eventMonth(event) {
  const value = event?.month || event?.date || event?.occurred_at || event?.created_at || event?.dt;
  return value ? String(value).slice(0, 7) : null;
}

function eventKind(event) {
  const raw = String(event?.type || event?.event_type || event?.kind || '').toLowerCase();
  if (raw.includes('release') || raw.includes('version') || raw.includes('publish')) return 'release';
  if (raw.includes('security') || raw.includes('vulnerability') || raw.includes('cve')) return 'security';
  if (raw.includes('govern') || raw.includes('policy') || raw.includes('maintainer')) return 'governance';
  if (raw.includes('contributor') || raw.includes('member') || raw.includes('people')) return 'contributor';
  return 'other';
}

function eventLabel(event) {
  return String(event?.label || event?.title || event?.summary || event?.name || EVENT_META[eventKind(event)].label);
}

function monthLabel(month, index, months) {
  if (!month) return '—';
  if (index === 0 || index === months.length - 1 || month.endsWith('-01')) return month;
  return month.slice(5);
}

export default function EcosystemTimelineV2({ months, value, onChange, disabled, events = [] }) {
  const [playing, setPlaying] = useState(false);
  const index = Math.max(0, months.indexOf(value));
  const normalizedEvents = useMemo(() => events
    .map((event, eventIndex) => ({
      ...event,
      id: event.id || event.event_id || eventIndex,
      month: eventMonth(event),
      kind: eventKind(event),
      label: eventLabel(event),
    }))
    .filter((event) => event.month && months.includes(event.month)), [events, months]);
  const eventsByMonth = useMemo(() => {
    const grouped = new Map();
    for (const event of normalizedEvents) {
      if (!grouped.has(event.month)) grouped.set(event.month, []);
      grouped.get(event.month).push(event);
    }
    return grouped;
  }, [normalizedEvents]);
  const visibleKinds = useMemo(() => [...new Set(normalizedEvents.map((event) => event.kind))], [normalizedEvents]);

  useEffect(() => {
    if (!playing || disabled || months.length < 2) return undefined;
    const timer = window.setTimeout(() => onChange(months[index >= months.length - 1 ? 0 : index + 1]), 1350);
    return () => window.clearTimeout(timer);
  }, [playing, disabled, months, index, onChange]);

  const step = (offset) => {
    if (!months.length || disabled) return;
    onChange(months[Math.max(0, Math.min(months.length - 1, index + offset))]);
  };

  return <div className="ecosystem-timeline ecosystem-timeline-v2">
    <div className="timeline-caption">
      <strong>生态事件时间线</strong>
      <span>ECOSYSTEM TIMELINE</span>
      {visibleKinds.length > 0 && <div className="timeline-event-legend">{visibleKinds.map((kind) => <span key={kind} className={kind}>{EVENT_META[kind].symbol} {EVENT_META[kind].label}</span>)}</div>}
    </div>
    <div className="timeline-navigation">
      <button type="button" className="timeline-play" onClick={() => setPlaying((current) => !current)} disabled={!months.length} aria-label={playing ? '暂停时间轴' : '播放时间轴'}>{playing ? 'Ⅱ' : '▶'}</button>
      <button type="button" className="timeline-step" onClick={() => step(-1)} disabled={disabled || index <= 0} aria-label="上一个月">‹</button>
    </div>
    <div className="timeline-month-grid" style={{ '--timeline-month-count': Math.max(1, months.length) }}>
      {months.map((month, monthIndex) => {
        const monthEvents = eventsByMonth.get(month) || [];
        return <button type="button" key={month} className={month === value ? 'active' : ''} onClick={() => !disabled && onChange(month)} disabled={disabled} aria-label={`${month}${monthEvents.length ? `，${monthEvents.length} 个生态事件` : ''}`}>
          <i className="timeline-tick" />
          <span className="timeline-event-stack">{monthEvents.slice(0, 3).map((event) => <i key={event.id} className={event.kind} title={event.label}>{EVENT_META[event.kind].symbol}</i>)}</span>
          <strong>{monthLabel(month, monthIndex, months)}</strong>
        </button>;
      })}
    </div>
    <button type="button" className="timeline-step" onClick={() => step(1)} disabled={disabled || index >= months.length - 1} aria-label="下一个月">›</button>
  </div>;
}
