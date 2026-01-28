# 开源新人项目推荐算法

## 1. 概述

该算法旨在为初次接触开源项目的开发者推荐适合其技术栈和时间投入的项目。通过 **召回 (Recall)** -> **评分 (Score)** -> **组装 (Assemble)** 三个阶段，从海量仓库中筛选出最匹配的新人友好项目。

核心代码位于：

- 服务编排：`backend/app/services/newcomer_plan.py`
- 评分逻辑：`backend/app/services/newcomer_scoring.py`

## 2. 算法流程

### 2.1 召回阶段 (Recall)

系统首先根据用户输入的 **领域 (Domain)**、**技术栈 (Stack)** 和 **关键词 (Keywords)** 进行粗筛。

1.  **宽泛召回**：从数据库 `seed_repo_catalog` 中提取前 N 个项目（默认 150 个，避免性能瓶颈）。
2.  **严格匹配 (Strict Match)**：
    - 领域完全匹配（部分包含关系）
    - 技术栈完全匹配
    - 关键词命中（标签或描述中包含）
3.  **松弛匹配 (Relaxed Match - Fallback)**：
    - 如果严格匹配结果少于预设限制（默认 6 个），则启用松弛匹配。
    - 条件放宽为：领域或技术栈命中其一即可，或者关键词命中。
4.  **填充 (Filler)**：如果依然不足，用剩余仓库补足数量限制。

### 2.2 评分阶段 (Scoring)

对召回的候选仓库进行深度评分，计算 **Match Score**。

$$ \text{MatchScore} = 0.55 \times \text{FitScore} + 0.45 \times \text{ReadinessScore} $$

#### A. 匹配度 (Fit Score) - 满分 100

衡量仓库与用户技能树的契合度。

$$ \text{FitScore} = 40 \times \text{DomainHit} + 35 \times \text{StackHit} + 25 \times \text{KeywordOverlap} $$

- **DomainHit (0/1)**: 项目领域是否包含用户意向领域。
- **StackHit (0/1)**: 项目技术栈是否包含用户技术栈。
- **KeywordOverlap (0.0~1.0)**: 用户关键词与项目标签/描述的重合比例。

#### B. 准备度 (Readiness Score) - 满分 100

衡量项目是否适合新人参与，基于以下四个维度加权计算：

| 维度                      | 权重 | 说明                             |
| :------------------------ | :--- | :------------------------------- |
| **Responsiveness (响应)** | 35%  | 维护者的响应速度，避免新人受挫。 |
| **Activity (活跃)**       | 20%  | 项目的生命力和增长趋势。         |
| **Supply (供给)**         | 25%  | 是否有足够的适合新人的 Issue。   |
| **Onboarding (文档)**     | 20%  | 文档的完善程度。                 |

**具体计算逻辑：**

1.  **Responsiveness (35%)**:

    - 基于 `issue_response_time`, `pr_response_time`, `issue_age`, `pr_age` 四个指标。
    - 使用全局 `10% - 90%` 分位点进行归一化 (`norm_lo`，越小越好)。
    - **权重**: Issue 响应(40%) > PR 响应(30%) > Issue 积压(20%) > PR 积压(10%)。

2.  **Activity (20%)**:

    - 基于 `activity_3m` (3 个月活跃度), `activity_growth` (增长率), `new_contributors` (新贡献者)。
    - 使用全局分位点归一化 (`norm_hi`，越大越好)。
    - **权重**: 活跃总量(45%) > 新贡献者(30%) > 增长率(25%)。

3.  **Supply (25%)**:

计算“任务供给量”：

$S = 2 \times \text{good\\_first} + 1.5 \times \text{help\\_wanted} + 1.0 \times \text{docs} + 1.0 \times \text{i18n}$
  - 对数处理后归一化：

$Score = \text{Norm}(\ln(1+S))$
  - **新鲜度修正**: 乘以 `freshness_factor` (0.6~1.0)，Issue 越新得分越高。
  - **新鲜度修正**: ...

4.  **Onboarding (20%)**:
    - README 存在: +30
    - CONTRIBUTING 存在: +40
    - PR Template 存在: +15
    - 自动提取环境搭建/测试指令 (setup/build/test): +15
    - 上限 100 分。

### 2.3 组装建议 (Assemble)

对于得分最高的 Top 1 仓库，系统会生成具体的行动计划：

1.  **Issue Board**: 提取 `good_first_issue` 或 `help_wanted` 标签的 Issue，按新鲜度排序。
2.  **Timeline**: 根据用户的每周可用时间 (`time_per_week`)，动态生成 1~4 周的任务规划。
    - 时间较少 (<5h): 侧重文档阅读和环境搭建。
    - 时间充裕 (>10h): 侧重代码贡献和 issue 认领。
3.  **Checklist**: 生成可复制的 Markdown 清单，包含阅读文档、搭建环境、运行测试等具体步骤。

---

## 3. 难度分级 (Difficulty Label)

系统根据 `ReadinessScore` 和用户时间投入自动打标难度：

- **Easy**: Readiness > 75
- **Medium**: 55 < Readiness <= 75
- **Hard**: Readiness <= 55

(注：若用户每周时间极少，会自动略微调高难度评级，提示需要更多投入)