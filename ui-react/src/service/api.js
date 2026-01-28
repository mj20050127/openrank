const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

async function handleJsonResponse(res) {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function postChat(payload) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleJsonResponse(res);
}

export async function postAgentRun(payload) {
  const res = await fetch(`${API_BASE}/agent/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleJsonResponse(res);
}

export async function fetchTrend(repo, metric = 'openrank') {
  const url = new URL(`${API_BASE}/api/metrics/trend`);
  url.searchParams.set('repo', repo);
  url.searchParams.set('metric', metric);
  const res = await fetch(url.toString());
  return handleJsonResponse(res);
}

export async function bootstrapHealth(repoFullName) {
  const url = new URL(`${API_BASE}/api/health/bootstrap`);
  url.searchParams.set('repo_full_name', repoFullName);
  url.searchParams.set('metrics', 'all');
  const res = await fetch(url.toString(), { method: 'POST' });
  return handleJsonResponse(res);
}

export async function refreshTodayHealth() {
  const res = await fetch(`${API_BASE}/api/health/refresh-today`, {
    method: 'POST',
  });
  return handleJsonResponse(res);
}

export async function refreshHealth(repoFullName, dt) {
  const url = new URL(`${API_BASE}/api/health/refresh`);
  url.searchParams.set('repo_full_name', repoFullName);
  if (dt) url.searchParams.set('dt', dt);
  const res = await fetch(url.toString(), { method: 'POST' });
  return handleJsonResponse(res);
}

export async function fetchLatestHealthOverview(repoFullName) {
  const url = new URL(`${API_BASE}/api/health/overview/latest`);
  url.searchParams.set('repo_full_name', repoFullName);
  const res = await fetch(url.toString());
  return handleJsonResponse(res);
}

export async function fetchDataEaseDashboardUrl(repoFullName) {
  const url = new URL(`${API_BASE}/api/dataease/dashboard-url`);
  url.searchParams.set('repo', repoFullName);
  const res = await fetch(url.toString());
  return handleJsonResponse(res);
}

export async function postNewcomerPlan(payload) {
  const res = await fetch(`${API_BASE}/api/newcomer/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleJsonResponse(res);
}

export async function fetchNewcomerIssues(repoFullName, readiness = 60) {
  const url = new URL(`${API_BASE}/api/newcomer/issues`);
  url.searchParams.set('repo_full_name', repoFullName);
  url.searchParams.set('readiness', readiness);
  const res = await fetch(url.toString());
  return handleJsonResponse(res);
}

export async function postTaskBundle(payload) {
  const res = await fetch(`${API_BASE}/api/newcomer/task_bundle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleJsonResponse(res);
}

export async function fetchTrendSeries({ repo, metrics, start, end }) {
  const url = new URL(`${API_BASE}/api/trends/series`);
  url.searchParams.set('repo', repo);
  (metrics || []).forEach((m) => url.searchParams.append('metrics', m));
  if (start) url.searchParams.set('start', start);
  if (end) url.searchParams.set('end', end);
  const res = await fetch(url.toString());
  return handleJsonResponse(res);
}

export async function fetchTrendDerived({ repo, metrics, start, end, slope_window = 7, response_hours = 48 }) {
  const url = new URL(`${API_BASE}/api/trends/derived`);
  url.searchParams.set('repo', repo);
  (metrics || []).forEach((m) => url.searchParams.append('metrics', m));
  url.searchParams.set('slope_window', slope_window);
  url.searchParams.set('response_hours', response_hours);
  if (start) url.searchParams.set('start', start);
  if (end) url.searchParams.set('end', end);
  const res = await fetch(url.toString());
  return handleJsonResponse(res);
}

export async function postTrendReport(payload) {
  const res = await fetch(`${API_BASE}/api/trends/report`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  return handleJsonResponse(res);
}

export async function fetchCompositeTrends({ repo, start, end, window_days = 180 }) {
  const url = new URL(`${API_BASE}/api/trends/composite`);
  url.searchParams.set('repo', repo);
  if (start) url.searchParams.set('start', start);
  if (end) url.searchParams.set('end', end);
  if (window_days) url.searchParams.set('window_days', window_days);
  const res = await fetch(url.toString());
  return handleJsonResponse(res);
}

export async function fetchRiskViability(repo, start, end) {
  const url = new URL(`${API_BASE}/risk_viability`);
  url.searchParams.set('repo', repo);
  if (start) url.searchParams.set('start', start);
  if (end) url.searchParams.set('end', end);
  const res = await fetch(url.toString());
  return handleJsonResponse(res);
}

// AI报告相关API调用
export async function fetchHealthReport(repoFullName, timeWindowDays = 30) {
  const res = await fetch(`${API_BASE}/ai/report/health`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_full_name: repoFullName, time_window_days: timeWindowDays }),
  });
  return handleJsonResponse(res);
}

export async function fetchNewcomerReport(domain, stack, timePerWeek, keywords = '', topN = 3) {
  const res = await fetch(`${API_BASE}/ai/report/newcomer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      domain, 
      stack, 
      time_per_week: timePerWeek, 
      keywords, 
      top_n: topN 
    }),
  });
  return handleJsonResponse(res);
}

export async function fetchTrendReport(repoFullName, timeWindowDays = 180, metrics = ['activity', 'first_response', 'bus_factor', 'scorecard']) {
  const res = await fetch(`${API_BASE}/ai/report/trend`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      repo_full_name: repoFullName, 
      time_window_days: timeWindowDays, 
      metrics 
    }),
  });
  return handleJsonResponse(res);
}
