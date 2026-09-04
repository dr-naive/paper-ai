# Development Notes

这些约定用于后续代码迭代。修改前尽量先读本文件和相关模块代码。

## 推荐维护方式

1. 所有 V1 开发先遵循根目录 `AGENTS.md` 的文档读取顺序。
2. 当前产品与施工规范以 `docs/spec-v2/` 为准。
3. 当前实施进度与跨会话交接以 `docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md` 为准。
4. 本文件只记录日常开发、启动、调试和环境操作约定，不承担产品或架构权威。
5. 涉及接口时同步检查并更新 `docs/API.md`。
6. 涉及用户流程时运行 `docs/SMOKE_TESTS.md` 中相关场景。
7. 遇到长期风险查看 `docs/TODO_OR_RISKS.md`。

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

## 代码修改后的最低检查

前端改动：

```bash
cd frontend
npm run build
```

后端改动：

```bash
docker compose exec backend pytest -q
```

如果当前测试不完整，至少执行：

```bash
docker compose up -d --build backend
curl http://localhost:8000/health
```

然后访问：

```text
http://localhost:8000/health
http://localhost:8000/docs
```
