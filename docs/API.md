# API

本文档记录当前后端主要 API 路径，以及前端 API 客户端的调用关系。以后修改接口时，先同步这里，避免前后端路径漂移。

## 认证

Router：`backend/app/api/auth.py`

前缀：`/api/auth`

| Method | Path | 用途 | 前端调用 |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | 登录并返回 access token | `frontend/src/api/auth.ts` |
| POST | `/api/auth/register` | 注册用户 | `frontend/src/api/auth.ts` |
| GET | `/api/auth/users/me` | 获取当前用户 | 后端存在；前端当前疑似未对齐 |

认证方式：

```text
Authorization: Bearer <access_token>
```

注意：当前前端 `auth.ts` 中存在 `/api/auth/me` 和 `/api/auth/logout` 调用，但后端当前代码没有对应路由。详见 `docs/TODO_OR_RISKS.md`。

## 论文

Router：`backend/app/api/papers.py`

前缀：`/api/v1/papers`

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/v1/papers/` | 获取论文列表，支持分页、状态、搜索 |
| POST | `/api/v1/papers/upload` | 上传 PDF 论文 |
| GET | `/api/v1/papers/tasks/{task_id}` | 获取后台处理任务状态 |
| GET | `/api/v1/papers/{paper_id}` | 获取论文详情 |
| GET | `/api/v1/papers/{paper_id}/pdf` | 获取论文 PDF 文件 |
| GET | `/api/v1/papers/{paper_id}/sections` | 获取论文章节 |
| DELETE | `/api/v1/papers/{paper_id}` | 删除论文 |
| POST | `/api/v1/papers/{paper_id}/qa` | 针对论文提问 |
| POST | `/api/v1/papers/{paper_id}/interpret` | 论文解读 |
| POST | `/api/v1/papers/{paper_id}/summarize` | 生成结构化摘要 |
| GET | `/api/v1/papers/{paper_id}/summary` | 获取结构化摘要 |

前端主要调用文件：`frontend/src/api/paper.ts`

注意：前端 `updateReadingStatus()` 调用了 `PATCH /api/v1/papers/{paper_id}/status`，但当前后端 `papers.py` 中未看到对应 router。详见 `docs/TODO_OR_RISKS.md`。

## 聊天会话

Router：`backend/app/api/chat.py`

前缀：`/api/v1/chat`

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/v1/chat/sessions` | 获取会话列表 |
| POST | `/api/v1/chat/sessions` | 创建会话 |
| DELETE | `/api/v1/chat/sessions/{session_id}` | 删除会话 |
| GET | `/api/v1/chat/sessions/{session_id}/messages` | 获取会话消息 |
| POST | `/api/v1/chat/sessions/{session_id}/ask` | 在会话中提问 |
| GET | `/api/v1/chat/papers/{paper_id}/summary` | 获取摘要缓存 |
| POST | `/api/v1/chat/papers/{paper_id}/summarize` | 生成摘要并缓存 |
| GET | `/api/v1/chat/papers/{paper_id}/interpret/{interpret_type}` | 获取解读缓存 |
| POST | `/api/v1/chat/papers/{paper_id}/interpret/{interpret_type}` | 生成解读并缓存 |

前端主要调用文件：`frontend/src/api/paper.ts`

## 已移除接口

当前不提供笔记功能，`/api/v1/notes` 未挂载到 FastAPI 应用。

## 前端 Axios 约定

文件：`frontend/src/api/index.ts`

- `baseURL = import.meta.env.VITE_API_BASE_URL || ''`
- 请求前自动从 `localStorage.access_token` 注入 Bearer token。
- 收到 401 时删除 token 并跳转 `/login`。

如果前后端不同源运行，需要配置：

- `VITE_API_BASE_URL=http://localhost:8000`，或
- 反向代理。

当前 Docker 前端通过 Nginx 将 `/api/` 代理到 backend 容器，通常无需设置该变量。
