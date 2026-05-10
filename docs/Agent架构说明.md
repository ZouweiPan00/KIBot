# KIBot Agent 架构说明

## 设计原则

KIBot 第一版采用 single-orchestrator first。原因是比赛演示更需要稳定、可解释的主链路：教材解析、图谱、RAG、教师复核、报告生成应共享同一个 session 事实源，避免多个 agent 同时写状态造成不可复现结果。

同时，数据结构和工具边界保持 cluster-ready：未来可以把“教材解析 agent”“图谱 agent”“融合 agent”“报告 agent”拆分为协作节点，但它们仍通过同一个 session store 读写结构化状态。

## 单 Orchestrator

`KIBotOrchestrator` 当前职责：

- 从 session 构造上下文。
- 调用 session-grounded tools 获取教材、压缩统计、token、图谱、融合决策、报告状态。
- 对状态类问题返回 deterministic summary，减少不必要 LLM 调用。
- 对解释类问题调用 LLM，并在 system prompt 中限制只能使用提供的 session context。

这让系统在没有 LLM key 时仍能提供可演示的状态摘要。

## Tool Registry

当前工具以 Python 模块方式组织，可视为轻量 tool registry：

- `get_selected_textbooks(session)`
- `get_compression_stats(session)`
- `get_token_usage(session)`
- `get_graph_summary(session)`
- `get_integration_decisions(session)`
- `update_decision(session, decision_id, action, teacher_note)`
- `get_report(session)`

工具只接收 session 或明确参数，不直接依赖聊天历史。后续扩展多 agent 时，可把这些函数包装为显式 tool schema，由 orchestrator 或 agent cluster 统一调度。

## Session State

Agent 不把聊天记录当作唯一记忆。结构化 session 是事实源：

- 教材与章节：来自解析结果。
- chunk：来自 chunker。
- graph：来自 graph build API。
- integration decisions：由融合流程和教师修改写入。
- report：由报告生成流程写入。
- messages：可保存对话过程，但不替代结构化字段。

这种设计便于重放、调试和评委检查。

## Context Compaction

长对话下，Agent 上下文应按以下规则压缩：

1. 保留 session id、选中教材、图谱摘要、压缩统计、token usage。
2. 对历史消息抽取 `memory_summary`，只保存教师偏好、已确认决策、未完成问题。
3. 大体量教材正文不直接进入 prompt，只通过 RAG 检索片段进入。
4. 教师确认或修改必须写回 `integration_decisions`、`report` 或图谱字段，而不是只写入 `memory_summary`。

当前代码已有 `memory_summary` 字段和 orchestrator 读取逻辑；自动 compaction 策略可在后续 agent/chat API 中补齐。

## Token Observability

`TokenUsage` 包含：

- `calls`
- `input_tokens`
- `output_tokens`
- `total_tokens`

LLM client 优先使用 provider 返回的 `usage`；如果 provider 不返回 usage，则按字符数估算。工具层通过 `get_token_usage(session)` 暴露统计，便于前端展示成本、压缩率和调用次数。

## Cluster-ready 方案

后续多 agent 集群可以按职责拆分：

- Corpus Agent：负责教材解析、章节质量检查、chunk 状态。
- Graph Agent：负责概念抽取、关系构建、图谱解释。
- Integration Agent：负责跨教材去重、合并、保留、冲突标记。
- Report Agent：负责生成 Markdown 报告和引用清单。
- Review Agent：负责教师反馈落库和变更审计。

集群模式下仍建议由一个 coordinator 持有写权限，其他 agent 输出建议或 patch，避免并发覆盖 session 状态。

