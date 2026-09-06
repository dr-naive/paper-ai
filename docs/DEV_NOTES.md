# Development Notes

这些约定用于后续代码迭代。修改前尽量先读本文件和相关模块代码。

## 推荐维护方式

1. V1 开发首先遵循根目录 `AGENTS.md`。
2. 每个 Codex 会话读取 `docs/spec-v2/execution/EXECUTION_INDEX.md`，只加载当前 Block 所需规范。
3. 当前施工状态查看 `docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md`。
4. 涉及接口时同步检查并更新 `docs/API.md`。
5. 涉及用户流程时在 Block / Phase 验收点运行相关 smoke，而不是每个小改动后全量运行。
6. 长期风险查看 `docs/TODO_OR_RISKS.md`。

## Git 提交与远程推送

- 所有用户可见的回复、提交信息和推送说明使用中文；代码和标准技术名称可保留原文。
- 推送前必须先说明目标远程、分支、提交标题、变更摘要，以及是否会改写远程历史。
- 只有用户明确同意后，才允许执行 `git push` 或任何形式的强制推送。
- 用户未确认前，可以完成本地修改、测试和提交，但不得同步远端。

## 启动约定

项目统一使用 Docker Compose v2，不再维护 systemd 或直接运行 Python/Node 的启动脚本。根目录的 `start.sh`、`stop.sh` 和 `restart.sh` 仅封装 Docker Compose。

日常命令：

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend
docker compose restart backend frontend
docker compose down
```

不要使用旧版 `docker-compose`，也不要在停止服务时添加 `-v`。

## 环境变量

配置入口：`backend/app/config.py`

加载优先级：

1. `backend/.env`
2. 项目根目录 `.env`

请使用 `.env.example` 作为模板，不要提交真实 API key。

## 数据库

Docker Compose 使用 PostgreSQL：

```text
postgresql+asyncpg://postgres:postgres@db:5432/paperai
```

数据库保存在 `postgres_data` volume，文件和向量数据保存在 `paperai_data` volume。

## 前端开发约定

- 页面放在 `frontend/src/views`。
- API 调用放在 `frontend/src/api`。
- 路由和登录拦截在 `frontend/src/router/index.ts`。
- UI 库是 Arco Design Vue，后续新增页面优先沿用。
- Axios 已统一注入 Bearer token，不要在页面里重复拼 token，除非上传等特殊请求确实需要覆盖 header。

## 后端开发约定

- 新 API 优先放入现有业务 router，保持路径前缀一致。
- 认证相关复用 `app.api.auth.get_current_user` 或 `app.api.papers.get_current_user_id`。
- 数据库模型修改后要确认 `init_db()` 是否足够，生产环境需要迁移方案。
- LLM 调用优先走 `app.llm.client.get_llm_client()`。
- 论文知识库能力优先走 `app.rag.knowledge_base.get_knowledge_base()`。
- 长任务需要更新任务状态，避免前端轮询卡死。

## 冒烟测试是什么

冒烟测试不是完整测试。它是一份很短的检查清单，用来确认“服务没有炸，主流程还能走”。

典型做法：

1. 改完代码后启动服务。
2. 打开前端。
3. 按清单走一遍关键路径，例如登录、上传论文、查看列表、打开阅读器、提问。
4. 每一步只确认最关键的结果，不追求覆盖所有边界条件。

它的价值是快速发现低级回归，例如：

- 后端启动失败。
- 前端白屏。
- 登录接口路径错了。
- token 没带上。
- 上传后任务状态不更新。
- 问答接口 500。

具体清单见 `docs/SMOKE_TESTS.md`。

## 代码修改后的检查节奏

不要每修改一个小文件就执行全量测试。

开发过程中：

- 可按需运行 targeted test / typecheck / API check；
- 用于快速排错，不要求因此 commit。

完整 Implementation Block 完成后，再集中运行该 Block 相关测试。

Phase 完成后，再执行需要的更广 regression / build / smoke。

常见命令：

前端：

```bash
cd frontend
npm run build
```

后端：

```bash
docker compose exec backend pytest -q
```

具体当前 Block 应运行哪些检查，以
`docs/spec-v2/execution/EXECUTION_INDEX.md`、当前 feature spec 和
`docs/spec-v2/execution/IMPLEMENTATION_PROGRESS.md` 为准。
