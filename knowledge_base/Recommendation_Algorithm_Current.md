# 开源新人项目推荐算法（当前实现）

## 1. 概述

该算法根据开发者的兴趣领域、技术栈、关键词和每周可投入时间，推荐适合参与的开源项目，并进一步生成 Issue 看板、贡献时间线和可复制的上手清单。

当前实现位于：

- 服务编排：`backend/app/services/newcomer_plan.py`
- 评分逻辑：`backend/app/services/newcomer_scoring.py`
- GitHub 数据采集：`backend/app/services/github_fetch.py`

算法采用 **召回（Recall）→ 评分（Score）→ 组装（Assemble）** 三阶段流程。

核心总分保持旧版结构：

$$
\text{MatchScore} = 0.55 \times \text{FitScore} + 0.45 \times \text{ReadinessScore}
$$

其中：

- `FitScore`：项目与用户兴趣、技术栈和关键词的匹配程度；
- `ReadinessScore`：项目对新人实际参与的友好程度；
- `MatchScore`：最终排序分，范围为 0–100 分。

---

## 2. 用户输入

推荐请求包括：

| 输入 | 说明 |
| ---- | ---- |
| `domains` | 感兴趣的项目领域，可多选 |
| `stacks` | 熟悉的技术栈，可多选 |
| `keywords` | 额外关键词，空格或逗号分隔 |
| `time_per_week` | 每周可投入时间，例如 `1-2h`、`3-5h`、`6-10h`、`10+h` |
| `top_n` | 请求的推荐数量，接口允许 1–12 个 |

输入会先去重、清理空白，并统一转换为小写关键词。

---

## 3. 召回阶段（Recall）

### 3.1 候选数据集

系统从启用状态为 `curated` 的完整项目目录中读取候选仓库：

1. 读取 `RepoCatalog`；
2. 关联 `RepositoryDataStatus`；
3. 只保留 `scope = curated` 且 `enabled = true` 的仓库；
4. 按仓库全名稳定排序；
5. 单次召回最多保留 **400 个候选项目**。

候选项目的匹配字段由以下信息合并而成：

- 领域：`domains`、`seed_domain`，为空时回退到 `topics`；
- 技术栈：`stacks`、主语言、`tags`、`topics`；
- 关键词文本：`tags` 与项目描述。

### 3.2 领域和技术栈别名

系统对常见输入提供别名扩展，例如：

| 用户输入 | 可匹配别名示例 |
| -------- | -------------- |
| `ai_ml` | `ai`、`ai-data`、`machine-learning`、`deep-learning` |
| `backend` | `backend`、`backend-enterprise` |
| `cloud_infra` | `cloud`、`cloud-observability`、`cloud-native` |
| `javascript` | `javascript`、`typescript`、`js`、`ts` |
| `nodejs` | `nodejs`、`node.js`、`javascript`、`typescript` |
| `react` | `react`、`reactjs` |
| `python` | `python` |
| `go` | `go`、`golang` |
| `cpp` | `c`、`c++`、`cpp` |

匹配时会移除非字母数字、`+`、`#`、`.` 以外的符号，并进行大小写归一化。

### 3.3 严格召回（Strict Match）

严格召回要求：

```text
领域命中 AND 技术栈命中 AND 关键词命中（如果用户提供关键词）
```

如果用户没有提供某一类条件，则该条件不参与限制。例如用户没有填写关键词时，不会因为缺少关键词而淘汰项目。

### 3.4 放宽召回（Relaxed Match）

当严格匹配不足时，系统继续扫描未入选项目：

```text
（领域命中 OR 技术栈命中）AND 关键词命中（如果用户提供关键词）
```

严格匹配结果优先保留，随后追加放宽匹配结果，最终截取前 400 个候选。

关键词召回使用项目标签或描述中的子串命中；进入评分阶段后，关键词分数使用更严格的 token 交集计算。

---

## 4. 评分阶段（Score）

### 4.1 匹配度 Fit Score

匹配度由领域、技术栈和关键词三部分组成：

$$
\text{FitScore} =
\frac{40 \times D + 35 \times S + 25 \times K}
{\text{参与计算的权重总和}} \times 100
$$

其中：

- $D$：领域命中为 1，否则为 0；
- $S$：技术栈命中为 1，否则为 0；
- $K$：关键词重合比例，范围为 0–1。

关键词重合比例为：

$$
K = \frac{|\text{UserKeywords} \cap \text{RepoTokens}|}
{|\text{UserKeywords}|}
$$

`RepoTokens` 来自项目标签和描述文本的英文数字 token。没有提供某一类输入时，对应权重会被移除并对剩余权重重新归一化；如果三类输入都为空，`FitScore = 0`。

---

### 4.2 新人就绪度 Readiness Score

新人就绪度由四个子维度组成：

| 子维度 | 权重 | 说明 |
| ------ | ---- | ---- |
| **Responsiveness（响应）** | 35% | 项目对 Issue/PR 的响应速度和积压情况 |
| **Activity（活跃）** | 20% | 项目的近期活动、增长和新贡献者 |
| **Supply（任务供给）** | 25% | 可供新人参与的 Issue 数量和新鲜度 |
| **Onboarding（上手）** | 20% | README、贡献指南、PR 模板和环境命令 |

缺失的子维度不会直接填充为 0，而是从最终权重中移除并对剩余子维度重新归一化；如果所有子维度均不可用，`ReadinessScore = 0`。

#### A. Responsiveness（35%）

首先使用当前候选项目集合计算 10% 和 90% 百分位点。时间类指标越小越好，使用：

$$
\text{NormLo}(x) = \text{clamp}\left(1 - \frac{x-P_{10}}{P_{90}-P_{10}}, 0, 1\right)
$$

四个输入及子权重为：

$$
\text{Responsiveness} =
0.40 \times \text{NormLo}(\text{IssueResponse})
+ 0.30 \times \text{NormLo}(\text{PRResponse})
+ 0.20 \times \text{NormLo}(\text{IssueAge})
+ 0.10 \times \text{NormLo}(\text{PRAge})
$$

归一化结果最后转换为 0–100 分。

#### B. Activity（20%）

活动类指标越大越好，使用：

$$
\text{NormHi}(x) = \text{clamp}\left(\frac{x-P_{10}}{P_{90}-P_{10}}, 0, 1\right)
$$

$$
\text{Activity} =
0.45 \times \text{NormHi}(\text{Activity}_{3m})
+ 0.25 \times \text{NormHi}(\text{ActivityGrowth})
+ 0.30 \times \text{NormHi}(\text{NewContributors})
$$

其中：

- `Activity_3m`：最近三个月 Activity 之和；
- `ActivityGrowth`：

$$
\frac{\text{Activity}_{3m} - \text{Activity}_{prev3m}}
{\text{Activity}_{prev3m}}
$$

- `NewContributors`：最新的新贡献者指标。

#### C. Supply（25%）

任务供给量为：

$$
S =
2.0 \times \text{good\_first}
+ 1.5 \times \text{help\_wanted}
+ 1.0 \times \text{docs}
+ 1.0 \times \text{i18n}
$$

先进行对数压缩：

$$
S_{base} = \ln(1+S)
$$

再使用候选项目集合的 10% 和 90% 百分位点归一化，并应用新鲜度修正：

$$
\text{Supply} =
100 \times \text{NormHi}(S_{base}) \times \text{FreshnessFactor}
$$

新鲜度因子为：

$$
\text{FreshnessFactor} =
\text{clamp}\left(e^{-\text{days}/30}, 0.6, 1.0\right)
$$

若没有更新时间，默认新鲜度因子为 0.6。

#### D. Onboarding（20%）

上手分按文档和命令覆盖情况计算：

| 条件 | 得分 |
| ---- | ---- |
| README 存在 | +30 |
| CONTRIBUTING.md 存在 | +40 |
| PR Template 存在 | +15 |
| 抽取到 setup/build/test/commands 命令 | +15 |

上手分上限为 100 分。

命令抽取优先读取 README、CONTRIBUTING 和 PR 模板中的代码块，也会回退扫描普通文本。支持识别 `git`、`npm`、`pnpm`、`yarn`、`pip`、`poetry`、`pytest`、`make`、`go test` 和 `go build` 等命令。

---

### 4.3 最终匹配分

$$
\text{MatchScore} =
0.55 \times \text{FitScore}
+ 0.45 \times \text{ReadinessScore}
$$

所有候选项目按 `MatchScore` 降序排列。默认最多返回 12 个项目。

每个项目还会保存：

- `fit_score`；
- `readiness_score`；
- `match_score`；
- `responsiveness`；
- `activity`；
- `trend_delta`；
- 命中的领域和技术栈；
- 最多 5 条推荐理由。

---

## 5. 难度分级（Difficulty Label）

难度由 `ReadinessScore` 和每周可投入时间共同决定。

### 默认时间档位

| 标签 | 条件 |
| ---- | ---- |
| **Easy** | Readiness ≥ 75 |
| **Medium** | 55 ≤ Readiness < 75 |
| **Hard** | Readiness < 55 |

### 每周 3–5 小时

| 标签 | 条件 |
| ---- | ---- |
| **Easy** | Readiness ≥ 70 |
| **Medium** | 50 ≤ Readiness < 70 |
| **Hard** | Readiness < 50 |

### 每周 6 小时及以上

| 标签 | 条件 |
| ---- | ---- |
| **Easy** | Readiness ≥ 65 |
| **Medium** | 45 ≤ Readiness < 65 |
| **Hard** | Readiness < 45 |

时间越充足，系统允许更低的就绪度项目进入 Easy/Medium 档位；这不会改变项目本身的 `ReadinessScore`。

---

## 6. 组装阶段（Assemble）

### 6.1 推荐项目列表

系统返回排序后的前 12 个项目；若没有召回候选，则返回空的推荐列表、Issue 看板、时间线和清单。

### 6.2 Issue Board

对 Top 1 项目生成四类任务看板：

- `good_first_issue`；
- `help_wanted`；
- `docs`；
- `i18n`。

每条任务的排序分为：

$$
\text{IssueTaskScore} =
0.50 \times \text{LabelPriority}
+ 0.30 \times \text{Freshness}
+ 0.20 \times \frac{\text{ReadinessScore}}{100}
$$

标签优先级为：

| 类型 | LabelPriority |
| ---- | -------------: |
| `good_first` | 1.0 |
| `docs` | 0.8 |
| `help_wanted` | 0.7 |
| `i18n` | 0.6 |
| 其他 | 0.6 |

每个类别最多返回 20 条任务。

### 6.3 贡献时间线

Top 1 项目默认生成以下步骤：

1. **Fork**：在 GitHub 完成 Fork；
2. **Clone**：克隆项目到本地；
3. **Setup**：优先使用仓库文档抽取的安装命令；
4. **Build & Test**：优先使用仓库文档抽取的构建和测试命令；
5. **First PR**：创建分支、提交代码、发起 PR、关联 Issue、请求评审。

如果仓库没有抽取到命令，系统按技术栈提供通用模板：

- Python：创建虚拟环境、安装 `requirements.txt`、运行 `pytest`；
- Go：运行 `go mod download`、`go test ./...`；
- 其他技术栈：默认使用 `npm install`、`npm run build`、`npm test`。

### 6.4 可复制清单

系统将时间线渲染为 Markdown 清单，包含：

- 每个阶段的标题；
- 可执行命令或 GitHub 地址；
- 文档抽取或通用模板的来源说明；
- 用户的时间档位。

针对单个 Issue 的任务包则进一步生成 Setup、Build、Test 和 PR 步骤，并包含分支命名、提交、推送和关联 Issue 的操作。

---

## 7. 数据流与缺失处理

1. **读取候选目录**：读取已启用的精选仓库目录；
2. **加载最新指标**：Issue/PR 响应、Issue/PR 年龄、新贡献者、OpenRank 和 Activity 历史；
3. **加载任务与文档**：读取任务分类、更新时间、README、CONTRIBUTING、PR 模板和抽取命令；
4. **计算候选集合基准**：对响应、活跃度和任务供给计算 P10/P90；
5. **评分与排序**：计算 Fit、Readiness 和 Match；
6. **组装输出**：生成推荐列表、Top 1 任务看板、时间线和清单。

当指标缺失时：

- 分位点归一化无法计算时，对应子项记为缺失；
- Readiness 会对可用子维度重新归一化；
- 缺少 Issue 统计时，任务供给会降为低分；
- 缺少文档时，Onboarding 分为 0；
- 缺少任务更新时间时，FreshnessFactor 为 0.6；
- 没有候选项目时，不生成虚构推荐。

---

## 8. 与旧版推荐算法的关系

- `MatchScore = 0.55 × FitScore + 0.45 × ReadinessScore` 保持不变；
- Readiness 的四维权重保持为 35%/20%/25%/20%；
- 当前版本将召回上限调整为 400 个精选候选；
- 当前版本使用候选集合 P10/P90 做动态归一化；
- 当前版本按每周时间调整难度阈值；
- 当前版本的任务板按标签优先级、新鲜度和新人就绪度共同排序；
- 旧版文档中的“默认召回 150 个”“不足 6 个时填充”及“1–4 周时间规划”不代表当前实现。