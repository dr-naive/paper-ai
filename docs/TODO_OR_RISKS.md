# TODO / Risks

本文档记录当前代码中已经发现、但尚未处理的风险点。后续迭代前先看这里，避免重复踩坑。

## API 路径不一致

### 当前用户接口

前端：

```ts
request.get('/api/auth/me')
```

后端：

```text
GET /api/auth/users/me
```

影响：如果前端页面调用 `getCurrentUser()`，会出现 404。

建议：统一路径。可以选择：

- 后端新增兼容路由 `/api/auth/me`，或
- 前端改为 `/api/auth/users/me`。

### 退出登录接口

前端：

```ts
request.post('/api/auth/logout')
```

后端当前未看到 `/api/auth/logout`。

影响：如果前端调用 logout API，会出现 404。

建议：如果 JWT 无服务端黑名单，前端本地删除 token 即可；也可以后端增加空操作 logout 接口用于兼容。

### 阅读状态接口

前端：

```ts
PATCH /api/v1/papers/{paper_id}/status
```

后端 `papers.py` 当前未看到对应 router。

影响：收藏、阅读状态、阅读进度更新可能失败。

建议：要么实现后端接口，要么移除/调整前端调用。

## CORS 配置较宽

`backend/app/main.py` 中 CORS 当前为：

```python
allow_origins=["*"]
allow_credentials=True
```

同时存在 `is_allowed_origin()`，但没有实际接入 middleware。

影响：开发环境方便，但生产环境不够严谨。

建议：生产部署前按 `settings.CORS_ORIGINS` 收敛来源。

## 配置文件日志仍偏吵

`backend/app/config.py` 当前启动时会打印配置诊断信息。API key 已改为 masked 输出，但这些日志仍更像开发期诊断。

建议：生产环境进一步收敛配置打印，或接入标准 logger 并按 `DEBUG` 控制。

## 绝对路径绑定

这些文件包含 `/home/ddd/project/myAgent`：

- `start.sh`
- `stop.sh`
- `restart.sh`
- `run_backend.sh`
- `paperai-backend.service`
- `paperai-frontend.service`

影响：项目移动目录或换机器部署时会失败。

建议：systemd service 可以继续使用绝对路径，但需要在部署文档中明确；脚本可逐步改为根据自身路径计算项目根目录。

## 本地数据库路径需确认

默认数据库 URL：

```text
sqlite+aiosqlite:///./paperai.db
```

后端 service `WorkingDirectory` 是项目根目录，但 `run_backend.sh` 会 `cd backend` 后启动 uvicorn。

影响：SQLite 文件可能根据实际启动目录落在不同位置。

建议：明确 SQLite 绝对路径，或统一启动目录。

## 前端 systemd 服务未安装

本次冒烟测试中，后端 `paperai-backend.service` 已安装并运行，但系统中未找到 `paperai-frontend.service`。

影响：`5173` 端口无法由 systemd 自动守护；普通 `start.sh` 在没有 sudo/systemd bus 权限时只能尝试后台启动前端。

建议：在服务器终端执行：

```bash
sudo cp /home/ddd/project/myAgent/paperai-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable paperai-frontend
sudo systemctl start paperai-frontend
```

## 前端文件 watcher 上限

普通 `npm run dev` 会因为系统 watcher 上限报错：

```text
ENOSPC: System limit for number of file watchers reached
```

本次已将 `paperai-frontend.service` 和 `start.sh` 的前端启动补充为 `CHOKIDAR_USEPOLLING=true`，作为低权限环境下的可运行兜底。

长期建议：也可以提高系统 watcher 限制，例如调整 `fs.inotify.max_user_watches`。

## 论文解析结构化章节丢失

本次上传测试中，论文解析 Agent 日志显示 LLM 成功解析出 4 个章节，但 `_process_paper_async` 后续读取到的 `sections` 数量为 0，最终只保存了默认“全文”章节。

影响：阅读器章节导航和引用定位会退化。

建议：检查 `backend/app/agent/paper_parser/graph.py` 返回结构和 `backend/app/api/papers.py` 对 `parse_result.get('sections')` 的读取字段是否一致。

## 表格提取变量顺序问题

本次上传无表格 PDF 时出现 warning：

```text
PDF 表格提取失败: local variable 'tables_dir' referenced before assignment
```

影响：当 pdfplumber 没提取到表格并进入 VLM 表格图片路径时，该分支会失败。

建议：在 `backend/app/api/papers.py` 中先创建 `paper_storage_dir/images_dir/tables_dir`，再进入表格提取逻辑。

## Docker 与本地运行方式差异

本地默认 SQLite，Docker Compose 使用 PostgreSQL + Redis。

影响：两套环境的数据存储、连接方式和依赖服务不同，可能出现“本地可用、Docker 不可用”或反过来的情况。

建议：若要正式使用 Docker，补齐 Dockerfile、迁移策略、环境变量文档和 Compose 冒烟测试。

## 依赖目录可能被纳入项目

当前项目中存在：

- `.venv/`
- `frontend/node_modules/`
- `backend/lib/`

影响：仓库体积变大，依赖版本可能混乱。

建议：确认 `.gitignore` 是否覆盖这些目录；后续不要把依赖产物提交到版本库。

## 后端测试覆盖不足

当前只保留了最小应用导入测试。历史一次性 `test_*.py`、`check_*.py`、`analyze_*.py` 调试脚本已经清理。

建议：后续改后端时优先跑：

```bash
cd backend
../.venv/bin/python -m pytest
```

如果测试缺失，至少跑后端启动和关键 API 冒烟测试。
