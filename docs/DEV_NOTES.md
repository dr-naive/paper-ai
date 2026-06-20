# Development Notes

这些约定用于后续代码迭代。修改前尽量先读本文件和相关模块代码。

## 推荐维护方式

1. 先读 `README.md`、`docs/ARCHITECTURE.md` 和本文件。
2. 涉及接口时同步检查 `docs/API.md`。
3. 涉及用户流程时改完跑 `docs/SMOKE_TESTS.md` 中相关场景。
4. 遇到已知坑先看 `docs/TODO_OR_RISKS.md`。

## 启动约定

用户倾向使用 systemd 自动维护服务。后续默认以 systemd 作为推荐运行方式。

服务：

- `paperai-backend.service`
- `paperai-frontend.service`

日常命令：

```bash
sudo systemctl status paperai-backend paperai-frontend
sudo systemctl restart paperai-backend paperai-frontend
journalctl -u paperai-backend -n 100
journalctl -u paperai-frontend -n 100
```

项目日志：

```bash
tail -f logs/backend.log
tail -f logs/frontend.log
```

脚本：

- `start.sh`：复制 service 文件、reload systemd、启动后端、启动前端。
- `restart.sh`：重启服务。
- `stop.sh`：停止服务。
- `run_backend.sh`：后端 systemd 实际执行入口，运行 `uvicorn app.main:app --reload`。

注意：这些脚本和 service 文件包含绝对路径 `/home/ddd/project/myAgent`。移动项目目录时必须同步修改。

## 环境变量

配置入口：`backend/app/config.py`

加载优先级：

1. `backend/.env`
2. 项目根目录 `.env`

请使用 `.env.example` 作为模板，不要提交真实 API key。

## 数据库

默认配置：

```text
sqlite+aiosqlite:///./paperai.db
```

因为后端 service 的 working directory 是项目根目录，而 `run_backend.sh` 会 `cd backend`，实际 SQLite 相对路径需要以运行时 working directory 为准。调整启动方式时要特别核对数据库文件位置。

Docker Compose 使用 PostgreSQL：

```text
postgresql+asyncpg://postgres:postgres@db:5432/paperai
```

切换 SQLite/PostgreSQL 前需要确认数据迁移和表结构兼容。

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
cd backend
../.venv/bin/python -m pytest
```

如果当前测试不完整，至少执行：

```bash
cd backend
../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

然后访问：

```text
http://localhost:8000/health
http://localhost:8000/docs
```

