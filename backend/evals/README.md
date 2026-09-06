# PaperAI Evaluation

本目录用于离线评估 PaperAI 的检索、回答、引用和系统性能。评测数据使用 JSONL：每一行是一条独立 JSON 对象。

## 当前已经具备

- 数据集结构和严格校验
- 数据分布统计
- 检索 Hit@K、Evidence Recall@K、Precision@K、MRR
- 明确表格问题的 Table Hit@K
- 按问题类型和难度输出切片指标
- 保存每条问题的原始检索结果，便于定位失败原因
- 端到端引用、页码、拒答和硬幻觉指标

检索基线已建立。端到端采集器可保存真实回答、引用、检索上下文和延迟；答案与引用评分在采集真实结果后执行。

## 评测分层

当前优先评估可定性判对错的能力，不评价语言风格。

1. 检索层：系统是否把 Gold 证据找回来，以及证据是否排得足够靠前。
2. 回答层：系统是否覆盖标准原子事实、引用是否真实、页码是否可靠。
3. 拒答层：论文没有答案时是否拒答，可回答问题是否过度拒答。
4. 硬幻觉层：回答是否出现证据或标准答案中没有的关键数字，或在必须拒答时给出确定答案。

`silver` 是 AI 生成且通过程序硬校验的候选样本；`verified` 是人工确认过的 Gold 样本。Silver 可用于开发调试和扩充覆盖面，最终质量报告应优先使用 verified 样本。

## Agent Runtime 运行观测

Agent Runtime 报告读取 PostgreSQL 中已有的 `AgentExecution`、`ResearchTask`、
`ToolCall` 和任务范围内的 `ModelCall`，只计算确定性运行事实，不做 LLM 评审，
不读取完整提示词或推理内容。报告包含 Execution/Task/Skill/Executor 切片、
Tool/Model 延迟与调用量、预算使用、同一任务内的重复成功工具调用及失败分类。

在 `backend/` 目录运行：

```bash
python -m evals.run_agent_runtime_report \
  --limit 1000 \
  --output evals/reports/agent_runtime_manual.json
```

也支持 `--since`、重复传入 `--task-type` 和 `--skill-id`。默认输出为
`evals/reports/agent_runtime_<timestamp>.json`，`sample_size` 会明确记录实际样本量。
现有静态面板会自动加载最新的 `agent_runtime_*.json`；也可以用
`--agent-runtime-report` 指定报告文件。

## 1. 查看当前可用于评测的论文

在 `backend/` 目录运行：

```bash
../.venv/bin/python -m evals.list_papers
```

输出中的 `paper_id` 必须与向量库中的论文 ID 一致。不要使用标题相同但解析不完整的重复上传记录。

## 2. 建立正式数据集

复制示例文件：

```bash
cp evals/datasets/paperqa_v1.example.jsonl evals/datasets/paperqa_v1.jsonl
```

编辑 `paperqa_v1.jsonl`。JSONL 与普通 JSON 数组不同：一行一条记录，行尾没有逗号，整个文件也没有方括号。

字段说明：

| 字段 | 含义 |
| --- | --- |
| `id` | 稳定且唯一的问题 ID，例如 `paper03_q007` |
| `paper_id` | PaperAI 数据库和向量库使用的论文 UUID |
| `paper_title` | 便于人工检查的论文标题 |
| `question` | 用户问题 |
| `task_type` | `metadata/fact/method/concept/experiment/table/comparison/cross_section/multi_turn/unanswerable/adversarial` |
| `difficulty` | `easy/medium/hard` |
| `split` | `dev` 用于调参；`test` 仅用于最终报告 |
| `answerable` | 论文是否能回答该问题 |
| `must_abstain` | 系统是否必须拒答，与 `answerable` 相反 |
| `reference_answer` | 人工核对后的标准答案 |
| `reference_claims` | 将答案拆成独立、可判真的原子事实 |
| `evidence` | 支持答案的 PDF 原文、物理页码、章节和表号 |
| `expected_tables` | 明确表格问题期望命中的表号 |
| `annotation_status` | 原始候选为 `draft`；自动检查通过为 `silver`；人工核对后为 `verified` |

## 3. 人工标注规范

### 标准答案

只写论文能够直接支持的内容，不补充常识，不根据摘要推断实验细节。数值、数据集名称、比较对象和方向必须与 PDF 一致。

### 原子事实

一句话中出现多个可独立判定的事实时必须拆开。例如：

```json
"reference_claims": [
  "移除 DTG 后检测性能下降",
  "IMD2020 上 ACC 下降 0.12",
  "IMD2020 上 F1 下降 0.11"
]
```

不要写成一个包含三项结论的长 claim，否则后续无法计算完整性。

### 证据

- `quote` 必须从 PDF 原文连续复制，不要改写，建议 30～200 字。
- `page` 填 PDF 阅读器显示的物理页码，不填论文印刷页码。
- 一条原文无法支持全部 claims 时，添加多条 evidence。
- 表格问题设置 `source_type=table`，填写 `table_number` 和能够证明目标数值的表格内容。
- 证据仅仅“主题相关”不算合格，必须能够直接支持至少一个 claim。

### 不可回答问题

设置：

```json
"answerable": false,
"must_abstain": true,
"reference_claims": [],
"evidence": []
```

标记不可回答前，需要使用关键词和同义词搜索全文。问题不能明显荒谬，应当像真实用户可能提出、但论文确实没有报告的问题。

### 开发集与测试集

必须按论文切分，而不是按问题随机切分。同一篇论文的全部问题只能属于一个 split。推荐 70% 论文为 `dev`，30% 论文为 `test`。调分块、Prompt 和重排时只能查看 dev 结果。

## 4. 校验数据集

```bash
../.venv/bin/python -m evals.validate_dataset \
  --dataset evals/datasets/paperqa_v1.jsonl
```

校验通过不代表答案正确，只代表数据结构和最低标注要求合格。

## 5. 运行检索评测

运行会调用当前配置的 Embedding API，可能产生少量费用：

```bash
../.venv/bin/python -m evals.run_retrieval_eval \
  --dataset evals/datasets/paperqa_v1.jsonl \
  --split dev \
  --top-k 5
```

默认只运行 `verified` 样本。运行自动检查通过的 Silver 开发集：

```bash
../.venv/bin/python -m evals.run_retrieval_eval \
  --dataset evals/datasets/paperqa_v1.jsonl \
  --split dev \
  --top-k 5 \
  --include-silver
```

标注过程中调试原始草稿可显式加入：

```bash
../.venv/bin/python -m evals.run_retrieval_eval \
  --dataset evals/datasets/paperqa_v1.jsonl \
  --split dev \
  --top-k 5 \
  --include-drafts
```

报告写入 `evals/reports/`，包含总指标、类型切片、难度切片和每个问题的 Top-K 检索内容。

## 6. 推荐建立顺序

先完成 3 篇论文 × 8 个问题的 24 条试标数据。确认字段和标注尺度稳定后，再扩展到 10 篇、80～120 条。不要一次标完 100 条后才发现证据尺度不一致。

可用 LLM 先生成候选 Silver/Draft 数据：

```bash
../.venv/bin/python -m evals.generate_silver_dataset \
  --manifest evals/datasets/pilot_manifest.json \
  --questions-per-paper 6 \
  --unanswerable-per-paper 2 \
  --output evals/datasets/paperqa_v1.jsonl
```

`--questions-per-paper` 生成可回答题。`--unanswerable-per-paper` 生成必须拒答的候选题，这类题默认标为 `draft`，因为“论文未报告某信息”需要人工复核后才能升级为 verified。

导出待审核队列：

```bash
../.venv/bin/python -m evals.review_dataset \
  --dataset evals/datasets/paperqa_v1.jsonl \
  --status silver \
  --status draft \
  --limit 20 \
  --export-md evals/reports/review_queue.md
```

人工核对某条样本后，将其升级为 verified：

```bash
../.venv/bin/python -m evals.review_dataset \
  --dataset evals/datasets/paperqa_v1.jsonl \
  --case-id p04_q001 \
  --set-status verified \
  --review-note "人工核对问题、答案、claims 和 evidence 通过"
```

确认候选题质量较差时，可从 JSONL 中丢弃：

```bash
../.venv/bin/python -m evals.review_dataset \
  --dataset evals/datasets/paperqa_v1.jsonl \
  --case-id p04_q009 \
  --discard
```

## 7. 采集端到端回答与引用

先运行一条样本，确认模型、数据库和向量库连接正常：

```bash
../.venv/bin/python -m evals.run_e2e_eval \
  --dataset evals/datasets/paperqa_v1.jsonl \
  --split test \
  --case-limit 1 \
  --output evals/reports/e2e_test_raw.json
```

确认后断点续跑全部 Gold 样本：

```bash
../.venv/bin/python -m evals.run_e2e_eval \
  --dataset evals/datasets/paperqa_v1.jsonl \
  --split test \
  --output evals/reports/e2e_test_raw.json \
  --resume
```

报告逐题落盘，中断后可继续。报告中的 `intent_confidence` 仅表示意图分类置信度，不能解释为答案准确率。回答生成超时会标记为 `generation_timeout`，不会伪装成正常完成样本。

## 8. 端到端评分指标

对原始报告执行确定性评分：

```bash
../.venv/bin/python -m evals.score_e2e_eval \
  --input evals/reports/e2e_test_raw.json \
  --output evals/reports/e2e_test_scored.json
```

当前端到端质量指标只在成功生成有效答案的样本上计算；服务稳定性用 `valid_answer_rate` 和 `timeout_rate` 单独展示。

当前端到端指标：

| 指标 | 含义 |
| --- | --- |
| `citation_precision` | 引用文字可由其 `source_id` 指向的检索块支持的比例 |
| `citation_recall` | Gold 证据被已引用检索块覆盖的比例 |
| `page_accuracy` | 引用页码与其指向检索块页码一致的比例 |
| `claim_coverage_proxy` | 答案与 Gold 原子事实的字符重合代理，不等同于答案准确率 |
| `valid_answer_rate` | 原始样本中成功生成有效答案的比例 |
| `timeout_rate` | 原始样本中回答生成阶段超时的比例 |
| `abstention_accuracy` | 必须拒答样本中，系统实际拒答的比例 |
| `over_abstention_rate` | 可回答样本中，系统错误拒答的比例 |
| `unsupported_number_rate` | 答案中的数字未出现在 Gold 或检索/引用证据中的比例 |
| `critical_hallucination_rate` | 出现硬幻觉的样本比例：应拒答未拒答，或答案含无证据数字 |

硬幻觉指标是第一版保守定义，用于稳定自动化回归。语义级幻觉后续应通过“答案原子事实抽取 + 证据支持判断”扩展，而不是直接让模型笼统评价整段回答。
