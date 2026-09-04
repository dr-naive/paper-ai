# PaperAI V1 Frontend Design System and Pages Specification

> 文档状态：ACTIVE / AUTHORITATIVE
> 版本：v2.0-draft
> 适用对象：Codex、AI Coding Agent、PaperAI 前端开发者
> 本文定义 PaperAI V1 的全局前端信息架构、页面布局、组件层次、交互状态、视觉规则、响应式与前端实现边界。
> 本文的目标是：**Codex 负责实现，不负责重新做产品设计。**

---

# 0. 前端设计目标

PaperAI 是科研生产力工具，不是消费娱乐 App。

V1 视觉目标：

- 专业
- 克制
- 高信息密度但不拥挤
- 长时间使用不疲劳
- 功能主线清晰
- 页面结构稳定
- Desktop First

参考的是现代生产力工具的设计原则，而不是照搬具体产品。

可借鉴：

- Notion：内容层级与编辑体验
- Linear：克制的信息密度和状态表达
- Claude / ChatGPT：对话区可读性
- Medium / Typora：正文阅读与写作宽度
- Zotero：论文列表的信息密度

---

# 1. 全局信息架构

V1：

```text
PaperAI
├── Home / Projects
├── Independent Reading
├── Settings
│
└── Project
    ├── Overview
    ├── Discover
    ├── Papers
    └── Writing
```

禁止在一级导航加入：

- Research Map
- Evidence Matrix
- Experiment Design
- Agent Center
- Tool Center
- Skills
- Activity
- Reading Plan

---

# 2. Global Shell

推荐结构：

```text
┌──────────────────────────────────────────────────────────────────┐
│ Global Sidebar │ Main Content                                    │
│                │                                                 │
│                │                                                 │
│                │                                                 │
└──────────────────────────────────────────────────────────────────┘
```

## Sidebar Width

Desktop 默认：

```text
180px
```

允许范围：

```text
176–188px
```

折叠后：

```text
56–64px
```

---

# 3. Global Sidebar

结构：

```text
PaperAI

首页
项目
独立阅读

────────────

最近项目
Project A
Project B
Project C

────────────

设置
用户
```

## 规则

- 一级导航始终固定
- 最近项目最多显示 5 个
- 更多项目进入 Projects 首页
- 当前项目高亮
- 不显示项目内部 Overview / Discover / Writing 导航

---

# 4. Sidebar Visual

建议：

```text
background: near-white / light neutral
border-right: 1px solid subtle gray
```

不要：

- 深色大侧栏 + 内容浅色
- 大面积品牌渐变
- 每个菜单不同颜色

菜单 item：

```text
height: 36–40px
border-radius: 6–8px
```

active：

- 浅强调背景
- 主文字加深
- 可有 2px 左侧强调线或图标强调

---

# 5. Main Content

Main：

```text
min-width: 0
flex: 1
background: page background
```

普通页面内容最大宽度：

```text
1200–1320px
```

Discover 结果页可稍宽。

Writing 页面不使用普通 max-width，由三栏占满。

---

# 6. Project Header

进入 Project 后，Main 顶部显示 Project Header。

结构：

```text
Project Name
Research Topic / secondary text

[概览] [文献发现] [项目论文] [写作]
```

建议高度：

```text
72–88px
```

二级导航采用 Tabs / underline nav。

不要再增加 Project Sidebar。

---

# 7. Project Navigation

固定四项：

```text
概览
文献发现
项目论文
写作
```

Route：

```text
/projects/:projectId/overview
/projects/:projectId/discover
/projects/:projectId/papers
/projects/:projectId/writing
```

active tab：

- 主文字
- 底部 2px indicator

---

# 8. Color System

V1 不要求完全重做现有 design tokens。

若项目已有稳定 CSS variables，优先映射。

建议语义 token：

```text
--bg-page
--bg-surface
--bg-subtle

--text-primary
--text-secondary
--text-muted

--border-default
--border-strong

--accent
--accent-hover
--accent-subtle

--success
--warning
--danger
--info
```

---

# 9. 推荐色彩方向

页面背景：

```text
#F7F8FA 附近
```

Surface：

```text
#FFFFFF
```

Primary Text：

```text
#1F2328 / 深中性
```

Secondary：

```text
#5F6772
```

Border：

```text
#E6E8EB
```

主 Accent：

- 冷蓝
- 蓝紫之间
- 不高饱和

具体 hex 应尽量复用当前品牌色，不为本规格机械重写全部 CSS。

---

# 10. Semantic Color

仅用于状态：

```text
success → green
warning → amber/orange
danger → red
info → blue
```

颜色不能是唯一状态表达。

必须配：

- icon
- text
- label

---

# 11. Typography

优先使用系统 sans-serif / 当前项目字体。

推荐：

```text
Page Title: 24–28px / 600
Section Title: 18–20px / 600
Card Title: 15–17px / 600
Body: 14–16px
Secondary: 13–14px
Caption: 12–13px
```

Writing editor 正文：

```text
16–18px
line-height: 1.7–1.85
```

---

# 12. Spacing System

采用 4px 基础倍数。

核心：

```text
4
8
12
16
20
24
32
40
48
```

页面水平 padding：

```text
24px desktop
16px medium
12–14px narrow
```

卡片内部：

```text
16–20px
```

---

# 13. Radius

科研平台不需要巨大圆角。

推荐：

```text
small: 6px
default: 8px
large: 10–12px
```

不要默认 20–24px 大圆角。

---

# 14. Shadow

默认 Surface 主要靠 border。

Shadow 只用于：

- Drawer
- Dropdown
- Popover
- Floating panel

Card 不要强阴影。

---

# 15. Buttons

层级：

```text
Primary
Secondary
Ghost
Danger
Icon
```

## Primary

用于页面单一主操作：

```text
创建项目
搜索论文
新建论文
```

不要一个区域同时出现多个 Primary。

## Secondary

如：

```text
上传 PDF
导出
重新搜索
```

## Ghost

如：

```text
详情
收藏
展开
```

---

# 16. Button Height

建议：

```text
small: 30–32px
default: 36–38px
large: 40–44px
```

Paper Card actions 使用 small / compact。

---

# 17. Disabled

必须：

- 保留布局
- pointer disabled
- opacity / neutral style
- Tooltip 解释

例如：

```text
暂无可用下载链接
暂无可导入的论文全文
```

---

# 18. Tooltip

用于解释：

- disabled action
- icon button
- citation status
- truncated metadata

不要用 Tooltip 承载长说明。

---

# 19. Loading

禁止页面只有中央 spinner。

使用上下文 loading。

例如 Discover：

```text
正在搜索相关论文
正在筛选结果
```

Project Papers：

Skeleton rows。

Writing：

右侧 Agent 显示阶段状态。

---

# 20. Empty State

Empty State 必须告诉用户：

1. 当前为什么为空
2. 下一步做什么

不要只写：

```text
暂无数据
```

---

# 21. Error State

用户看到业务语言。

内部技术错误写日志。

例如：

错误：

```text
SemanticScholarHTTPError 429
```

用户：

```text
论文搜索服务当前繁忙，请稍后重新搜索。
```

---

# 22. Projects Home

Route：

```text
/projects
```

或现有项目首页 route。

页面结构：

```text
我的科研项目                         [新建项目]

最近项目 / 全部项目

┌─────────────────┐ ┌─────────────────┐
│ Project A       │ │ Project B       │
│ topic...        │ │ topic...        │
│                 │ │                 │
│ 6 篇论文        │ │ 3 篇论文        │
│ 最近编辑...     │ │ 最近编辑...     │
└─────────────────┘ └─────────────────┘
```

---

# 23. Project Card

第一版字段：

- 项目名
- 研究主题（最多 2 行）
- 已导入论文数
- 最近更新时间

可选：

- 当前 WritingDocument title

不要：

- 10 个 KPI
- 大型 progress ring
- Agent usage count

---

# 24. Create Project Modal / Page

必填：

```text
项目名称
研究主题
```

可选折叠区：

```text
学科领域
研究对象
研究问题
研究目标
关键词
方法 / 技术方向
补充说明
```

默认不要一次铺满 8 个字段制造压力。

建议：

```text
基础信息
+
[补充更多研究信息]
```

---

# 25. Project Overview

目标：

> 让用户快速继续工作。

页面：

```text
Project Name

研究主题
[编辑]

继续你的研究

┌──────────────┐
│ 文献发现     │
│ 找适合论文   │
│ [开始搜索]   │
└──────────────┘

┌──────────────┐
│ 项目论文     │
│ 已导入 6 篇  │
│ [查看论文]   │
└──────────────┘

┌──────────────┐
│ 论文写作     │
│ 继续正文     │
│ [继续写作]   │
└──────────────┘
```

Desktop：

3 张并列卡片。

---

# 26. Overview Secondary Area

可显示：

```text
最近使用
- 阅读了 Paper A
- 编辑了 2.1
```

如果当前代码难以可靠提供，V1 可不做。

不应因此阻塞 Overview。

---

# 27. Overview No Dashboard Rule

禁止：

- 文献完成率饼图
- Agent 活跃度
- Evidence 数量图
- 工具调用曲线
- Token 使用量

除非后续真实用户证明需要。

---

# 28. Literature Discover Page

结构：

```text
Page Header
Requirement Area
Search Conditions
Results
```

普通页面宽度：

```text
max 1260px
```

---

# 29. Requirement Area

初始大面板：

```text
┌──────────────────────────────────────────────┐
│ 与 PaperAI 明确你要找的论文                  │
│                                              │
│ conversation                                 │
│                                              │
│ [输入研究需求............................] ↑ │
└──────────────────────────────────────────────┘
```

建议高度：

```text
360–480px initial
```

但不要占满整个屏幕。

---

# 30. Requirement Messages

Agent message：

- neutral background
- 不使用夸张头像
- max width 80–90%

User：

- subtle accent background

不要气泡过度圆角。

---

# 31. Requirement Ready State

当 Search Intent ready：

显示：

```text
已整理检索需求
```

并滚动 / 展示 Search Conditions。

---

# 32. Collapsed Requirement

搜索开始或完成后：

```text
当前检索需求：
生成式 AI 对大学生自主学习影响的实证研究...

[重新讨论]
```

高度：

```text
48–64px
```

---

# 33. Search Conditions Card

一张宽 Surface。

布局建议：

```text
搜索需求 [textarea full width]

年份        语言
领域        文献类型

                      [搜索论文]
```

Desktop 可两列字段。

---

# 34. Search Input

自然语言需求 textarea：

```text
min-height: 88–112px
```

允许修改。

---

# 35. Search Result Header

```text
找到 10 篇论文

[全部 10] [已收藏 3]
```

左侧结果数。

右侧未来可扩排序，但 V1 不做复杂排序 UI。

---

# 36. Paper Grid

Desktop：

```text
display: grid
grid-template-columns: repeat(2, minmax(0, 1fr))
gap: 16–20px
```

---

# 37. Paper Card

建议结构：

```text
┌──────────────────────────────────────────┐
│ Title                                    │
│ Authors · Year · Venue                   │
│                                          │
│ Abstract                                 │
│ line 1                                   │
│ line 2                                   │
│ line 3                                   │
│ line 4                         [展开]     │
│                                          │
│ 为什么推荐                               │
│ short reason                             │
│                                          │
│ metadata chips                           │
│                                          │
│ [详情] [收藏] [下载] [导入]              │
└──────────────────────────────────────────┘
```

---

# 38. Paper Card Height

默认 collapsed 状态：

统一最小高度。

推荐：

```text
min-height: 360–420px
```

实际根据现有 typography 调整。

Actions 使用：

```text
margin-top: auto
```

固定到底部。

---

# 39. Paper Title

最多：

```text
2–3 lines
```

超出使用 clamp。

完整标题可 Tooltip 或 Detail Drawer 查看。

---

# 40. Authors

最多显示：

```text
2–3 authors + et al.
```

完整作者在 Drawer。

---

# 41. Abstract

默认：

```text
line-clamp: 4
```

展开：

```text
none
```

按钮：

```text
展开
收起
```

---

# 42. Recommendation Reason

视觉比 Abstract 次一级。

Label：

```text
为什么推荐
```

正文：

2–3 行。

如果当前后端没有 reason：

整个区域可以隐藏，但卡片 action 位置保持。

---

# 43. Metadata Chips

可显示：

```text
2024
英文
期刊
被引 132
```

只显示真实可得字段。

不要生成：

```text
权威 ★★★★★
```

V1 暂不做。

---

# 44. Paper Actions

固定顺序：

```text
详情
收藏
下载
导入
```

建议：

- 详情 → Ghost
- 收藏 → Ghost / toggle
- 下载 → Secondary compact
- 导入 → Primary compact

但卡片里主按钮不要视觉过强到压过标题。

---

# 45. Paper Detail Drawer

从右侧进入。

建议宽度：

```text
480–560px
```

内容：

```text
Title
Authors
Venue / Year
DOI
Abstract
Recommendation Reason
Metadata
Original Page

Footer:
收藏 | 下载 | 导入
```

---

# 46. Drawer Footer

Actions sticky bottom。

避免用户滚完长 Abstract 后回顶部操作。

---

# 47. Project Papers Page

使用表格 / dense list。

页面：

```text
项目论文                             [上传 PDF]

[搜索当前项目论文...]

[全部] [未阅读] [阅读中] [已阅读]

Title                  Year    Status    Action
------------------------------------------------
Paper A                2024    阅读中    继续阅读
Paper B                2023    未阅读    开始阅读
```

---

# 48. Papers 表格列

第一版：

```text
Title
Authors
Year
Status
Action
```

Venue 可选。

不要塞：

- 15 个 metadata 字段
- Evidence count
- Agent score

---

# 49. Papers Title Column

Title 主文本。

Authors 次文本。

这样减少横向列数量。

---

# 50. Upload PDF

右上：

```text
[上传本地 PDF]
```

复用现有上传流程。

上传成功后进入现有解析。

---

# 51. Papers Status

如果现有代码已有可靠阅读状态，使用：

```text
未阅读
阅读中
已阅读
```

如果没有稳定数据，不为了 UI 强造状态。

可以先：

```text
已解析
处理中
失败
```

以真实数据为准。

---

# 52. Reader Entry

Action：

```text
开始阅读
继续阅读
```

进入现有 `PaperReader.vue`。

V1 Reader 不重新设计。

---

# 53. Writing Page

Writing 是全宽特殊页面。

结构：

```text
Global Sidebar
Project Header / compact
Writing 3-column workspace
```

Writing 页面顶部 Project header 可以压缩高度。

---

# 54. Writing Left Panel

默认：

```text
176px
```

内容：

```text
Document
Outline
```

Panel background：

```text
surface/subtle
```

与编辑器有细边框。

---

# 55. Writing Center

中心：

```text
flex: 1
min-width: 0
```

内部正文：

```text
max-width: 860px
margin: auto
padding: 28–56px 28–56px 96px
```

---

# 56. Writing Toolbar

sticky：

```text
top: 0
```

高度：

```text
40–44px
```

内容 compact。

---

# 57. Writing Right Panel

默认：

```text
320px
```

结构：

```text
Panel Header
Context Badge
Conversation
Proposal Card
Input Composer
```

---

# 58. Writing Agent Header

```text
AI 写作助手                 [收起]
```

不要：

```text
Research Agent Runtime v2
```

---

# 59. Context Badge

无 selection：

```text
当前：2.1 国内外研究现状
```

有：

```text
当前：2.1 国内外研究现状
已选中 126 字
```

使用小型 neutral chips / inline badge。

---

# 60. Writing Agent Input

底部 sticky composer：

```text
[说明你希望 AI 怎么处理...        ]
                                      [发送]
```

支持多行。

---

# 61. Proposal Card

与普通对话 message 有明显但克制区分。

结构：

```text
建议内容

text...

引用
Paper A    ✓ 已验证
Paper B    △ 证据较弱

[替换选中内容] [复制]
```

---

# 62. Proposal Actions

有 selection：

```text
替换选中内容
复制
```

无 selection：

```text
复制
```

按钮顺序必须稳定。

---

# 63. Citation Display

正文 Citation Node：

- inline
- 视觉清晰
- 不使用巨大 chip

例如：

```text
[1]
```

或 APA inline。

Hover：

```text
Paper title
verification status
```

Click：

Popover / Drawer。

---

# 64. Citation Detail Popover / Drawer

至少：

```text
Paper
Authors / Year
Evidence snippet
Page
Verification
[查看论文]
```

---

# 65. Writing Save State

顶部：

```text
已保存
保存中...
保存失败
```

使用 muted text + small icon。

---

# 66. Writing Export

顶部右侧：

```text
[导出 ▼]
```

Menu：

```text
DOCX
PDF
Markdown
LaTeX
```

只显示当前真实支持的格式。

DOCX 优先。

---

# 67. Agent Progress

右侧显示：

```text
正在读取项目资料
正在查找相关论文
正在查找支持证据
正在生成内容
正在验证引用
```

可用 vertical step / subtle status。

不显示工具日志。

---

# 68. Writing Error UX

例如无论文：

```text
当前项目还没有可用于引用的已导入论文。

[前往项目论文]
```

无 Evidence：

```text
当前项目资料中没有找到足够证据支持这项表述。
```

---

# 69. Global Toast

Toast 用于：

- 保存成功 / 失败
- 收藏成功
- 导入开始
- 导入失败
- 复制成功

不要用 Toast 展示长 Agent 结果。

---

# 70. Modal

Modal 用于：

- 创建项目
- 删除确认
- 高风险操作

不要把 Paper Detail 做 Modal，优先 Drawer。

---

# 71. Confirmation

删除 / destructive 操作才确认。

收藏、搜索、打开 Drawer 不要确认。

Remote import 如果已有安全检查，不要求额外确认。

---

# 72. Navigation Feedback

Project tab 切换：

- route 立即更新
- 页面使用 skeleton

不要整个页面 fade 500ms 动画。

---

# 73. Motion

V1 动画非常轻。

允许：

```text
drawer slide 160–220ms
dropdown fade 100–160ms
hover 100–150ms
```

不要：

- card floating animation
- gradient movement
- agent pulse effects

---

# 74. Iconography

使用一套统一 icon library。

不要混：

- Emoji
- FontAwesome
- Lucide
- 自制 SVG
- Material Icons

建议沿用当前项目已有主要 icon library。

---

# 75. Icons

常用：

```text
Home
Folder / Projects
Book / Reader
Search / Discover
FileText / Writing
Settings
Download
Upload
Bookmark
ExternalLink
Chevron
```

---

# 76. Form Inputs

统一：

```text
height: 36–40px
border radius: 6–8px
```

Focus：

- accent border
- subtle ring

Error：

- danger border
- helper text

---

# 77. Select

学科 / 语言 / 类型：

不要 native select 如果当前项目已有稳定 Select component。

要支持 keyboard。

---

# 78. Search Fields

年份：

两个 number input 或 compact year picker。

不要为了年份引入复杂 date picker。

---

# 79. Textarea

Requirement / Search Intent / Agent composer：

自动增长到最大高度后滚动。

---

# 80. Skeleton

Project cards：

Card Skeleton。

Paper Grid：

2-column card skeleton。

Papers：

Row Skeleton。

Writing：

不 skeleton 正文，优先加载现有 document 后显示。

---

# 81. Responsive Breakpoints

建议：

```text
>= 1280px  full desktop
1024–1279  compact desktop
768–1023   tablet
< 768       mobile
```

具体可与现有断点统一。

---

# 82. Discover Responsive

>= 1024：

2-column paper grid。

768–1023：

1 column。

< 768：

1 column + full-width Drawer/Sheet。

---

# 83. Writing Responsive

>= 1280：

3 columns。

1024–1279：

左 panel 可折叠，右 panel 340px。

768–1023：

left collapsed，Agent 用 side drawer。

< 768：

V1 保证基本查看/编辑，不追求完整三栏科研写作体验。

---

# 84. Sidebar Responsive

< 1024：

默认折叠。

< 768：

变成 overlay drawer / mobile nav。

---

# 85. Desktop Priority

开发验收优先：

```text
1440×900
1280×800
```

其次：

```text
1024×768
```

---

# 86. Accessibility

必须：

- semantic button
- form label
- keyboard focus
- aria label for icon buttons
- disabled real attribute
- status 不只靠颜色
- Drawer 可 Esc 关闭
- focus trap

---

# 87. Component Boundaries

建议：

```text
shared/
├── AppSidebar
├── ProjectHeader
├── AppButton
├── AppTooltip
├── AppDrawer
├── EmptyState
├── LoadingState
└── StatusBadge
```

Discover：

```text
RequirementChat
SearchIntentSummary
SearchFilterForm
SearchExecutionStatus
PaperResultGrid
PaperResultCard
PaperDetailDrawer
```

Writing：

```text
WritingDocumentEditor
WritingOutline
WritingAgentPanel
SelectionContextBadge
WritingProposalCard
CitationStatus
CitationDetail
```

---

# 88. Component Anti-Pattern

禁止：

```text
ProjectWorkspace.vue = 2000+ lines
```

页面负责：

- layout
- compose components
- route data

复杂业务状态进 store / composable / service。

---

# 89. Composables

可按现有 Vue 架构使用：

```text
useProject
useDiscovery
useWritingEditorContext
useExecutionStream
```

不要为了形式主义把每个函数都做 composable。

---

# 90. API Layer Frontend

统一放：

```text
frontend/src/api/
```

建议：

```text
projects.ts
discovery.ts
writing.ts
papers.ts
```

组件不直接写 axios/fetch。

---

# 91. State Source of Truth

Project metadata：

`projectStore`

Discover：

`discoverStore`

Tiptap document：

Editor / existing document model

Writing Agent：

`writingStore`

Shell：

`workspaceStore`

---

# 92. Persisted UI State

可以本地保存：

- sidebar collapsed
- writing agent collapsed
- last opened project

不要 localStorage 保存：

- search Provider raw results（长期）
- Agent conversation secrets
- entire Tiptap document as第二真值

---

# 93. Project Overview Component Tree

```text
ProjectOverview.vue
├── ProjectSummary
├── ContinueResearchGrid
│   ├── DiscoverEntryCard
│   ├── PapersEntryCard
│   └── WritingEntryCard
└── RecentActivity (optional)
```

---

# 94. Discover Component Tree

```text
LiteratureDiscover.vue
├── DiscoverHeader
├── RequirementChat
├── SearchIntentSummary
├── SearchFilterForm
├── SearchExecutionStatus
└── PaperResultGrid
    └── PaperResultCard
        └── PaperDetailDrawer
```

---

# 95. Papers Component Tree

```text
ProjectPapers.vue
├── PageHeader
├── PaperToolbar
├── PaperFilters
└── ProjectPaperTable
```

---

# 96. Writing Component Tree

```text
ProjectWriting.vue
├── WritingOutlinePanel
├── WritingMain
│   ├── WritingToolbar
│   └── WritingDocumentEditor
└── WritingAgentPanel
    ├── SelectionContextBadge
    ├── AgentConversation
    ├── WritingProposalCard
    └── AgentComposer
```

---

# 97. Route Ownership

页面只能取当前 `projectId`。

如果 project 不存在：

```text
项目不存在或你没有访问权限
[返回项目列表]
```

不要报 raw 404。

---

# 98. Page Title

浏览器 title：

```text
Project Name – PaperAI
文献发现 – Project Name – PaperAI
写作 – Project Name – PaperAI
```

---

# 99. Global Header

有 Sidebar 时不需要再放一个大型全局顶部导航。

Main 里只保留 Project header / page header。

---

# 100. Project Name Truncation

Sidebar / header：

超长时 ellipsis。

Hover 可显示完整。

---

# 101. Search Result Card Example

```text
┌──────────────────────────────────────────────────┐
│ Generative AI and Self-Regulated Learning        │
│ Zhang, Li et al. · 2024 · Computers & Education │
│                                                  │
│ This study examines how generative AI...         │
│ ...                                              │
│ ...                                      展开    │
│                                                  │
│ 为什么推荐                                       │
│ 直接研究高等教育场景下生成式 AI 与自主学习。     │
│                                                  │
│ 2024   英文   期刊   被引 132                    │
│                                                  │
│ 详情    收藏    下载    导入                     │
└──────────────────────────────────────────────────┘
```

---

# 102. Disabled Example

```text
详情    收藏    下载    导入
                ↑       ↑
              disabled
```

Hover：

```text
暂无可用下载链接
暂无可导入的论文全文
```

布局不变。

---

# 103. Overview Card Example

```text
┌──────────────────────┐
│ 文献发现             │
│ 找到适合当前主题的论文│
│                      │
│ [开始搜索]           │
└──────────────────────┘
```

不要放插画占 60% 空间。

---

# 104. Empty Papers Example

```text
当前项目还没有论文

你可以从“文献发现”导入论文，
或上传已有 PDF。

[发现论文] [上传 PDF]
```

---

# 105. Empty Writing Example

```text
开始撰写论文

创建一个正式写作文档后，
你可以使用章节结构、引用和 AI 写作助手。

[新建论文]
```

---

# 106. UX Copy

文案要简洁。

不要：

```text
Agent harness will autonomously orchestrate literature tools...
```

用：

```text
PaperAI 会根据你的研究需求搜索并筛选论文。
```

---

# 107. Terminology

用户界面统一中文名：

```text
Project → 项目
Discover → 文献发现
Papers → 项目论文
Writing → 写作
Evidence → 证据（仅用户真正看到时）
Citation → 引用
```

工程内部可以英文。

---

# 108. “工作区”术语

“导入工作区”在产品语义中：

> 导入当前项目并进入 PaperAI 解析链。

UI 可直接写：

```text
导入
```

不用每次显示“加入工作区”。

---

# 109. User Control

Agent 输出必须有明确可拒绝行为。

- Rewrite → 用户点击替换
- Generate → 用户复制
- Search Intent → 用户可编辑
- Search Filters → 用户可修改

不做暗中自动改内容。

---

# 110. No Fake UI

禁止：

- placeholder chart
- fake citation count
- fake progress
- demo-only Agent Activity
- button 点击后 Toast “Coming soon”却长期留在主 UI

未实现功能：

- 不显示
- 或明确 disabled + “暂未支持”，只限确实需要提前占位的少数场景

---

# 111. Frontend Migration

## `ProjectWorkspace.vue`

拆分。

第一阶段可变成 route shell。

最终不再容纳全部功能。

## `ProjectChat.vue`

抽取可复用 conversation UI。

不再作为 Project 主页面。

## `WritingDocumentEditor.vue`

保留核心，拆 Agent panel 与 layout。

## `PaperReader.vue`

冻结。

## `ResearchProjectList.vue`

重构成 Projects Home。

---

# 112. CSS Migration

不要一次性全项目重写样式。

策略：

1. 建 semantic tokens。
2. 新页面使用新 token。
3. 复用旧组件时适配。
4. 主线稳定后再清理 legacy CSS。

---

# 113. Acceptance - Global

必须验证：

- Sidebar 不溢出
- Project tabs 工作
- route refresh 正常
- no duplicate navigation
- 1280px 可用

---

# 114. Acceptance - Discover

必须验证：

- requirement chat
- collapsed state
- search form
- 2-column
- abstract clamp
- expand
- actions fixed
- disabled tooltip
- favorite
- drawer
- partial results
- error

---

# 115. Acceptance - Papers

必须验证：

- upload
- table
- reader entry
- empty state
- processing state

---

# 116. Acceptance - Writing

必须验证：

- outline
- Tiptap
- agent panel
- selection badge
- proposal
- replace
- copy
- citation status
- panel collapse
- export
- save state

---

# 117. Design Review Checklist

Codex 完成一个页面后，必须检查：

```text
[ ] 页面是否只有一个明确主任务
[ ] 是否存在无效信息
[ ] 是否把工程概念暴露给用户
[ ] Primary button 是否过多
[ ] Empty state 是否告诉用户下一步
[ ] Loading 是否有上下文
[ ] Error 是否是用户语言
[ ] 1280px 是否溢出
[ ] disabled 是否保持布局
[ ] 所有按钮是否真实工作
```

---

# 118. V1 Frontend Definition of Done

前端 V1 完成应达到：

1. 用户无需理解 Agent 架构。
2. Project 主线只有 Overview / Discover / Papers / Writing。
3. Discover 一眼知道“先明确需求，再搜索论文”。
4. 搜索结果不是文本，而是双列结构化卡片。
5. 收藏 / 下载 / 导入行为清晰且不混淆。
6. Papers 是高密度论文列表，不重复 Discover 卡片。
7. Reader 保持现有成熟体验。
8. Writing 是真正编辑器，不是 Chat 页面。
9. AI 与编辑器 selection / section 有明确联动。
10. Citation 可追溯、可验证。
11. 页面视觉克制且一致。
12. 不出现无效按钮、假数据和开发者日志。
