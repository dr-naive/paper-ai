# PaperAI V1 Product Scope

> 文档状态：ACTIVE / AUTHORITATIVE  
> 版本：v2.0-draft  
> 适用对象：Codex、AI Coding Agent、PaperAI 开发者  
> 本文只定义 **PaperAI V1 做什么、不做什么、用户如何使用**。  
> 本文不定义数据库表、类名、Tool 实现或具体迁移步骤；这些由后续施工规格定义。

---

## 0. 文档优先级

PaperAI `agent-rearchitecture-v1` 后续施工以 `docs/spec-v2/` 为当前权威规范。

旧文档：

- `docs/PROJECT_AGENT_IMPLEMENTATION_SPEC.md`
- `docs/PROJECT_AGENT_UPGRADE_CONTEXT.md`

应视为历史设计与历史代码快照，不再作为当前施工合同。

若旧文档与 `docs/spec-v2/` 冲突，以 `docs/spec-v2/` 为准。

---

# 1. 产品定位

## 1.1 核心用户

PaperAI V1 的核心用户是：

- 大学生
- 研究生
- 需要完成课程论文、毕业论文、研究论文的学习者

V1 优先服务“需要完成一篇论文”的真实工作，而不是面向专业科研机构建立大型文献基础设施。

## 1.2 长期目标

PaperAI 的长期目标是：

> 一个围绕科研项目组织、将找论文、读论文、写论文连接起来的一站式 AI 科研工作平台。

这是长期方向，不代表 V1 必须一次实现完整科研生命周期。

## 1.3 V1 核心目标

V1 只优先打通一条高价值主链：

```text
创建 Project
    ↓
明确研究主题
    ↓
发现合适论文
    ↓
收藏 / 下载 / 导入
    ↓
阅读已导入论文
    ↓
沉淀可供项目使用的论文信息与证据
    ↓
进入论文写作
    ↓
AI 基于当前 Project 已导入论文辅助生成或修改段落
    ↓
真实引用
    ↓
引用验证
```

V1 的成功标准不是“Agent 功能很多”，而是用户能连续完成这条主链。

---

# 2. 产品原则

## 2.1 用户成果优先于 Agent 行为

用户来到 PaperAI 是为了完成论文，不是为了观察 Agent。

前端禁止把以下工程概念作为用户核心信息：

- Tool
- Skill
- ReAct
- Harness
- Planner
- Executor
- SubAgent
- raw chain-of-thought
- 原始 tool arguments / tool results

用户可以看到可理解的执行阶段，例如：

- 正在明确检索需求
- 正在搜索相关论文
- 正在检查结果相关性
- 正在补充检索
- 正在查找支持当前段落的论文证据
- 正在验证引用

## 2.2 确定性能力不要强行 Agent 化

适合普通程序 / workflow 的能力：

- PDF 解析
- Chunk
- Embedding
- Indexing
- 固定字段过滤
- 年份过滤
- 语言过滤
- DOI / metadata 规范化
- 文件下载
- 文档导出
- 引用格式化
- schema validation

Agent 负责不确定判断：

- 帮用户澄清模糊研究需求
- 生成搜索策略
- 生成多个搜索 Query
- 判断搜索结果是否偏题
- 判断是否需要追加搜索
- 在已导入论文中判断哪些与当前写作任务相关
- 决定需要检索什么 Evidence
- 组织写作内容

## 2.3 不允许为了“显得强”增加功能

任何新增功能必须回答：

1. 用户什么时候需要它？
2. 它解决什么具体问题？
3. 用户完成后获得什么？
4. 如果不做，V1 主链是否受影响？

无法回答则不进入 V1。

## 2.4 宁可少，不允许虚构

搜索结果不足 10 篇时，不允许 Agent 编造论文凑数。

证据不足时，不允许 Agent 生成看似确定但无法被真实论文支持的学术结论。

---

# 3. 产品一级结构

PaperAI V1 保留两条相互独立的产品路径。

```text
PaperAI
├── 独立论文阅读
│   └── 保留当前已有阅读模式
│
└── Projects
    └── Project
        ├── Overview
        ├── Discover
        ├── Papers
        └── Writing
```

## 3.1 独立论文阅读

现有独立论文上传、阅读、问答能力保留。

V1 不要求：

- 将独立阅读历史自动并入 Project
- 将独立论文一键转入 Project
- 一个 Paper 同时跨多个 Project 的高级管理交互

这些可作为后续优化。

## 3.2 Project

Project 是 V1 新主线的组织单位。

Project 用于串联：

```text
Discover → Papers → Writing
```

Project 不等于传统项目管理工具。

不加入：

- 截止时间管理
- 甘特图
- 任务负责人
- 复杂进度管理
- 团队协同

---

# 4. Project 创建

## 4.1 必填字段

创建 Project 时必须填写：

- 项目名称
- 研究主题

示例：

```text
项目名称：
生成式 AI 对大学生自主学习的影响

研究主题：
研究生成式 AI 在高等教育环境中对大学生自主学习能力的影响
```

## 4.2 可选字段

可提供用于逐渐缩小研究范围的可选信息：

- 学科领域
- 研究对象
- 研究问题
- 研究目标
- 关键词
- 方法 / 技术方向
- 用户补充说明

原则：

> 这些信息用于帮助 Agent 更准确理解研究范围，而不是做项目管理。

不加入：

- 截止时间
- 目标字数
- 项目预算
- 管理型字段

用户可以先仅填写名称和主题，后续随着研究逐渐明确再补充。

## 4.3 创建完成后的默认入口

创建成功后进入 `Project Overview`。

Overview 第一版保持轻量，核心提供：

- 项目名称
- 研究主题 / 主要研究信息
- 开始找论文
- 查看项目论文
- 开始 / 继续写作

允许显示少量最近活动，但不做复杂 Dashboard。

---

# 5. Literature Discovery

## 5.1 产品目标

文献发现解决的问题不是：

> “我已经知道某篇论文的标题，帮我搜出来。”

而是：

> “我大概知道我要研究什么，但不知道应该读哪些论文。”

PaperAI 应帮助用户从模糊研究意图走到一组可以实际阅读的候选论文。

## 5.2 两阶段搜索

Literature Discovery 必须分为两个阶段。

### 阶段 A：需求澄清

形式：

- 对话式
- Agent 主导
- 允许多轮

目标：

把用户的模糊想法整理为明确的 `Search Intent`。

例如：

```text
用户：
我想研究大语言模型对大学生学习的影响。

Agent：
进一步确认研究对象、关注指标、技术范围等。

最终：
查找生成式 AI / ChatGPT 对大学生自主学习能力影响的实证研究，
重点关注高等教育场景。
```

阶段完成后，Agent 自动生成一份搜索描述，并填入搜索表单。

用户必须可以手动修改。

### 阶段 B：实际检索

实际检索不依赖一个巨大 Prompt。

搜索参数由两部分组成：

#### 结构化固定条件

第一版至少考虑：

- 年份
- 语言
- 学科 / 领域
- 文献类型

能作为搜索 Provider 的确定性 filter 时必须直接作为 API 参数，不得仅写入自然语言 Prompt。

#### 自然语言检索需求

用于表达难以固定字段化的细节要求。

---

# 6. Agent 在搜索中的职责

Agent 不负责替代学术数据库。

真实搜索由 Academic Search Provider / API 执行。

Agent 负责：

```text
Search Intent
    ↓
制定 Query Strategy
    ↓
生成一个或多个 Query
    ↓
调用搜索能力
    ↓
检查结果
    ↓
判断结果是否偏题 / 不足
    ↓
必要时修改 Query 再搜索
    ↓
合并、去重
    ↓
返回候选论文
```

V1 必须设置明确预算，防止无限检索。

建议最大搜索轮次在施工规格中固定为有限值。

---

# 7. 搜索结果

## 7.1 数量

V1 每次搜索目标返回：

**10 篇**

如果符合条件的真实论文不足 10 篇，则如实返回实际数量。

## 7.2 返回形式

禁止只返回一段文本列表。

后端必须返回结构化论文对象，由前端自动生成论文卡片。

## 7.3 布局

Desktop：

**一行两张卡片。**

卡片默认保持统一布局。

## 7.4 摘要

若学术数据源能提供完整 Abstract：

- 后端保存 / 返回完整 Abstract
- 不允许为了 UI 在后端截断为 500 字符等固定长度
- 前端默认显示 4 行
- 提供“展开 / 收起”

默认状态卡片排列整齐。

用户主动展开后允许卡片高度变化。

## 7.5 卡片主要信息

第一版至少包含：

- 标题
- 作者
- 年份
- Venue / Journal / Conference（有则显示）
- Abstract
- 基础元数据
- AI 推荐理由（数据可得且结果稳定时显示）
- 详情
- 收藏
- 下载
- 导入

排序和“权威性评分”暂不作为 V1 强制核心能力。

---

# 8. 搜索结果的四个操作

四个操作必须保持固定位置，不因资源状态改变布局。

```text
详情 | 收藏 | 下载 | 导入
```

## 8.1 详情

点击后优先在 PaperAI 内部 Drawer / Detail View 展示：

- 标题
- 作者
- 年份
- DOI
- 完整 Abstract
- 来源信息
- 可用链接

提供“查看原始页面”。

不要强迫用户一开始就离开 PaperAI。

## 8.2 收藏

收藏的作用是：

> 对搜索结果进行二次筛选。

收藏不等于：

- 下载
- 导入
- 全文解析

只保存必要 metadata 与链接。

搜索结果页至少可以区分：

- 全部
- 已收藏

## 8.3 下载

下载表示：

> 将可获得的 PDF 下载到用户本地。

若没有合法可用的 PDF 地址：

- 按钮保留
- 按钮 disabled / 置灰
- Hover Tooltip：`暂无可用下载链接`

## 8.4 导入

“导入”表示真正进入当前 Project 的论文工作区：

```text
搜索结果
    ↓
获取可用 PDF
    ↓
进入现有 PaperAI 解析流程
    ↓
完成解析与索引
    ↓
加入当前 Project Papers
```

导入不是 metadata 收藏。

若没有可获得全文：

- 导入按钮保留
- disabled / 置灰
- Tooltip 说明无法获取全文

---

# 9. Project Papers

Project Papers 只管理 **已经正式导入当前 Project** 的论文。

它与 Discover 中的“收藏结果”是不同概念。

V1 倾向使用信息密度更高的列表 / 表格，而不是继续使用大型卡片。

核心能力：

- 查看当前项目已导入论文
- 上传本地 PDF 到当前项目
- 打开论文阅读器
- 显示基本阅读状态（以现有能力为准）

## 9.1 Reader 约束

现有 `PaperReader` V1 不重做。

原则：

> 保持现有成熟论文阅读体验，只做 Project 主链所需的最小连接。

不得为了新的 Project / Agent 架构推倒 Reader。

---

# 10. Project Context

Project 必须建立可供后续 Agent 使用的长期研究上下文。

它不是一个无限增长的聊天记录。

建议概念分层：

```text
Project Context
├── Project Profile
├── Literature Memory
├── Paper Profiles
├── Evidence
└── Writing Context
```

## 10.1 Project Profile

记录当前研究“究竟在研究什么”：

- 研究主题
- 学科领域
- 研究对象
- 研究问题
- 研究目标
- 关键词
- 方法方向
- 用户明确补充信息

## 10.2 Literature Memory

记录有长期价值的检索信息，例如：

- 关键检索意图
- 已使用的重要关键词
- 用户明显偏好的方向
- 用户明确排除的方向
- 已收藏 / 导入的重要论文关系

不保存所有搜索结果全文。

## 10.3 Paper Profile

论文正式导入并解析成功后，自动生成轻量结构化 Paper Profile。

建议内容：

- 研究主题
- 研究问题
- 研究对象
- 研究方法
- 数据集 / 样本（有则记录）
- 主要结果
- 核心结论
- 主要贡献
- 局限性
- 关键词
- 与当前 Project 的关系

目的：

> 让 Agent 快速判断“哪篇论文值得进一步检索 Evidence”。

Paper Profile 不是最终引用证据。

## 10.4 用户行为

V1 不要求改造 Reader 新增复杂高亮 / 笔记功能。

如果现有系统已经产生可靠的用户笔记、已保存 Evidence 等数据，可以作为高权重 Context 使用。

普通阅读聊天历史：

- 可以继续保存用于恢复会话
- 默认不等于 Project Memory
- 不应整段无差别塞入长期 Context

## 10.5 Evidence

Evidence 表示：

> 论文中能够实际支撑某个写作主张的可追溯来源。

至少需要关联：

- Project
- Paper
- 原文 snippet
- page / section / chunk 等定位信息（可得时）
- normalized claim
- 来源 metadata

Paper Profile 用来“找相关论文”。

Evidence 用来“支撑真正写作和引用”。

---

# 11. Context 调用原则

不允许每次把：

- 所有聊天
- 所有论文全文
- 所有 Memory
- 整篇正在写的论文

全部塞给模型。

正确模式：

```text
Agent 判断当前需要什么类型的信息
        ↓
Context / Retrieval 层负责找到具体相关内容
        ↓
控制上下文规模
        ↓
提供给 Agent
```

例如写作：

```text
当前章节
+
用户请求
+
Project Profile
+
相关 Paper Profiles
+
相关 Evidence
+
必要的附近正文
```

---

# 12. Writing Workspace

## 12.1 产品定位

写作是 PaperAI V1 的核心页面之一。

它必须是真正可以持续写论文的编辑区域，而不是“AI 输出文本页面”。

整体体验采用：

> 博客 / Notion / Medium / Typora 类现代编辑体验 + 论文专用能力。

不追求 V1 复刻完整 Microsoft Word。

## 12.2 基础布局

Desktop V1：

```text
┌─────────────┬───────────────────────────────┬────────────────────┐
│ 论文结构    │ 正文编辑器                    │ AI 写作助手        │
│             │                               │                    │
│ Outline     │ Tiptap / 正式文档             │ Conversation       │
│             │                               │                    │
└─────────────┴───────────────────────────────┴────────────────────┘
```

建议：

- 左侧约 220px
- 中间自适应
- 右侧约 340–380px
- AI 区允许折叠
- Desktop First

现有 Tiptap / WritingDocument / Revision 能力优先复用。

## 12.3 论文层级

正常支持：

- 文档标题
- Heading
- 多级章节
- Outline 导航

不额外发明复杂的“论文流程节点”。

## 12.4 基础编辑器能力

至少保留 / 支持：

- Heading
- Bold
- Italic
- Blockquote
- List
- Link（技术允许时）
- 图片（按现有能力和开发量）
- 表格（按现有能力和开发量）
- 公式
- 撤销 / 重做

论文增强能力优先：

- Citation
- Footnote（可作为后续小阶段）
- 公式
- 图表题注（可作为后续小阶段）

---

# 13. Writing Agent 交互

右侧 Agent 是写作上下文助手。

不要在编辑器工具栏堆大量固定 AI 按钮。

## 13.1 用户选中正文

右侧必须能感知：

```text
当前：2.1 国内外研究现状
已选中 126 字
```

用户在 Agent 输入：

```text
帮我润色得更学术，但不要改变原意。
```

Agent 返回修改结果。

固定快捷操作：

- 替换选中内容
- 复制

替换必须由用户明确点击后执行。

AI 不允许自行覆盖正文。

## 13.2 用户未选中正文

右侧显示当前章节上下文。

用户可以输入：

```text
根据我已经导入的论文，写一段生成式 AI 对大学生自主学习积极影响的研究现状。
```

Agent 基于当前 Project 生成一个段落。

V1 快捷操作：

- 复制

暂不强制提供“自动插入光标位置”。

---

# 14. AI 生成内容的引用

这是 V1 必须能力，不是后续锦上添花。

## 14.1 引用来源限制

Writing Agent 自动引用只能来自：

> 当前 Project 中已经正式导入、完成解析、可检索的真实论文。

V1 不允许直接引用：

- Discover 搜索结果但未导入的论文
- 仅收藏的 metadata
- 模型凭预训练记忆想起的论文
- 无法定位的网页内容

## 14.2 写作生成链

推荐固定主流程：

```text
用户写作请求
    ↓
读取当前章节 / selection / 附近正文
    ↓
读取 Project Profile
    ↓
通过 Paper Profile 找候选论文
    ↓
在候选论文全文中检索 Evidence
    ↓
生成段落 + Citation Mapping
    ↓
Citation Verification
    ↓
通过后返回用户
```

核心流程不得允许 Agent 随意跳过 Citation Verification。

## 14.3 Citation 必须结构化

内部不得只保存纯文本 `[1]`。

Citation 至少关联：

- paper_id
- evidence_id（有证据引用时）
- citation key / stable identifier

显示格式由 Citation Style 决定。

---

# 15. Citation Verification

自动检查引用是 V1 必须能力。

系统必须检查至少：

1. Citation 是否关联真实 Project Paper
2. Evidence 是否存在并属于当前 Project
3. Evidence 的 Paper 是否与 Citation Paper 匹配
4. 当前主张是否有合理证据支持

如果验证失败：

- 不得把不可靠结果伪装成已验证内容
- 可以重新检索 Evidence
- 可以降低表述强度
- 可以提示用户证据不足

验证机制具体如何从当前 lexical gate 演进，由后续 Evidence 施工规格定义。

---

# 16. Citation Style

V1 支持常见格式，优先：

- GB/T 7714
- APA
- IEEE

内部 Citation 与显示 Style 必须解耦。

改变 Style 不应该要求重新生成论文正文。

---

# 17. 导入 / 导出

## 17.1 导入

必须保留现有本地 PDF 上传。

Project Papers 应允许用户将本地 PDF 导入当前项目。

Literature Discovery 的远程导入是额外来源，不替代本地上传。

## 17.2 导出

写作最终结果应支持导出。

V1 优先级：

1. DOCX
2. PDF / 其他格式按现有能力和实施成本推进
3. Markdown / LaTeX 若已有稳定能力可继续保留

现有 export 能力不得因 Writing V2 改造而无故破坏。

---

# 18. 前端全局信息架构

V1 推荐：

```text
Global Shell
├── Home / Projects
├── Independent Reader / Library
├── Settings
│
└── Project
    ├── Overview
    ├── Discover
    ├── Papers
    └── Writing
```

## 18.1 Global Sidebar

推荐左侧全局导航：

```text
PaperAI

首页
项目
独立阅读

────────
最近项目
────────

设置
用户
```

项目内部使用顶部二级导航：

```text
[概览] [文献发现] [项目论文] [写作]
```

不要出现两套重型 Sidebars。

## 18.2 视觉方向

总体风格：

- 浅色
- 克制
- 专业
- 高信息密度但不拥挤
- Desktop First

避免：

- 大面积渐变
- 发光 Agent
- 大量彩色状态
- 过度圆角
- 无意义动画
- 大量 Dashboard KPI

视觉应更接近专业生产力工具，而不是消费娱乐 App。

---

# 19. Agent Runtime 产品约束

底层技术细节由后续架构文档定义，但 V1 产品层必须遵守：

1. 保持一个主 Research Agent 思路，不建立通用多 Agent 平台。
2. 核心业务场景使用固定 Workflow + Agent 有限决策。
3. Agent 可自主决定搜索 Query、是否补搜、需要什么 Context。
4. 确定性验证、过滤、引用校验不得交给自由 Agent 决策。
5. 执行必须有上限与失败边界。
6. 用户看到的是可理解阶段，不是内部执行日志。
7. 失败时宁可返回更少真实结果，也不得生成假数据。

---

# 20. V1 明确不做

以下内容即使当前代码已有原型，也不应因此变成 V1 主功能：

- Research Map 作为一级页面
- Reading Plan 作为一级页面
- Evidence Matrix 作为一级页面
- Experiment Design 作为一级页面
- Experiment Results 工作台
- Submission Suggestion
- 独立 Activity Center
- Agent Center
- Skill 选择器
- Tool 面板
- 完整 Zotero 替代品
- 自建海量论文数据库
- 团队科研协作
- 复杂项目管理
- 独立阅读与 Project 的深度互通
- 写作过程中主动联网搜索并自动引用新论文
- 完整 Word 页面排版引擎
- 自动生成整篇论文作为 V1 核心能力
- 复杂论文权威性评分模型
- 多 Agent 平台

这些代码如已存在，应在迁移文档中决定：

- 保留底层兼容
- 隐藏 UI
- 冻结
- 后续删除

而不是继续扩展。

---

# 21. V1 核心页面

最终 V1 主页面集合应保持精简：

```text
Home / Projects
Independent Paper Library / Reader

Project
├── Overview
├── Discover
├── Papers
└── Writing
```

普通用户不需要看到工程内部模块。

---

# 22. V1 主链验收

只有以下用户旅程完整可用，才可以称 V1 主线完成：

## Journey A：文献发现

1. 用户创建 Project。
2. 填写项目名称和研究主题。
3. 进入 Overview。
4. 进入 Discover。
5. 与 Agent 对话澄清搜索需求。
6. Agent 将结果填入可编辑搜索表单。
7. 用户调整年份 / 语言 / 领域等固定条件。
8. 点击搜索。
9. Agent / Search Workflow 完成有限多轮真实检索。
10. 页面自动生成最多 10 篇真实论文卡片。
11. 用户可以查看详情。
12. 用户可以收藏。
13. 有 PDF 时可以下载。
14. 有可获取全文时可以导入。
15. 无全文时按钮保持但明确 disabled。

## Journey B：项目阅读

1. 用户从 Discover 导入论文或在 Project Papers 上传本地 PDF。
2. PaperAI 完成现有解析流程。
3. 论文出现在 Project Papers。
4. 用户可以进入现有 PaperReader 正常阅读。
5. 不因 Project 重构破坏原有 Reader / RAG / citation 能力。

## Journey C：论文写作

1. 用户进入 Writing。
2. 创建 / 打开正式 WritingDocument。
3. 左侧可以查看论文结构。
4. 中间可以正常编辑正文。
5. 右侧 Agent 知道当前章节。
6. 用户选中文字并给出修改要求。
7. Agent 返回修改文本。
8. 用户可一键替换或复制。
9. 用户不选中文本，要求生成一段。
10. Agent 从当前 Project 已导入论文中检索真实 Evidence。
11. Agent 返回带真实 Citation Mapping 的段落。
12. 系统执行 Citation Verification。
13. 引用失败时明确标记，不允许假装通过。
14. 文档可以保存 revision。
15. 核心导出能力保持可用。

---

# 23. V1 成功标准

V1 不以“实现了多少 Agent Tool / Skill”计分。

成功应表现为：

> 用户能在一个 Project 中从“我不知道该读什么”走到“我找到并读了需要的论文”，再走到“我可以基于这些真实论文写出带可验证引用的论文段落”。

如果这个流程仍然需要用户频繁：

- 复制论文标题去其他网站重新搜索
- 把资料手动复制给 ChatGPT
- 自己告诉 AI 每篇论文讲了什么
- 检查 AI 是否编造引用
- 把 AI 输出复制到另一个完全独立的写作工具才能继续

则 PaperAI V1 仍没有完成核心目标。
