# 当前即时健康分评估模型（current-v1）

## 概述

当前健康分（Health Score）是面向开源项目的即时治理体检指标，采用 **五维度加权评分模型**，总分范围为 **0–100 分**。

当前即时体检以后端 `current-v1` 为唯一权威口径：

- 接口：`GET /health/current?repo={owner}/{repo}`
- 评分版本：`current-v1`
- 默认观测窗口：最近 90 天
- 数据来源：GitHub REST API + OpenSSF Scorecard
- 当前排行榜：使用 `scores.comprehensive`

> 本文档记录当前即时模型。历史月度 `HealthOverviewDaily` 模型请参见 [`Health_Score_Algorithm.md`](Health_Score_Algorithm.md)，两者的五维总权重相同，但内部指标和数据窗口不同。

## 五维度模型

| 维度                         | 权重 | 说明                                  |
| ---------------------------- | ---- | ------------------------------------- |
| **Vitality（活跃度）**       | 30%  | 最近活动、维护节奏与参与规模          |
| **Responsiveness（响应度）** | 25%  | Issue/PR 流转效率和开放队列年龄        |
| **Resilience（韧性）**       | 20%  | 贡献者分散度、Bus Factor 和持续参与     |
| **Governance（治理）**       | 15%  | 协作流程与治理文件完整性               |
| **Security（安全）**         | 10%  | Scorecard、安全政策和供应链工作流       |

---

## 基础评分函数

所有中间分数都限制在 `[0, 100]` 区间。

### 1. 对数评分

用于贡献者规模和 Bus Factor，降低大型项目极端值的影响：

$$
L(x, r) = \text{clamp}\left(100 \times \frac{\ln(1+x)}{\ln(1+r)}, 0, 100\right)
$$

其中 $x$ 为实际值，$r$ 为参考值。

### 2. 负向指标评分

用于推送年龄和开放队列年龄，数值越小越好：

$$
D(x, b) = \text{clamp}\left(100 \times \left(1 - \frac{\min(x,b)}{b}\right), 0, 100\right)
$$

其中 $x$ 为实际年龄，$b$ 为风险上限。

### 3. 动能评分

用于比较当前 90 天与前一个 90 天窗口：

$$
M(x, p) = \text{clamp}\left(50 + 50 \times \tanh\left(\frac{x-p}{|p|}\right), 0, 100\right)
$$

其中 $x$ 为当前窗口值，$p$ 为前一窗口值。当前值与前值相等时约为 50 分，改善趋近 100 分，恶化趋近 0 分。

当 $p=0$ 时：当前值大于 0 返回 100 分，否则返回 50 分。

### 4. 流转比例评分

$$
Q(n,d,t) = \text{clamp}\left(100 \times \frac{n/d}{t}, 0, 100\right)
$$

其中 $n$ 为已处理数量，$d$ 为新增数量，$t$ 为目标比例。

当 $d \leq 0$ 时，若 $n>0$ 返回 100 分，否则该子项记为缺失。

### 5. 可用数据加权

对缺失子项不填充虚假分数，只对可用子项重新归一化：

$$
W(v_i,w_i) = \frac{\sum_{i \in A} v_i w_i}{\sum_{i \in A} w_i}
$$

其中 $A$ 为有有效值的子项集合。若可用权重低于 80%，该维度记为不可计算。

---

## 维度详解

### 1️⃣ Vitality（活跃度）$W_V = 30\%$

活跃度由最近 90 天 GitHub 证据计算：

$$
\text{Vitality} =
0.30 \times M(\text{commits}_{cur}, \text{commits}_{prev})
+ 0.25 \times A
+ 0.20 \times D(\text{push\_age}, 90)
+ 0.15 \times M(\text{throughput}_{cur}, \text{throughput}_{prev})
+ 0.10 \times L(\text{active\_contributors}, 100)
$$

其中：

$$
A = 100 \times \frac{\text{active\_weeks}}{\text{weeks\_observed}}
$$

$$
\text{throughput} = \text{issues\_opened} + \text{prs\_opened}
$$

- `commits_cur`：当前 90 天提交数；
- `commits_prev`：前一个 90 天提交数；
- `push_age`：默认分支距最近一次推送的天数；
- `active_weeks`：当前窗口有提交的周数；
- `active_contributors`：当前窗口有贡献的贡献者数。

---

### 2️⃣ Responsiveness（响应度）$W_R = 25\%$

响应度不再使用旧版的“首次响应/关闭周期/积压”三组子维度，而使用当前窗口的 Issue/PR 流转和开放队列年龄：

$$
I = Q(\text{issues\_closed}, \text{issues\_opened}, 1.0)
$$

$$
P = Q(\text{prs\_merged}, \text{prs\_opened}, 0.8)
$$

$$
\text{Responsiveness} =
0.30 \times I
+ 0.30 \times P
+ 0.20 \times D(\text{open\_issue\_age}, 180)
+ 0.20 \times D(\text{open\_pr\_age}, 120)
$$

其中：

- `issues_closed / issues_opened`：Issue 流转比例；
- `(prs_merged / prs_opened) / 0.8`：PR 相对于 80% 目标的流转比例；
- `open_issue_age`：开放 Issue 中位年龄，单位为天；
- `open_pr_age`：开放 PR 中位年龄，单位为天。

---

### 3️⃣ Resilience（韧性）$W_{Re} = 20\%$

韧性评估贡献结构是否过度依赖单一贡献者，以及社区是否具有持续参与能力：

$$
\text{Concentration} = \text{clamp}(100 \times (1 - \text{Top1Share}), 0, 100)
$$

$$
\text{Resilience} =
0.35 \times L(\text{bus\_factor}, 10)
+ 0.30 \times \text{Concentration}
+ 0.20 \times L(\text{active\_contributors}, 100)
+ 0.15 \times A
$$

其中：

- `bus_factor`：贡献总量达到 50% 所需的最少贡献者数量；
- `Top1Share`：第一贡献者占全部贡献的比例；
- `active_contributors`：当前窗口活跃贡献者数量；
- `A`：活跃周得分。

---

### 4️⃣ Governance（治理）$W_G = 15\%$

治理分由协作流程和治理文件两部分组成。

#### A. 流程分 Process Score

$$
P_g =
0.40 \times I
+ 0.40 \times P
+ 0.10 \times D(\text{open\_issue\_age}, 180)
+ 0.10 \times D(\text{open\_pr\_age}, 120)
$$

#### B. 治理文件分 Governance File Score

| 文件/配置 | 权重 |
| --------- | ---- |
| README | 10 |
| LICENSE | 15 |
| CONTRIBUTING | 20 |
| Code of Conduct | 15 |
| SECURITY | 10 |
| Issue Template | 10 |
| Pull Request Template | 10 |
| GOVERNANCE | 5 |
| CODEOWNERS | 5 |

若文件存在，则计入对应权重；治理文件满分为 100 分。

#### C. 最终治理分

$$
\text{Governance} = 0.60 \times P_g + 0.40 \times F_g
$$

其中 $F_g$ 为治理文件分。

---

### 5️⃣ Security（安全）$W_S = 10\%$

安全分基于 OpenSSF Scorecard 和仓库安全工作流：

$$
\text{Security} =
0.60 \times S_c
+ 0.10 \times S_p
+ 0.10 \times S_d
+ 0.10 \times S_{sast}
+ 0.10 \times S_w
$$

其中：

- $S_c$：Scorecard 原始分乘以 10，转换到 0–100 分；
- $S_p$：是否存在安全政策；
- $S_d$：依赖自动更新或依赖检查；
- $S_{sast}$：SAST 或代码审查检查；
- $S_w$：依赖固定、分支保护和工作流卫生检查。

每个布尔型或检查型组件通常映射为 0 或 100；Scorecard 检查项按其原始分转换。

---

## 总分计算

$$
\text{HealthScore} =
0.30 \times V
+ 0.25 \times R
+ 0.20 \times Re
+ 0.15 \times G
+ 0.10 \times S
$$

其中：

- $V$ = Vitality（活跃度）；
- $R$ = Responsiveness（响应度）；
- $Re$ = Resilience（韧性）；
- $G$ = Governance（治理）；
- $S$ = Security（安全）。

最终结果满足：

$$
\text{HealthScore} \in [0, 100]
$$

---

## 完整度与缺失处理

五维完整度为各维度可用程度按总权重加权后的结果：

$$
\text{Completeness} =
0.30 \times C_V
+ 0.25 \times C_R
+ 0.20 \times C_{Re}
+ 0.15 \times C_G
+ 0.10 \times C_S
$$

只有满足以下条件时才返回综合健康分：

1. 五个维度均可计算；
2. `Completeness >= 0.80`。

`null` 表示证据不足，不等于 0 分。若 Scorecard 暂时不可用，也不使用旧版的固定 50 分或 60 分兜底，而是保留来源状态并等待补采集。

---

## 数据流

1. **抓取当前证据**
   - GitHub 仓库元数据、提交统计、贡献者、Issue、PR；
   - GitHub 默认分支文件树与工作流；
   - OpenSSF Scorecard 及其检查项。

2. **计算派生特征**
   - 推送年龄、活跃周比例；
   - Issue/PR 流转比例；
   - 贡献集中度、Bus Factor；
   - 治理文件分和安全组件分。

3. **计算五维分**
   - 各维度对可用子项重新加权；
   - 计算完整度和置信度；
   - 证据不足时不生成虚假的综合分。

4. **持久化存储**
   - 写入 `CurrentRepoAssessment`；
   - 保存 `evidence_json`、`risks_json`、来源时间和来源状态；
   - 标记 `score_version = current-v1`。

5. **返回结果**
   - 返回五维分、综合分、完整度、风险和原始证据；
   - 排行榜仅使用同一版本的即时综合分。

---

## 与历史月度模型的关系

- 五维总权重保持一致：30%/25%/20%/15%/10%；
- 当前即时模型使用最近 90 天 GitHub 证据；
- 历史月度模型使用 OpenDigger 和 `HealthOverviewDaily`；
- 当前即时分用于当前状态和排名；
- 月度模型用于趋势、历史对比和指标下钻；
- 两者出现差异时，不应混合或互相覆盖。