export const CONTRIBUTOR_ROLE_COLORS = Object.freeze({
  core: '#245A48',
  active: '#34755F',
  newcomer: '#88AC94',
  churn_risk: '#C45F3A',
  other: '#A7AEA8',
});

export const CONTRIBUTOR_ROLE_LABELS = Object.freeze({
  core: '核心贡献者',
  active: '活跃贡献者',
  newcomer: '新晋贡献者',
  churn_risk: '流失风险',
  other: '其他',
});

function normalizedRole(node) {
  if (node?.churn_risk || node?.role === 'risk' || node?.role === 'churn_risk') return 'churn_risk';
  if (node?.role === 'new' || node?.role === 'newcomer') return 'newcomer';
  if (node?.role === 'core' || node?.role === 'active') return node.role;
  return 'other';
}

function activeMonthsInLast12(node) {
  if (!Array.isArray(node?.activity_12m)) return null;
  return node.activity_12m.reduce((count, item) => {
    const value = Number(item?.value ?? item?.contribution ?? item?.score);
    return count + (Number.isFinite(value) && value > 0 ? 1 : 0);
  }, 0);
}

export function adaptEcosystemContributors(nodes = []) {
  return nodes
    .filter((node) => node?.type === 'contributor')
    .map((node) => ({
      id: String(node.id || ''),
      login: String(node.login || node.label || node.id || ''),
      avatarUrl: node.avatar_url || node.avatarUrl || null,
      contribution: Number(node.contribution_score ?? node.contribution),
      role: normalizedRole(node),
      activeMonths12: activeMonthsInLast12(node),
    }));
}

function concentrationStatus(top5Share) {
  if (!Number.isFinite(top5Share)) return null;
  if (top5Share < 50) return { label: '结构分散', tone: 'balanced' };
  if (top5Share <= 70) return { label: '需要关注', tone: 'attention' };
  return { label: '集中度偏高', tone: 'high' };
}

export function buildContributorPareto(contributors = [], visibleLimit = 10) {
  const sorted = contributors
    .filter((item) => item?.id && item?.login && Number.isFinite(Number(item.contribution)) && Number(item.contribution) > 0)
    .map((item) => ({ ...item, contribution: Number(item.contribution) }))
    .sort((left, right) => right.contribution - left.contribution || left.login.localeCompare(right.login));

  const totalContribution = sorted.reduce((sum, item) => sum + item.contribution, 0);
  if (!sorted.length || totalContribution <= 0) {
    return {
      contributors: [],
      totalContribution: null,
      busFactor: null,
      top5Share: null,
      maxSingleShare: null,
      status: null,
    };
  }

  let cumulativeShare = 0;
  let busFactor = null;
  const calculated = sorted.map((item, index) => {
    const share = (item.contribution / totalContribution) * 100;
    cumulativeShare += share;
    if (busFactor === null && cumulativeShare >= 50) busFactor = index + 1;
    return {
      ...item,
      share,
      cumulativeShare: Math.min(cumulativeShare, 100),
      isBusFactorMember: busFactor === null || index < busFactor,
      isAggregate: false,
    };
  });

  // Bus Factor is known only after the whole sorted list has been traversed.
  const withMembership = calculated.map((item, index) => ({
    ...item,
    isBusFactorMember: index < busFactor,
  }));
  const top5Share = withMembership.slice(0, 5).reduce((sum, item) => sum + item.share, 0);
  const visible = withMembership.slice(0, visibleLimit);
  const remainder = withMembership.slice(visibleLimit);

  if (remainder.length) {
    visible.push({
      id: '__other__',
      login: '其他',
      avatarUrl: null,
      contribution: remainder.reduce((sum, item) => sum + item.contribution, 0),
      role: 'other',
      activeMonths12: null,
      share: remainder.reduce((sum, item) => sum + item.share, 0),
      cumulativeShare: 100,
      isBusFactorMember: busFactor > visibleLimit,
      isAggregate: true,
      aggregateCount: remainder.length,
    });
  }

  return {
    contributors: visible,
    totalContribution,
    busFactor,
    top5Share,
    maxSingleShare: withMembership[0]?.share ?? null,
    status: concentrationStatus(top5Share),
  };
}

export function formatParetoPercent(value) {
  return Number.isFinite(value) ? `${value.toFixed(1)}%` : '—';
}
