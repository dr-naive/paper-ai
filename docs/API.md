# API

> 状态：ACTIVE / CURRENT-CONTRACT-ONLY
>
> 本文档只记录当前代码中已经存在并完成验证的 API。
> `docs/spec-v2/` 中出现的未来 endpoint、DTO 或 route 只是施工目标，在对应实现与测试完成前不得提前写入本文。
>
> 每个实施 Phase 如果新增、删除或修改真实 API，必须在同一 Phase 更新本文和 `docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md`。

本文档记录当前后端主要 API 路径，以及前端 API 客户端的调用关系。以后修改接口时，先同步这里，避免前后端路径漂移。

## 认证

Router：`backend/app/api/auth.py`

前缀：`/api/auth`

| Method | Path | 用途 | 前端调用 |
| --- | --- | --- | --- |
| POST | `/api/auth/login` | 登录并返回 access token | `frontend/src/api/auth.ts` |
| POST | `/api/auth/register` | 注册用户 | `frontend/src/api/auth.ts` |
| GET | `/api/auth/users/me` | 获取当前用户及角色 | `frontend/src/api/auth.ts` |
| GET | `/api/auth/admin/users` | 管理员获取用户列表 | `frontend/src/api/auth.ts` |
| PATCH | `/api/auth/admin/users/{user_id}` | 管理员更新角色或启用状态 | `frontend/src/api/auth.ts` |

认证方式：

```text
Authorization: Bearer <access_token>
```

角色目前分为 `admin` 和 `user`。管理员接口只允许 `admin` 角色访问。
系统每次启动都会确保固定的 `admin` 管理员存在并处于启用状态；密码由 `DEFAULT_ADMIN_PASSWORD` 环境变量提供。

兼容性说明：如前端仍调用 `/api/auth/logout` 而后端没有对应路由，应在 `docs/TODO_OR_RISKS.md` 中以当前代码重新验证后记录；本文件只保留已经确认的接口事实。

## 管理员观测

Router：`backend/app/api/admin.py`

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/admin/dashboard` | 系统健康、使用量、AI Trace、七日趋势和最新评测汇总 |

该接口仅允许 `admin` 角色访问。AI Token 来自回答 Trace 的估算值，
用于观察趋势，不代表模型供应商账单；部署本版本后产生的回答会持久化统计。

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

阅读状态相关接口若在前后端存在契约差异，应以当前分支重新验证后记录到 `docs/TODO_OR_RISKS.md`；不要把未重新验证的历史风险继续固化在 API Contract 中。

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

## 文档维护规则

`API.md` 是当前实现 Contract，不是未来 API 设计文档。

以下接口只有在对应 Phase 实现、测试通过后才能加入：

- Project V1 新增 / 调整接口
- Literature Discovery API
- Favorite / Import API
- Project Context / Paper Profile API（如果最终对前端暴露）
- Writing Agent API
- Citation Verification API
- 新 Execution / SSE API

实现 API 时必须同步记录：

1. Method
2. Path
3. Request schema
4. Response schema
5. Ownership / auth requirement
6. Frontend caller
7. Backward compatibility
8. 对应测试

未来施工目标请查看 `docs/spec-v2/`，实施状态查看 `docs/spec-v2/08_IMPLEMENTATION_PROGRESS.md`。