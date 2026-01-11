# 趋势分析算法 (基于后端代码实现)

## 1. 核心计算逻辑 (`_compute_derived`)

该函数接收一个指标的时间序列数组 `values`，返回统计分析结果。

### 1.1 线性趋势检测 (Linear Regression Slope)

- **计算方法**: 使用一元线性回归拟合数据点。
- **实现**: `numpy.polyfit(x, values, 1)`，其中 `x` 是时间索引，`values` 是指标值。
- **窗口选择**: 选取数据的末尾段进行拟合。窗口长度为 `slope_window` 参数（默认值通常为 30），且受到数据总长度 `n` 的限制。
  - 代码逻辑: `arr[-min(max(slope_window, 2), n):]`
  - 约束: 至少需要 2 个数据点才能计算。
- **输出**: 拟合出的斜率 `slope`。

### 1.2 趋势方向判定 (`_direction_label`)

基于计算出的斜率 `slope` 进行分类：

- **rising (上升)**: `slope > 0`
- **falling (下降)**: `slope < 0`
- **flat (持平)**: `slope` 为 `None` 或等于 0

### 1.3 统计平滑 (Rolling Statistics)

计算基于固定窗口的移动平均值和中位数，作为平滑后的参考值。直接对数组末尾切片进行计算。

- **7 日窗口**:
  - `rolling_mean_7d`: `np.mean(arr[-7:])`
  - `rolling_median_7d`: `np.median(arr[-7:])`
- **30 日窗口**:
  - `rolling_mean_30d`: `np.mean(arr[-30:])`
  - `rolling_median_30d`: `np.median(arr[-30:])`

### 1.4 异常检测 (Anomaly Z-Score)

计算最后一个数据点的 Z-Score（标准分数）。

- **公式**: $Z = (x_{last} - \mu) / \sigma$
  - $x_{last}$: 数组最后一个值
  - $\mu$: 数组均值 (`np.mean(arr)`)
  - $\sigma$: 数组标准差 (`np.std(arr)`)
- **条件**: 仅当数据点数量 $n \ge 3$ 且 $\sigma > 0$ 时计算，否则返回 `None` 或 `0.0`。

### 1.5 响应达标率 (Response Ratio)

仅当传入 `response_hours` 参数时计算。

- **计算**: 统计序列中数值小于等于 `response_hours`（默认 48）的比例。
- **公式**: `np.mean(arr <= response_hours)`

---

### 1.6 滑动窗口归一化 (Sliding Window Normalization)

为适配非平稳时序（指标量级随时间变化、存在季节性或结构性突变），系统支持基于滑动窗口 $w$ 的动态归一化，用于趋势拟合与异常检测的前置预处理。

- **Z-Score 动态归一化**:

$$z_t = \frac{y_t - \mu_{t-w:t}}{\sigma_{t-w:t}}$$
其中

$\mu_{t-w:t}$、
$\sigma_{t-w:t}$ 
分别为窗口

$[t-w, t]$ 
内的统计值。

窗口长度 $w$ 的典型取值：7（日维平滑、快速响应）与 30（月度尺度、抗噪更强），与上文 Rolling Statistics 保持一致。

#### 优势与作用
- **适配非平稳**：随时间滚动的基线避免“长期漂移”污染斜率与异常值，兼容增长/衰减趋势。
- **提高可比性**：不同仓库、不同时间段的量级差异被动态标准化，便于跨项目与跨周期对比。
- **稳健异常检出**：在季节性波动场景下，Z-Score 以局部统计量为参照，减少误报与漏报。
- **增强回归稳定性**：对归一化后的序列进行最小二乘拟合，数值尺度统一、收敛更稳定。

实践建议：
- 在进行趋势斜率计算与异常检测前先执行窗口归一化；
- 当指标天然已归一（如占比/比例）且波动平稳，可跳过本步骤以降低计算开销；
- 对极端值敏感场景可在窗口内先做 Winsorize（截尾）或中位数绝对偏差（MAD）归一化。

## 2. 报告生成与诊断 (`generate_trend_report`)

该接口基于用户指定的时间窗口和指标，利用上述核心计算逻辑生成报告，并包含以下诊断规则。

### 2.1 供需比率 (Ratios)

基于查询到的时序数据总和计算：

- **Issue Closure Ratio**: $\sum(\text{issues\\_closed}) / \sum(\text{issues\\_new})$
- **PR Merge Ratio**: $\sum(\text{change\\_requests\\_accepted}) / \sum(\text{prs\\_new})$

### 2.2 自动诊断规则 (Hardcoded Diagnosis)

代码中包含以下固定的阈值判定逻辑。若条件满足，相应的诊断信息会被添加到 `diagnosis` 列表中。

| 检查指标                       | 判定条件               | 诊断信息                                   |
| :----------------------------- | :--------------------- | :----------------------------------------- |
| `metric_pr_response_time_h`    | 最新值(`latest`) > 48  | "PR 首响超过 48 小时，维护者响应偏慢"      |
| `metric_issue_response_time_h` | 最新值(`latest`) > 48  | "Issue 首响超过 48 小时，需要 triage 流程" |
| `metric_bus_factor`            | 最新值(`latest`) < 2   | "Bus Factor 偏低，核心贡献者集中"          |
| `metric_top1_share`            | 最新值(`latest`) > 0.5 | "Top1 占比过高，贡献集中度风险"            |
| `metric_scorecard_score`       | 最新值(`latest`) < 6   | "Scorecard 得分偏低，安全流程需要补全"     |

### 2.3 建议行动 (Fixed Improvements)

无论数据如何，代码固定返回以下建议列表：

1. "设定 triage 值班和 48h 首响 SLA，优先处理新 issue/PR"
2. "每周清理 backlog，先处理 age 较长的 issue/PR"
3. "制定贡献者轮值与代码所有权，分散核心贡献者风险"
4. "补齐 SECURITY.md / CODEOWNERS / 模板，提升 scorecard"

---

## 3. 复合指标计算 (`get_composite_series`)

该接口计算三个复合维度的归一化得分趋势：Vitality, Responsiveness, Resilience。具体的合成逻辑（如 `compute_vitality_series`）在 `graph_lab/metrics.py` 或相关模块定义，本文件仅负责数据组装和调用。