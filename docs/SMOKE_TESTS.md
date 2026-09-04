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

## 可选 Docker 出站代理

默认不设置代理时，`backend` 和 `worker` 直连外部服务。需要使用宿主机代理时，
先让代理程序允许 Docker 网桥访问，再在本地 `.env` 配置（不要提交该文件）：

```env
PAPERAI_HTTP_PROXY=http://host.docker.internal:7892
PAPERAI_HTTPS_PROXY=http://host.docker.internal:7892
```

重建并检查两个服务收到的代理地址：

```bash
docker compose up -d --build backend worker
docker compose exec backend sh -lc 'python -c "import os; print(os.environ.get(\"HTTPS_PROXY\") or \"direct\")"'
docker compose exec worker sh -lc 'python -c "import os; print(os.environ.get(\"HTTPS_PROXY\") or \"direct\")"'
```

如果代理只监听宿主机 `127.0.0.1`，容器不能访问它；不要把容器代理地址写成
`127.0.0.1:7892`。未配置或代理不可用时，PaperAI 仍使用直连和既有超时/失败处理。

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

## V1 Project 主链

这是当前 V1 应持续保持稳定的产品级 smoke；它不把旧 Research Map、Reading Plan、Evidence
Matrix、Experiment Design、Activity 或 Universal Project Chat 当作验收步骤。

### 1. Discover → Papers

1. 登录后进入 `/projects`，创建或打开一个 Project。
2. 确认 Project 内只出现 `/projects/{id}/overview`、`/discover`、`/papers`、`/writing` 四个
   canonical 页面；`/projects/{id}`、`/project/{id}` 和 `/project/{id}/chat` 均应重定向到 Overview。
3. 在 Discover 输入检索意图并提交结构化 filters（年份、语言、领域、出版物类型）。结果必须是
   真实结构化论文对象，摘要保留完整 Provider 内容，不由前端解析 prose。
4. Provider 路径应遵守：Semantic Scholar Academic Graph 未认证优先；Crossref 仅用于 metadata
   enrichment / bounded fallback；`SEMANTIC_SCHOLAR_API_KEY` 是可选增强，不是启动条件。匿名
   429/401/403/超时应显示有界错误或回退，不得伪造论文或无限 retry。
5. 分别验证 Favorite、Download、Import 是独立动作。Import 只接受合法 arXiv 标识和 approved
   locator；Worker 负责下载、PDF 校验、解析、索引和 Project Papers 关联，前端显示 queued →
   processing → completed/failed。重复导入同一论文不得创建重复任务。

### 2. Papers → Reader / Profile

1. 在 Project Papers 打开已完成导入的论文，确认 `/paper/{id}` Reader 能加载 PDF、章节和可定位
   elements，并能执行原有正文问答/RAG。
2. 确认导入完成后 Paper Profile 在 Worker 中异步生成；Profile 失败不影响 Reader、Project Papers
   或既有 QA。

### 3. Writing → Evidence → Citation

1. 进入 `/projects/{id}/writing`，创建或打开 WritingDocument；确认 Tiptap、当前 revision 和
   导出能力保持可用。
2. 无选中文本时请求生成一段文字；服务端只能从当前 Project 已导入、可检索且有可用 Profile 的
   论文中取得 Evidence。返回 proposal，不应自动改正文。
3. 选中文本请求 rewrite；确认 proposal 显示结构化 citation 状态，并可显式 Replace、Copy 或
   放弃。接受后才创建新 revision；过期 `base_revision_id` 返回冲突。
4. 对包含 Citation Node 的 revision 执行 citation audit，确认 Project/Paper/Evidence 归属、
   source locator、lexical gate 和 semantic verifier 均执行；`unsupported` / `weak` 不得显示为
   verified。
5. 导出 Markdown、LaTeX、Word 或投稿包时，确认正文、引用映射和审计结果与当前 revision 一致。

### 4. Compatibility / developer-only checks

以下脚本仍用于兼容后端 artifact/tool 链路和历史数据回归，不是 V1 产品验收，也不应据此恢复
已删除的旧前端入口：

```bash
cd backend
PAPERAI_TOKEN='<access-token>' python -m scripts.verify_project_flow
docker compose run --rm --no-deps backend \
  python -m scripts.verify_agent_manuscript_flow
```

如需检查旧 artifact 导出或 Agent tool trace，可单独运行上述脚本；失败时应先判断是否为兼容
代码问题，不得把 Research Map 等非 V1 能力重新接回 canonical route。

### 5. Optional proxy acceptance

代理是可选增强，不是 V1 启动条件。默认直连即可完成 V1；只有在用户主动配置并希望验证宿主机代理时才执行以下检查：

```bash
docker compose exec backend sh -lc 'python -c "import os; print(os.environ.get(\"HTTPS_PROXY\") or \"direct\")"'
docker compose exec worker sh -lc 'python -c "import os; print(os.environ.get(\"HTTPS_PROXY\") or \"direct\")"'
```

随后由 Worker 发起一次有界 arXiv/Crossref 请求，确认代理路径成功；401/403/429/超时不得无限
重试。当前代理监听仅绑定宿主机 loopback 时，可记录为可选验证未执行；直连路径仍是默认验收路径，
不得因此阻塞 V1。

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
