const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

async function handleJsonResponse(res) {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function fetchTrend(repo, metric = 'openrank') {
  const url = new URL(`${API_BASE}/api/metrics/trend`);
  url.searchParams.set('repo', repo);
  url.searchParams.set('metric', metric);
  const res = await fetch(url.toString());
  return handleJsonResponse(res);
}

export async function bootstrapHealth(repoFullName) {
  return importRepository(repoFullName);
}


export async function refreshHealth(repoFullName) {
  return refreshMonthlyRepository(repoFullName);
}

export async function fetchLatestHealthOverview(repoFullName) {
  const url = new URL(`${API_BASE}/api/health/overview/latest`);
  url.searchParams.set('repo_full_name', repoFullName);
  const res = await fetch(url.toString());
  return handleJsonResponse(res);
}
export async function fetchHealthOverviewHistory({ repoFullName, months = '24' }) {
  const url = new URL(`${API_BASE}/api/health/monthly/trend`);
  url.searchParams.set('repo', repoFullName);
  url.searchParams.set('months', months);
  const res = await fetch(url.toString());
  return handleJsonResponse(res);
}

export async function fetchCurrentHealth(repoFullName) {
  const url = new URL(`${API_BASE}/api/health/current`);
  url.searchParams.set('repo', repoFullName);
  const res = await fetch(url.toString());
  return handleJsonResponse(res);
}

export async function refreshCurrentHealth(repoFullName, force = true) {
  const res = await fetch(`${API_BASE}/api/health/current/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo: repoFullName, force }),
  });
  return handleJsonResponse(res);
}

export async function fetchCurrentHealthJob(jobId) {
  const res = await fetch(`${API_BASE}/api/health/current/jobs/${jobId}`);
  return handleJsonResponse(res);
}

export async function fetchMonthlyHistory({ repoFullName, months = '24', metrics = [] }) {
  const url = new URL(`${API_BASE}/api/history/monthly`);
  url.searchParams.set('repo', repoFullName);
  url.searchParams.set('months', months);
  metrics.forEach((metric) => url.searchParams.append('metrics', metric));
  const res = await fetch(url.toString());
  return handleJsonResponse(res);
}

export async function fetchHistoryCoverage(repoFullName) {
  const url = new URL(`${API_BASE}/api/history/coverage`);
  url.searchParams.set('repo', repoFullName);
  const res = await fetch(url.toString());
  return handleJsonResponse(res);
}

export async function fetchRepositoryCatalog() {
  const res = await fetch(`${API_BASE}/api/repositories`);
  return handleJsonResponse(res);
}

export async function searchRepositories(query, limit = 8, signal) {
  const url = new URL(`${API_BASE}/api/repositories/search`);
  url.searchParams.set('q', query);
  url.searchParams.set('limit', String(limit));
  const res = await fetch(url.toString(), { signal });
  return handleJsonResponse(res);
}

export async function fetchHealthRanking(repo, limit = 10, scoreType = 'community') {
  const url = new URL(`${API_BASE}/api/health/current/ranking`);
  url.searchParams.set('limit', String(limit));
  url.searchParams.set('score_type', scoreType);
  if (repo) url.searchParams.set('repo', repo);
  const res = await fetch(url.toString());
  return handleJsonResponse(res);
}

export async function importRepository(repoFullName) {
  const res = await fetch(`${API_BASE}/api/repositories/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_full_name: repoFullName }),
  });
  return handleJsonResponse(res);
}

export async function fetchImportJob(jobId) {
  const res = await fetch(`${API_BASE}/api/repositories/import/${jobId}`);
  return handleJsonResponse(res);
}

export async function refreshMonthlyRepository(repoFullName) {
  const res = await fetch(`${API_BASE}/api/repositories/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_full_name: repoFullName }),
  });
  return handleJsonResponse(res);
}

export async function fetchEcosystemGraph({ rootRepo, start, end, contributorLimit = 30, signal }) {
  const url = new URL(API_BASE + '/api/ecosystem/graph');
  url.searchParams.set('root_repo', rootRepo);
  if (start) url.searchParams.set('start', start);
  if (end) url.searchParams.set('end', end);
  url.searchParams.set('contributor_limit', String(contributorLimit));
  const res = await fetch(url.toString(), { signal });
  return handleJsonResponse(res);
}

export async function fetchEcosystemExpansion({ nodeType, nodeId, start, end, limit, depth, rootRepo, signal }) {
  const url = new URL(API_BASE + '/api/ecosystem/expand');
  url.searchParams.set('node_type', nodeType);
  url.searchParams.set('node_id', nodeId);
  url.searchParams.set('start', start);
  url.searchParams.set('end', end);
  url.searchParams.set('limit', String(limit));
  url.searchParams.set('depth', String(depth));
  if (rootRepo) url.searchParams.set('root_repo', rootRepo);
  const res = await fetch(url.toString(), { signal });
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
