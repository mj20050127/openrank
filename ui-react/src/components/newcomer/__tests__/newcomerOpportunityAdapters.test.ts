import test from 'node:test';
import assert from 'node:assert/strict';
import {
  adaptNewcomerProjects,
  countUniqueTasks,
  filterNewcomerProjects,
  getBubbleRadius,
  layoutOpportunityNodes,
  normalizeTrend,
  resolveCustomDataItem,
  selectDefaultProject,
} from '../newcomerOpportunityAdapters.js';

function project(overrides = {}) {
  return adaptNewcomerProjects([{
    repo_full_name: 'demo/project',
    domains: ['ai_ml'],
    stacks: ['python'],
    matched_domains: ['ai_ml'],
    matched_stacks: ['python'],
    readiness_score: 82,
    match_score: 91,
    difficulty: 'Easy',
    responsiveness: 12,
    activity: 100,
    trend_delta: 0.12,
    stats: { good_first: 4, help_wanted: 3, docs: 2, i18n: 1 },
    ...overrides,
  }])[0];
}

test('新人任务按 Issue 标识去重', () => {
  assert.equal(countUniqueTasks([
    { issue_number: 1, title: 'same' },
    { issue_number: 1, title: 'same again' },
    { issue_number: 2, title: 'other' },
  ]), 2);
});

test('适配层保留真实任务计数并限制坐标', () => {
  const item = project({ readiness_score: 140, match_score: -4 });
  assert.equal(item.taskCount, 10);
  assert.equal(item.readiness, 100);
  assert.equal(item.match, 0);
});

test('趋势百分比兼容小数和百分数输入', () => {
  assert.equal(normalizeTrend(0.03), 'stable');
  assert.equal(normalizeTrend(0.12), 'up');
  assert.equal(normalizeTrend(-8), 'down');
});

test('任务和近期活跃筛选不把缺失当成 0 或活跃', () => {
  const active = project();
  const missing = project({ repo_full_name: 'demo/missing', stats: null, activity: null, last_activity_at: null });
  const result = filterNewcomerProjects([active, missing], {
    domains: ['ai_ml'], skills: ['python'], difficulty: 'all', minimumTasks: 5, recentOnly: true,
  });
  assert.deepEqual(result.map((item) => item.repository), ['demo/project']);
  assert.equal(missing.taskCount, null);
  assert.equal(missing.recentlyActive, false);
});

test('默认优先右上象限且任务数达标的项目', () => {
  const candidate = project();
  const weaker = project({ repo_full_name: 'demo/weaker', readiness_score: 90, match_score: 88, stats: { good_first: 1 } });
  assert.equal(selectDefaultProject([weaker, candidate], 5).repository, 'demo/project');
});

test('ECharts custom 系列在 params.data 缺失时按 dataIndex 取回仓库', () => {
  const item = project({ repo_full_name: 'demo/custom' });
  const data = [{ project: item }];
  assert.equal(resolveCustomDataItem(data, { dataIndexInside: 0 })?.project.repository, 'demo/custom');
  assert.equal(resolveCustomDataItem(data, { dataIndex: 0 })?.project.repository, 'demo/custom');
  assert.equal(resolveCustomDataItem(data, { data: data[0] })?.project.repository, 'demo/custom');
});
test('气泡半径使用平方根并保持范围', () => {
  assert.equal(getBubbleRadius(null), 14);
  assert.ok(getBubbleRadius(40) < getBubbleRadius(10) * 2);
  assert.equal(getBubbleRadius(10000), 32);
});
test('碰撞布局确定性且最大偏移受限', () => {
  const nodes = [
    { id: 'a', label: 'a', rawPixelX: 100, rawPixelY: 100, radius: 20 },
    { id: 'b', label: 'b', rawPixelX: 100, rawPixelY: 100, radius: 20 },
  ];
  const options = { bounds: { left: 0, top: 0, right: 300, bottom: 300 }, maxDisplacement: 36, iterations: 24 };
  const first = layoutOpportunityNodes(nodes, options);
  const second = layoutOpportunityNodes(nodes, options);
  assert.deepEqual(first, second);
  for (const node of first) {
    assert.ok(Math.hypot(node.offsetX, node.offsetY) <= 36.001);
  }
  assert.ok(first.some((node) => node.displaced));
});
test('集中分布的仓库标签全部显示且互不重叠', () => {
  const labels = [
    'jax-ml/jax',
    'huggingface/diffusers',
    'NVIDIA/Megatron-LM',
    'Lightning-AI/pytorch-lightning',
    'open-webui/open-webui',
    'astral-sh/uv',
    'apache/echarts',
    'browser-use/browser-use',
  ];
  const nodes = labels.map((label, index) => ({
    id: label,
    label,
    rawPixelX: 430 + (index % 4) * 24,
    rawPixelY: 170 + Math.floor(index / 4) * 26,
    radius: 20 + (index % 2) * 4,
    selected: index === 3,
  }));
  const result = layoutOpportunityNodes(nodes, {
    bounds: { left: 0, top: 0, right: 1000, bottom: 500 },
    maxDisplacement: 36,
    iterations: 24,
    labelGap: 5,
  });

  assert.equal(result.length, labels.length);
  result.forEach((node) => assert.ok(node.labelBox));

  for (let first = 0; first < result.length; first += 1) {
    for (let second = first + 1; second < result.length; second += 1) {
      const a = result[first].labelBox;
      const b = result[second].labelBox;
      const overlaps = (
        a.x < b.x + b.width + 5
        && a.x + a.width + 5 > b.x
        && a.y < b.y + b.height + 5
        && a.y + a.height + 5 > b.y
      );
      assert.equal(overlaps, false, labels[first] + ' overlaps ' + labels[second]);
    }
  }
});
test('仓库标签避开象限标题保留区域', () => {
  const reservedBoxes = [
    { x: 300, y: 20, width: 100, height: 28 },
    { x: 500, y: 240, width: 100, height: 28 },
  ];
  const nodes = [
    { id: 'a', label: 'huggingface/diffusers ↘', rawPixelX: 360, rawPixelY: 60, radius: 22 },
    { id: 'b', label: 'Lightning-AI/pytorch-lightning ↗', rawPixelX: 550, rawPixelY: 270, radius: 24 },
  ];
  const result = layoutOpportunityNodes(nodes, {
    bounds: { left: 0, top: 0, right: 900, bottom: 500 },
    reservedBoxes,
  });

  for (const node of result) {
    for (const reserved of reservedBoxes) {
      const label = node.labelBox;
      const overlaps = (
        label.x < reserved.x + reserved.width + 5
        && label.x + label.width + 5 > reserved.x
        && label.y < reserved.y + reserved.height + 5
        && label.y + label.height + 5 > reserved.y
      );
      assert.equal(overlaps, false);
    }
  }
});
test('后端放宽召回的仓库不会被兴趣与技能条件二次清空', () => {
  const stackMatch = project({
    repo_full_name: 'demo/stack-match',
    domains: ['developer_tools'],
    stacks: ['python'],
    matched_domains: [],
  });
  const result = filterNewcomerProjects([stackMatch], {
    difficulty: 'all',
    minimumTasks: 1,
    recentOnly: false,
  });
  assert.deepEqual(result.map((item) => item.repository), ['demo/stack-match']);
});

