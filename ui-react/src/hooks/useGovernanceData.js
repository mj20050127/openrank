import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  fetchCurrentHealth,
  fetchCurrentHealthJob,
  fetchHealthOverviewHistory,
  fetchHistoryCoverage,
  fetchMonthlyHistory,
  refreshCurrentHealth,
} from '../service/api';
import { REQUIRED_HISTORY_METRICS } from '../components/community-health/metricConfig.ts';

function adaptHistoryRecord(record, scoreRecord) {
  return {
    ...record,
    dt: record.metric_month,
    scores: scoreRecord ? {
      vitality: scoreRecord.score_vitality ?? null,
      responsiveness: scoreRecord.score_responsiveness ?? null,
      resilience: scoreRecord.score_resilience ?? scoreRecord.score_community ?? null,
      governance: scoreRecord.score_governance ?? null,
      security: scoreRecord.score_security ?? null,
      health: scoreRecord.score_comprehensive ?? scoreRecord.score_community ?? null,
    } : {},
    metrics: record.metrics || {},
  };
}

function adaptCurrent(payload) {
  if (!payload) return null;
  return {
    ...payload,
    dt: payload.observed_at,
    scoreType: 'current',
    data_completeness: payload.completeness,
    scores: {
      health: payload.scores?.comprehensive,
      vitality: payload.scores?.vitality,
      responsiveness: payload.scores?.responsiveness,
      resilience: payload.scores?.resilience,
      governance: payload.scores?.governance,
      security: payload.scores?.security,
      comprehensive: payload.scores?.comprehensive,
    },
  };
}

function wait(ms) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export function useGovernanceData(repo, range) {
  const [payload, setPayload] = useState(null);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!repo) return;
    setStatus('loading');
    setError('');
    const [historyResult, coverageResult, currentResult, monthlyScoresResult] = await Promise.allSettled([
      fetchMonthlyHistory({ repoFullName: repo, months: range, metrics: REQUIRED_HISTORY_METRICS }),
      fetchHistoryCoverage(repo),
      fetchCurrentHealth(repo),
      fetchHealthOverviewHistory({ repoFullName: repo, months: range }),
    ]);
    if (historyResult.status === 'rejected') {
      setPayload(null);
      setError(historyResult.reason?.message || '无法加载仓库月度历史');
      setStatus('error');
      return;
    }
    setPayload({
      history: historyResult.value,
      coverage: coverageResult.status === 'fulfilled' ? coverageResult.value : null,
      current: currentResult.status === 'fulfilled' ? currentResult.value : null,
      monthlyScores: monthlyScoresResult.status === 'fulfilled' ? monthlyScoresResult.value : null,
      currentError: currentResult.status === 'rejected' ? currentResult.reason?.message : '',
    });
    setStatus('ready');
  }, [repo, range]);

  useEffect(() => {
    void Promise.resolve().then(load);
  }, [load]);

  const records = useMemo(() => {
    const scoresByMonth = new Map((payload?.monthlyScores?.records || []).map((record) => [String(record.metric_month).slice(0, 7), record]));
    return (payload?.history?.records || []).map((record) => adaptHistoryRecord(
      record,
      scoresByMonth.get(String(record.metric_month).slice(0, 7)),
    ));
  }, [payload]);
  const current = useMemo(() => adaptCurrent(payload?.current), [payload]);

  const refresh = useCallback(async () => {
    const job = await refreshCurrentHealth(repo, true);
    for (let attempt = 0; attempt < 90; attempt += 1) {
      await wait(2000);
      const state = await fetchCurrentHealthJob(job.job_id);
      if (state.status === 'succeeded') {
        await load();
        return state;
      }
      if (state.status === 'failed') {
        throw new Error(state.error || '当前体检失败');
      }
    }
    throw new Error('当前体检仍在运行，请稍后重试');
  }, [repo, load]);

  return {
    payload: payload?.history,
    records,
    current,
    coverage: payload?.coverage,
    currentError: payload?.currentError,
    status,
    error,
    reload: load,
    refresh,
  };
}