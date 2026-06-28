# Smoke Tests

冒烟测试是一份“改完代码后快速确认主流程还能用”的清单。它不替代单元测试和集成测试，只用于快速发现明显回归。

## 准备

确认服务运行：

```bash
sudo systemctl status paperai-backend paperai-frontend
```

如果未运行：

```bash
sudo systemctl restart paperai-backend paperai-frontend
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
tail -n 200 logs/backend.log
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
