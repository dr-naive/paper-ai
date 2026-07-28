# 回答链路可观测性

每个回答任务在 API 创建时生成一个 `trace_id`，该标识会贯穿：

```text
HTTP/SSE → Redis 回答任务 → Worker Job → QA Workflow → 结构化日志
```

SSE 的 `task` 事件、`X-Trace-Id` 响应头、任务状态接口和最终回答结果都会
返回同一个 `trace_id`。

## 指标

| 字段 | 含义 |
| --- | --- |
| `stage_timings_ms` | 每个工作流节点耗时 |
| `intent_ms` | 意图识别耗时 |
| `retrieval_ms` | 整体检索耗时 |
| `rerank_ms` | 候选重排的纯计算耗时 |
| `first_token_ms` | 从 Worker 开始工作流到收到模型首个思考或回答 token |
| `thinking_tokens` | 思考内容 token 估算值 |
| `answer_tokens` | 最终回答 token 估算值 |
| `total_ms` | 回答工作流总耗时 |
| `model_calls` | 主回答模型调用次数 |
| `citation_count` | 确定性引用数量 |
| `worker_retry_count` | Worker 任务重试次数 |
| `configured_model_max_retries` | 模型客户端允许的最大内部重试次数 |
| `failure_stage` | 失败节点；成功时为 `null` |

流式接口不保证供应商返回 usage，所以 token 字段带有
`token_count_type: estimated`，用于性能比较，不作为供应商账单依据。

## 存储与查询

- Worker 完成、失败或取消任务时输出一条 `answer_trace` JSON 结构化日志。
- Trace 在 Redis 中保存，TTL 与回答任务相同。
- 登录用户可查询自己任务的指标：

```http
GET /api/v1/chat/answer-tasks/{task_id}/trace
```

任务仍在运行时，接口返回当前阶段以及 `metrics_pending: true`；任务完成后
返回完整指标。
