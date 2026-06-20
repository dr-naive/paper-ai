# PaperAI

PaperAI 是一个智能论文精读 AI Agent 系统。项目支持上传 PDF 论文、解析论文结构、抽取图表内容、构建论文知识库，并围绕论文提供问答、结构化摘要、深度解读、阅读管理和笔记能力。

## 技术栈

前端：

- Vue 3
- Vite
- TypeScript
- Vue Router
- Pinia
- Arco Design Vue
- Axios
- ECharts

后端：

- FastAPI
- SQLAlchemy async
- SQLite 本地开发 / PostgreSQL Docker 部署
- LangChain
- LangGraph
- ChromaDB
- OpenAI-compatible LLM API
- pdfplumber / PyMuPDF / pypdf

## 目录结构

```text
.
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/              # REST API 路由
│   │   ├── agent/            # LangGraph Agent 流程
│   │   ├── llm/              # LLM 客户端
│   │   ├── models/           # SQLAlchemy 数据模型
│   │   ├── parsers/          # PDF 图表和多媒体解析
│   │   ├── rag/              # 分块、Embedding、向量库
│   │   ├── utils/            # 工具模块
│   │   ├── config.py         # 应用配置
│   │   ├── database.py       # 数据库连接
│   │   └── main.py           # FastAPI 入口
│   ├── data/                 # 后端运行期数据
│   └── requirements.txt
├── frontend/                 # Vue 前端
│   ├── src/
│   │   ├── api/              # 前端 API 客户端
│   │   ├── components/       # 复用组件
│   │   ├── router/           # 路由和登录拦截
│   │   └── views/            # 页面
│   └── package.json
├── data/                     # 根目录运行期任务数据
├── logs/                     # 服务日志
├── paperai.db                # 本地 SQLite 数据库
├── docker-compose.yml        # Docker 部署配置
├── paperai-backend.service   # systemd 后端服务
├── paperai-frontend.service  # systemd 前端服务
├── start.sh                  # 统一启动脚本
├── stop.sh                   # 停止脚本
└── restart.sh                # 重启脚本
```

## 推荐启动方式

本项目后续维护建议以 systemd 为主，让系统自动守护后端和前端服务。

首次部署或服务文件变更后：

```bash
sudo cp paperai-backend.service /etc/systemd/system/
sudo cp paperai-frontend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable paperai-backend paperai-frontend
sudo systemctl start paperai-backend paperai-frontend
```

日常操作：

```bash
sudo systemctl status paperai-backend paperai-frontend
sudo systemctl restart paperai-backend paperai-frontend
sudo systemctl stop paperai-backend paperai-frontend
```

也可以使用项目脚本作为便捷入口：

```bash
./start.sh
./restart.sh
./stop.sh
```

默认访问地址：

- 前端：http://localhost:5173
- 后端：http://localhost:8000
- API 文档：http://localhost:8000/docs

日志位置：

- 后端：`logs/backend.log`
- 前端：`logs/frontend.log`

## 本地开发命令

后端：

```bash
cd backend
../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

前端：

```bash
cd frontend
npm run dev
```

前端构建检查：

```bash
cd frontend
npm run build
```

## 维护文档

后续修改代码前，优先阅读这些文档：

- `docs/ARCHITECTURE.md`：系统结构和核心流程
- `docs/API.md`：主要 API 路径和前后端调用关系
- `docs/DEV_NOTES.md`：开发约定、启动方式、冒烟测试说明
- `docs/SMOKE_TESTS.md`：手动冒烟测试清单
- `docs/TODO_OR_RISKS.md`：已知风险和待处理问题
- `.env.example`：环境变量模板

