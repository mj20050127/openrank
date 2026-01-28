# 健康分评估模型

## 概述

健康分（Health Score）是一个综合评估开源项目整体健康状况的指标，采用 **五维度加权评分模型**，总分 **0-100 分**。

## 五维度模型

| 维度                         | 权重 | 说明                                  |
| ---------------------------- | ---- | ------------------------------------- |
| **Vitality（活跃度）**       | 30%  | 项目的生命力和社区活跃程度            |
| **Responsiveness（响应度）** | 25%  | 项目对 Issue/PR 的响应和处理效率      |
| **Resilience（韧性）**       | 20%  | 项目的可持续性和风险抵御能力          |
| **Governance（治理）**       | 15%  | 项目的文档完整度和流程透明度          |
| **Security（安全）**         | 10%  | 项目的安全性评估（OpenSSF Scorecard） |

---

## 维度详解

### 1️⃣ Vitality（活跃度）$W_V = 30\%$

活跃度由四个子维度组成：

$$\text{Vitality} = 0.30 \times I + 0.40 \times M + 0.20 \times C + 0.10 \times G$$

其中：

- **Influence（影响力）$I$**：基于 OpenRank 对数评分，
- 
- $I=\text{clamp}(18 \times \ln(1 + \text{OpenRank}), 0, 100)$

- **Momentum（动能）$M$**：最近 3 个月活动量，
-
- $M=\text{clamp}(18 \times \ln(1 + \text{Activity}_{3m}), 0, 100)$

- **Community（社区）$C$**：参与者和新贡献者，
-
- $C = 0.7 \times \text{clamp}(18 \times \ln(1 + P), 0, 100) + 0.3 \times \text{clamp}(18 \times \ln(1 + NC), 0, 100)$
- ，其中 $P$ 为过去 3 个月参与者数，$NC$ 为新贡献者数

- **Growth（增长率）$G$**：活动增长势头，

$$G = \text{clamp}\left(100 \times \frac{\text{Activity}_{3m} - \text{Activity}_{prev3m}}{3 \times \text{Activity}_{prev3m}} + 100, 0, 100\right)$$

---

### 2️⃣ Responsiveness（响应度）$W_R = 25\%$

响应度评估项目对问题和变更的处理速度。使用时间评分函数：

$$
T(h, g, b) = \begin{cases}
100 & \text{if } h \leq g \\
0 & \text{if } h \geq b \\
100 \times \frac{b - h}{b - g} & \text{otherwise}
\end{cases}
$$

其中 $h$ 为小时数，$g$ 为优秀阈值，$b$ 为不可接受阈值。

各指标的时间阈值：

| 指标           | 优秀(g) | 不可接受(b) |
| -------------- | ------- | ----------- |
| Issue 首次响应 | 24h     | 168h        |
| PR 首次响应    | 12h     | 120h        |
| Issue 关闭     | 72h     | 720h        |
| PR 关闭        | 48h     | 720h        |
| Issue 积压     | 168h    | 2160h       |
| PR 积压        | 168h    | 2160h       |

三个子维度：

$$\text{FirstResponse} = \text{weighted-avg}(T(\text{issue-first}), T(\text{pr-first}), w)$$

$$\text{Closing} = \text{weighted-avg}(T(\text{issue-close}), T(\text{pr-close}), w)$$

$$\text{Backlog} = \text{weighted-avg}(T(\text{issue-age}), T(\text{pr-age}), w)$$

其中权重 $w$ 按 Issue/PR 数量的对数加权：$w_i = \ln(1 + n_i)$

最终：

$$\text{Responsiveness} = 0.45 \times \text{FirstResponse} + 0.35 \times \text{Closing} + 0.20 \times \text{Backlog}$$

---

### 3️⃣ Resilience（韧性）$W_R = 20\%$

韧性评估项目的可持续性和风险抵御能力。

$$\text{Resilience} = 0.45 \times BF + 0.35 \times D + 0.20 \times RT$$

其中：

- **Bus Factor（总线因子）$BF$**：
- $BF=\text{clamp}(20 \times \text{BusFactor}, 0, 100)$

- **Diversity（代码多样性）$D$**：
- $D=\text{clamp}(100 \times (1 - \text{HHI}), 0, 100)$；
- 或使用 Top-1 Share：
- $D=\text{clamp}(100 \times (1 - \text{Top1Share}), 0, 100)$

- **Retention（贡献者留存率）$RT$**：
- $RT=\text{clamp}\left(100 \times \left(1 - \frac{\text{InactiveContributors}}{\max(1, \text{TotalContributors})}\right), 0, 100\right)$

---

### 4️⃣ Governance（治理）$W_G = 15\%$

治理评估项目的文档完整度和过程透明度。

$$\text{Governance} = 0.45 \times F + 0.35 \times P + 0.20 \times T$$

其中：

- **Files（文件完整度）$F$**：GitHub Community Profile 返回的健康百分比，
- $F=\text{clamp}(\text{GitHub-Health-Percentage}, 0, 100)$

- **Process（流程透明度）$P$**：基于响应度的流程评分，
- $P = 0.6 \times \text{IssueFirstResponse} + 0.4 \times \text{IssueClosing}$

- **Transparency（透明度奖励）$T$**:
- 
$$
T = \begin{cases} 
100 & \text{if 有 README, License, Contributing 且有 Issue/PR 模板} \\ 
\text{Coverage}(\text{files}) & \text{otherwise} 
\end{cases}
$$
- 其中
- $\text{Coverage} = 100 \times \frac{\text{count of required files present}}{7}$

   必检查文件：README, License, Contributing, Code of Conduct, Security, Issue Template, PR Template

**降级处理**：若治理分无法计算，使用：
$$\text{Governance} = 0.8 \times \text{Vitality} + 20$$

---

### 5️⃣ Security（安全）$W_S = 10\%$

安全分基于 [OpenSSF Security Scorecard](https://securityscorecards.dev) 评估。

$$\text{Security} = 0.70 \times B + 0.20 \times C + 0.10 \times \text{Bonus}$$

其中：

- **Base（基础分）$B$**：
- $B=\text{clamp}(10 \times \text{Scorecard-Score}, 0, 100)$

- **Critical（关键检查）$C$**：关键检查项的平均分，
- $C=\text{clamp}\left(\frac{1}{n} \sum_{i=1}^{n} \text{check}_i \times 10, 0, 100\right)$

- **Bonus（奖励）**：固定 10 分

**降级处理**：若无法获取 Scorecard 数据（defaulted=true），直接设为 50 分；如果最终分为空，使用默认值 60 分。

---

## 总分计算

$$\text{HealthScore} = 0.30 \times V + 0.25 \times R + 0.20 \times Re + 0.15 \times G + 0.10 \times S$$

其中：

- $V$ = Vitality（活跃度）
- $R$ = Responsiveness（响应度）
- $Re$ = Resilience（韧性）
- $G$ = Governance（治理）
- $S$ = Security（安全）

**最终结果**：
$\text{HealthScore} \in [0, 100]$

---

## 数据流

1. **抓取源数据**

   - OpenDigger API → Activity, OpenRank, Contributors, etc.
   - GitHub API → Governance files, Community profile
   - OpenSSF API → Security Scorecard

2. **数据处理**

   - 取最新值 (latest)
   - 聚合求和 (3-month rolling sum, 12-month active months)
   - 计算衍生指标 (growth rate, retention rate, etc.)

3. **分数计算**

   - 各维度独立计算
   - 加权聚合为总分

4. **持久化存储**

   - 写入 HealthOverviewDaily 日表
   - 保存 raw_payloads 用于审计/前端展示

5. **返回结果**
   - 返回完整的健康快照 (snapshot)

---

## 特性说明

- **防空降级**：各维度数据缺失时有合理的降级方案，确保总分始终可用
- **对数评分**：高增长指标采用对数处理（$\ln(1+x)$），避免极端值过度主导
- **时间阈值**：用绝对时间阈值而非相对排名，更符合用户的切实体验
- **灵活权重**：五个维度和各子维度的权重都可根据业务需求调整
- **加权平均**：对于数据缺失，只对非空数据重新加权，防止假设分拉低总分