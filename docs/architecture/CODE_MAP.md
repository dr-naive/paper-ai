# PaperAI 代码导航

> 这是一份按功能入口整理的快速导航，不替代具体实现和规格文档。
> 修改代码前先从目标入口沿调用链读取；只有当调用链或测试结果显示存在影响时，
> 才继续扩展阅读范围。

## 一、后端目录职责

| 目录 | 负责内容 | 修改边界 |
| --- | --- | --- |
| `backend/app/api/` | HTTP 路由、鉴权、参数校验、响应和错误映射 | 不放长任务、科研算法或数据库业务编排 |
| `backend/app/application/` | 用例服务、业务工作流、事务边界、队列派发适配 | 复用既有 Service/Workflow，不复制 RAG 或 Agent Runtime |
| `backend/app/models/` | PostgreSQL ORM 模型和持久化关系 | 新表必须有 Alembic 迁移，旧字段只做兼容扩展 |
| `backend/app/job_queue.py` | Redis `WorkerJob` 入队、领取、确认、重试、死信和恢复 | 不在业务模块中重新实现队列 |
| `backend/app/worker.py` | Worker 任务类型注册和既有执行载体 | 只做任务入口适配，具体能力委托给 Service/Workflow/Runner |
| `backend/app/harness/` | Lead Agent、Skill、Tool Scope 和运行时约束 | Agent 只能处理当前任务范围 |
| `backend/app/rag/` | 检索、向量库、表格检索和 RRF | 不搬入 API 或 Orchestrator |
| `backend/evals/` | 离线/管理员评测脚本、指标和报告 | 评测能力由脚本拥有，API/Worker 只负责调度和结果持久化 |

## 二、前端目录职责

| 目录 | 负责内容 |
| --- | --- |
| `frontend/src/views/` | 页面级布局和页面数据加载 |
| `frontend/src/components/` | 可复用 UI、状态展示和交互组件 |
| `frontend/src/api/` | 按后端资源组织的类型化 HTTP 客户端 |
| `frontend/src/stores/` | 跨页面共享状态（Pinia） |
| `frontend/src/router/` | 页面路由和权限元数据 |

## 三、管理员测评真实调用链

```text
AdminDashboard.vue
  → components/admin/AdminEvaluationPanel.vue
  → api/admin.ts
  → POST /api/admin/evaluations
  → app/api/admin.py
  → EvaluationRun（PostgreSQL）
  → enqueue_job("admin_evaluation")
  → app/worker.py: dispatch_job
  → handle_admin_evaluation
  → application/admin_evaluation_runner.py
  → 既有 evals/run_* 脚本
  → evals/reports/admin_evaluations/{run_id}.json/.md
  → EvaluationRun.summary/status
  → GET /api/admin/evaluations/{run_id}
  → 前端轮询、结果卡片和历史日期
```

对应文件：

- 页面：`frontend/src/views/AdminDashboard.vue`
- 测评面板：`frontend/src/components/admin/AdminEvaluationPanel.vue`
- 前端接口：`frontend/src/api/admin.ts`
- 管理员路由：`backend/app/api/admin.py`
- 持久化模型：`backend/app/models/evaluation.py`
- 状态转换：`backend/app/application/evaluation_run_service.py`
- 评测脚本适配：`backend/app/application/admin_evaluation_runner.py`
- 队列入口：`backend/app/job_queue.py`、`backend/app/worker.py`
- 数据库迁移：`backend/alembic/versions/0009_admin_evaluation_runs.py`、
  `0010_admin_evaluation_active_guard.py`

## 四、管理员测评类型与能力归属

| 类型 | 适配的既有能力 | 是否默认调用外部服务 |
| --- | --- | --- |
| `runtime` | `run_agent_runtime_report`，读取 PostgreSQL Execution/Task/Tool/Model/事件 | 否 |
| `retrieval` | `run_retrieval_eval`，读取 `paperqa_v1.jsonl` 并调用现有 Knowledge Base | 可能需要向量/Embedding 配置 |
| `e2e` | `run_e2e_eval` + `score_e2e_eval`，沿用现有问答和确定性评分 | 需要现有 LLM/向量配置 |

不要在 `ResearchOrchestrator`、管理员 API 或前端重新实现检索、问答、引用评分或
运行时指标；需要增加评测类型时，只新增一个受控 Runner 适配，并复用同一个
`EvaluationRun → WorkerJob → Worker` 生命周期。

## 五、论文上传、解析与项目范围真实调用链

```text
ProjectPapers.vue / PaperList.vue
  → PaperUploadModal.vue
  → api/paper.ts: uploadPaper(file, projectId?)
  → POST /api/v1/papers/upload
  → app/api/papers.py: upload_paper
  → create_task + enqueue_job("paper_process")
  → app/worker.py: handle_paper_process
  → _schedule_process_paper
  → PaperUploadService.extract_text
  → PaperCoreProcessingService.extract_structure/persist_core/build_text_index
  → Paper / Section / DocumentElement / 既有知识库
```

项目上传会在 `Paper.is_project_only` 保存为项目专属；独立阅读的
`GET /api/v1/papers/` 只读取 `false`，而 `ProjectService.list_project_papers` 仍按
`ProjectPaper` 关系读取项目论文。已有独立论文通过加入项目接口建立关系时不会改变
`is_project_only`，因此可以同时出现在两个业务范围。

解析文本的清洗边界：`paper_files.extract_pdf_text` 和分页文本先清洗，
`PaperUploadService`、`PaperCoreProcessingService` 在解析结果、数据库字段和索引输入
处再次清洗，兼容 Worker 恢复、重试和直接调用路径。

失败导入清理链：

```text
PaperList.vue / PaperUploadModal.vue
  → DELETE /api/v1/papers/tasks/{task_id}
  → 校验当前用户 + FAILED 状态
  → 既有 KnowledgeBase.delete_paper
  → 删除部分 Paper（如存在）+ PDF
  → task_manager.remove_task（文件 + Redis）
```

对应文件：`backend/app/api/papers.py`、`backend/app/services/paper_files.py`、
`backend/app/services/paper_core_processing.py`、`backend/app/worker.py`、
`frontend/src/components/PaperUploadModal.vue`、`frontend/src/views/PaperList.vue`。

## 六、按影响范围选择测试

| 改动范围 | 先跑的测试 | 额外检查 |
| --- | --- | --- |
| 前端单个组件/页面 | 对应 `*.spec.ts` | `npm run typecheck`；涉及样式/模板时再跑 `npm run lint` |
| `frontend/src/api/` 类型或路径 | 使用该 API 的页面/组件测试 | `npm run typecheck` |
| 单个后端 Service/Runner | 对应后端测试文件 | 目标文件 Ruff/compile |
| API 路由 | 对应 API/安全测试和相关 Service 测试 | 不涉及迁移时不跑 Alembic |
| `worker.py`/`job_queue.py` | Worker 派发、队列重试/恢复测试 | 只有队列协议变更时才做 Redis 集成检查 |
| ORM 模型/迁移 | 对应模型测试、迁移测试 | `alembic current` + schema preflight |
| 跨前后端完整 Implementation Block | 上述受影响测试集合 | Block 收口后跑一次完整回归，不在每次小修改后全量运行 |

当前管理员测评 Block 的最小验证集合是：

```text
backend/tests/test_admin_evaluations.py
backend/tests/test_database_migrations.py
backend/tests/test_app.py
frontend/src/components/admin/AdminEvaluationPanel.spec.ts
frontend: npm run typecheck && npm run lint
```

完整后端/前端回归只在该 Block 最终收口或 Phase 验收时执行一次，并在
`IMPLEMENTATION_PROGRESS.md` 记录具体命令和结果。
