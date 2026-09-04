# Smoke Tests

冒烟测试是一份“改完代码后快速确认主流程还能用”的清单。它不替代单元测试和集成测试，只用于快速发现明显回归。

## 准备

确认服务运行：

```bash
docker compose ps
```

如果未运行：

```bash
docker compose up -d
```

确认基础地址：

- 前端：http://localhost:5173
- 后端健康检查：http://localhost:8000/health
- API 文档：http://localhost:8000/docs

## 后端基础检查

```bash
curl http://localhost:8000/health
```

期望：

```json
{"status":"healthy"}
```

```bash
curl http://localhost:8000/
```

期望：返回 PaperAI 应用名、版本和描述。

## 前端基础检查

1. 打开 `http://localhost:5173`。
2. 页面能正常渲染，不白屏。
3. 浏览器控制台没有明显启动错误。
4. 未登录访问 `/papers` 会跳转到 `/login`。

## 认证流程

1. 打开 `/register`。
2. 注册一个测试用户。
3. 注册成功后确认能进入应用，或可以使用该账号登录。
4. 打开 `/login`。
5. 输入测试用户账号密码。
6. 登录成功后确认 `localStorage.access_token` 存在。
7. 刷新页面，确认登录状态仍然可用。

## 论文上传和解析

准备一个小 PDF，优先使用页数少、体积小的论文。

1. 打开 `/papers`。
2. 上传 PDF。
3. 页面出现上传成功或任务创建成功反馈。
4. 任务状态开始轮询。
5. 状态变为 `ready` 后，上传窗口结束等待，论文出现在列表中。
6. 此时论文可以打开、阅读并进行正文问答，图表仍在后台增强。
7. 后台任务最终变为 `completed`，`details.media_status` 为 `completed`。
8. 刷新页面后论文仍然存在。

任务完成后检查状态接口中的 `details`：

- `timings_seconds`：各阶段实际秒数及总耗时。
- `timing_percentages`：各阶段占总耗时比例。
- `counts`：表格、图片候选、成功分析图片及向量片段数量。
- `ready_seconds`：论文首次可阅读、可进行正文问答的时间。
- `media_status`：图表增强状态，取值为 `processing`、`completed` 或 `failed`。

重点关注 `initial_text_extraction`、`table_extraction`、`image_analysis` 和
`vector_indexing`。性能优化前后应使用同一份 PDF 对比，不能只比较不同文件的总耗时。

如果任务失败，检查：

```bash
docker compose logs --tail 200 backend
```

## 论文阅读

1. 在论文列表点击一篇论文。
2. 进入 `/paper/{id}`。
3. PDF 能加载。
4. 论文基础信息能显示。
5. 章节列表或正文内容能显示。

## 论文问答

1. 打开论文问答页 `/paper/{id}/qa`。
2. 输入一个简单问题，例如“这篇论文主要研究什么？”
3. 提交问题。
4. 等待回答。
5. 回答应和论文内容相关，页面不报错。

如果问答失败，优先检查：

- `.env` 中 LLM API key 是否存在。
- `LLM_PROVIDER` 是否正确。
- 后端日志是否有模型调用错误。
- 知识库是否成功写入该论文内容。

## 摘要和解读

1. 在论文页触发结构化摘要。
2. 确认摘要能生成或显示缓存。
3. 触发一种深度解读。
4. 确认解读能生成或显示缓存。

## 研究项目完整流程

先登录并从浏览器开发者工具的 `localStorage.access_token` 获取测试令牌。测试账号至少需要有一篇已上传论文。

```bash
cd backend
PAPERAI_TOKEN='<access-token>' python -m scripts.verify_project_flow
```

也可以指定论文和服务地址：

```bash
PAPERAI_TOKEN='<access-token>' \
PAPERAI_PAPER_ID='<paper-id>' \
PAPERAI_BASE_URL='http://localhost:8000' \
python -m scripts.verify_project_flow
```

脚本覆盖项目 CRUD、项目文档库、精读队列、结构化论文阅读卡片、带论文/页码来源的长期记忆、领域地图、写作产物以及项目会话的 `project_id` 贯穿。默认无论成功或失败都会删除测试项目；传 `--keep` 可保留数据用于前端检查。

脚本还会建立“证据矩阵 → 实验设计 → 论文蓝图 → 章节草稿”的血缘样本，并确认通用 REST
接口不能伪造受信任审计报告或论文终稿。

### Agent 工具链完整验证

下面的验证器不调用 LLM，不消耗模型额度，但会加载真实的 21 个项目 `StructuredTool`，并使用
数据库中一篇现有论文生成临时项目，并一路执行到终稿和投稿包：

```bash
docker compose run --rm --no-deps backend \
  python -m scripts.verify_agent_manuscript_flow
```

覆盖论文卡片、领域地图、精读计划、证据矩阵、实验设计、论文蓝图、分节草稿、确定性参考
文献、全文组装、审计、定稿、LaTeX 引用、Word 容器和投稿 ZIP。默认成功或失败都会清理
临时项目；传 `--keep` 可保留产物做人工检查。

若要额外验证当前配置的真实 LLM 能看到项目上下文并自主选择项目工具，可运行一次最小在线冒烟
（会产生一次很短的模型调用）：

```bash
docker compose run --rm --no-deps backend \
  python -m scripts.verify_project_agent_live
```

脚本只要求 Agent 调用 `project_append_memory`，验证 trace 和数据库副作用后自动删除临时项目。

如果已有一次由 Agent 真正完成并锁定的终稿，可追加两个参数验证四种导出与投稿包内部结构：

```bash
PAPERAI_TOKEN='<access-token>' \
python -m scripts.verify_project_flow \
  --existing-project-id '<project-id>' \
  --final-artifact-id '<final-manuscript-id>'
```

也可使用 `PAPERAI_EXISTING_PROJECT_ID` 和 `PAPERAI_FINAL_ARTIFACT_ID` 环境变量。该模式会检查
Markdown、LaTeX、Word 的 MIME 与内容、DOCX 容器，以及投稿 ZIP 中的正文、BibTeX、审计报告和清单。

前端手动检查：

1. 登录后从首页账户菜单进入“研究项目”，地址应为 `/projects`。
2. 新建项目后进入 `/project/{id}`，确认研究地图、精读计划、证据矩阵、实验设计、论文写作、文档库、写作产物和长期记忆等工作区可切换。
3. 新建空项目应首先显示“研究任务书”阶段；让 Agent 澄清题材后，工作台应显示已知背景、约束、未知项、检索式、纳入排除标准和选题评价准则，并推进到候选筛选阶段。
4. 让 Agent 按任务书执行检索并保存候选台账；确认查询来源与结果数、去重数、纳入/排除/待定、相关度、覆盖维度和理由可见，且至少一个候选被纳入后才推进到文献入库。
5. “领域地图”空状态应说明如何生成；生成后应显示关键词、研究问题、方法、数据集、研究空白和候选选题。
6. 即使文档库为空，“进入项目对话”也应可用，并进入 `/project/{id}/chat`；输入框应预填当前工作流的下一步建议。
7. 在项目对话中让 Agent 从已纳入候选中导入一个严格的 arXiv ID。工作台应显示导入的排队、处理、完成或失败状态；处理完成后论文自动加入项目文档库。重复导入同一篇论文不得创建重复任务。
8. 加入论文、生成精读计划，确认论文按队列顺序展示，阅读理由、重点、待回答问题和状态可见。
9. 手动把队列状态切换为“精读中”；Agent 保存论文卡片后应自动变为“已完成”。
10. 点击“自动精读”，确认显示当前论文和总体进度；暂停应在当前论文完成后生效，继续或失败重试应从未完成论文开始。
11. 至少完成两张论文卡片后生成“跨论文证据矩阵”，确认方法、数据集、指标、发现和局限来自卡片，冲突项显示来源编号。
12. 基于证据矩阵保存实验设计，确认研究问题、假设、变量、数据、评价指标和威胁项可见，并正确设置是否需要新实证结果。
13. 实证研究在用户提供真实输出后登记结果，确认运行标识、来源定位或校验和、指标、不确定性、协议偏差与假设结论可见；通用产物 REST 不能伪造 `experiment_results`。
14. 基于已满足结果关口的实验设计生成论文蓝图，确认每个章节都有目标字数、核心主张、证据引用和引用需求；缺少证据的主张必须列入待解决项。
15. 分章节生成草稿，确认草稿记录蓝图章节 ID、论文来源和未解决问题。结果章节写入实际数值时必须绑定对应 `experiment_results_id`。
16. 先从章节 `evidence_refs` 生成参考文献列表，再尝试组装全文：章节缺失、仍有待解决项、参考文献键缺失或实证设计没有结果章节绑定时默认应拒绝；通过后应按蓝图顺序生成带 `[@citation_key]` 的 `full_draft`。
17. 对完整草稿执行全文审计，确认报告绑定具体全文和版本，并分别统计 blocker、major、minor；工作台显示“草稿 → 审计 → 终稿”状态。
18. blocker 大于零时尝试定稿，后端必须拒绝；定向修订章节、重新组装和重新审计后，旧报告不得用于新版本定稿。
19. 确认未被章节使用的项目论文不会混入参考文献，重复作者年份生成不同引用键，缺 DOI 或 page/source_id 会明确提示；参考文献更新后，旧全文不得直接定稿。
20. 最新审计 blocker 为零、全文无占位符且引用与参考文献一致后生成 `final_manuscript`；分别下载 Markdown、LaTeX、Word 和投稿 ZIP。
21. 解压投稿包，确认包含 `manuscript.md`、`manuscript.tex`、`manuscript.docx`、`references.bib`、`audit-report.md` 和 `MANIFEST.txt`。
22. 追加一条带来源论文和页码的记忆，刷新后来源仍可点击并能回到对应论文。
23. 项目对话刷新后应恢复同一项目会话；从回答中的论文引用可跳转到对应阅读页。
24. 在 360px、768px 和桌面宽度下检查工具栏、项目列表与研究驾驶舱：桌面端研究路线应保持可见，窄屏应变成可横向浏览的阶段导航，工作区不应横向挤压。
25. 在研究路线依次选择任务书、候选文献、领域地图、证据矩阵、实验与写作阶段，确认右侧工作区正确切换；点击“在 Agent 中处理”后，项目对话应预填与当前工作区对应的具体任务。
26. 删除或移除操作必须显示明确的确认说明。

Agent 写作链路建议依次发送：

1. “基于证据矩阵制定实验设计，明确是否需要新实证结果。”
2. “这是实际实验输出及其来源，请登记结果；不要补写文件中不存在的数值。”
3. “基于已满足结果关口的实验设计制定论文蓝图并保存。”
4. “按蓝图撰写方法和结果章节；每个主张标记论文来源，结果数值绑定实验结果产物，无法支持的内容保留为待解决项。”
5. “继续完成其余章节，不要虚构实验结果。”
6. “检查章节、结果来源和参考文献完整性并组装全文；若仍有缺口，先返回缺口清单。”
7. “审计全文的事实、引用、结果完整性、主张证据覆盖与结构问题，并保存审计报告。”
8. “按审计报告定向修订阻断项，重新组装并审计；通过后锁定终稿。”

验收重点不是模型是否能生成长文本，而是 Agent 是否调用 `project_save_paper_blueprint`、
`project_save_section_draft`、`project_assemble_full_draft`、`project_audit_full_draft` 和
`project_finalize_manuscript`，以及后端是否拒绝越过证据、版本、审计与完整性约束。

前端构建验证：

```bash
cd frontend
npm run build
```

## 改动对应检查建议

只改前端样式：

- 前端基础检查
- 被修改页面的核心操作
- `npm run build`

改登录/认证：

- 后端基础检查
- 认证流程
- 未登录跳转
- token 过期/401 行为

改论文上传/解析：

- 后端基础检查
- 论文上传和解析
- 论文阅读
- 后端日志

改 RAG/LLM/Agent：

- 论文问答
- 摘要和解读
- LLM 配置检查
- 后端日志

改数据库模型：

- 后端启动
- 注册/登录
- 论文列表
- 相关业务 CRUD
