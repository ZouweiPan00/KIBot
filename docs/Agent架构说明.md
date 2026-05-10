# KIBot Agent 架构说明

## 总体架构

```mermaid
graph TD
    A[FastAPI API 层] -->|call: chat / graph / report| B[KIBotOrchestrator]
    B -->|call: 7 tools| C[Tool Registry]
    C -->|read/write: textbooks, chunks, graph, decisions, report| D[Session Store]
    B -->|read: session context| D
    B -->|call: grounded prompt| E[LLM Client]
    E -->|write: usage / answer| D
```

主链路保持单入口：FastAPI 接收请求，Orchestrator 负责选择工具、读取 session 事实源、必要时调用 LLM，并把回答、token usage 或教师修改写回 Session Store。

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

## 架构方案对比

| 方案 | 适用阶段 | 优点 | 代价估计 | 调试难度 |
| --- | --- | --- | --- | --- |
| Single Orchestrator | P0 演示与闭环 | 状态单一、可重放、低延迟 | 每轮约 1 次 LLM，2k-8k input tokens | 2/5 |
| LangGraph | P1 复杂流程 | 有状态图、分支清晰、适合人工审核节点 | 每轮约 2-4 次 LLM，6k-20k input tokens | 3/5 |
| CrewAI | P2 多角色探索 | 角色拆分自然，适合头脑风暴式任务 | 每轮约 4-8 次 LLM，15k-50k input tokens | 4/5 |

当前选择 Single Orchestrator，是为了把 token 成本、状态一致性和比赛现场调试压力控制在可解释范围内。LangGraph 更适合后续把“抽取-融合-复核-报告”做成显式流程图；CrewAI 更适合多 agent 研究型扩展，不作为首版主链路。

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

## Prompt Engineering

### 图谱抽取 few-shot

system prompt 固定要求：

- 只抽取教材片段中明确出现的概念和关系。
- 节点名使用教材原文或等价短语，不扩写成外部知识。
- 关系类型限制在 `包含`、`前置`、`解释`、`对比`、`应用`。
- 输出 JSON，包含 `nodes`、`edges`、`evidence`、`confidence`。

few-shot 示例保持短小：

```json
{
  "chunk": "函数由定义域、值域和对应法则构成。一次函数是函数的一类。",
  "output": {
    "nodes": ["函数", "定义域", "值域", "对应法则", "一次函数"],
    "edges": [
      {"source": "函数", "target": "定义域", "type": "包含"},
      {"source": "函数", "target": "值域", "type": "包含"},
      {"source": "函数", "target": "对应法则", "type": "包含"},
      {"source": "一次函数", "target": "函数", "type": "解释"}
    ],
    "evidence": ["函数由定义域、值域和对应法则构成", "一次函数是函数的一类"],
    "confidence": 0.86
  }
}
```

### 防幻觉策略

- Retrieved chunks only：LLM 只能使用 RAG 返回片段和 session summary，不允许补充外部教材知识。
- Confidence output：每个答案、节点合并和关系抽取都输出 `confidence`；低于阈值时标记为待教师复核。
- JSON schema validation：LLM 输出先过 schema 校验；失败时不进入图谱写入。
- Fallback to rules：schema 失败或置信度过低时，退回规则抽取、BM25 证据排序和人工复核队列。

## Cluster-ready 方案

后续多 agent 集群可以按职责拆分：

- Corpus Agent：负责教材解析、章节质量检查、chunk 状态。
- Graph Agent：负责概念抽取、关系构建、图谱解释。
- Integration Agent：负责跨教材去重、合并、保留、冲突标记。
- Report Agent：负责生成 Markdown 报告和引用清单。
- Review Agent：负责教师反馈落库和变更审计。

集群模式下仍建议由一个 coordinator 持有写权限，其他 agent 输出建议或 patch，避免并发覆盖 session 状态。

## Roadmap

- P0：BM25 检索。先保证教材片段召回稳定，所有回答和图谱抽取都能追溯到 chunk evidence。
- P1：LLM secondary dedup。对规则去重后的候选概念做二次语义合并，输出合并理由、证据和置信度。
- P2：Multi-agent cluster。拆分 Corpus、Graph、Integration、Report、Review agents，但保留 coordinator 单点写入 session。

## F 创新与自由发挥

赛题 F 维度要求在本文独立说明“做了什么、为什么做、效果如何”。KIBot 的创新不是堆 Agent 数量，而是把教材整合做成可复核、可解释、低成本、可部署的 AI 工程闭环。

| 创新类型 | 做了什么 | 为什么做 | 效果与证据路径 |
| --- | --- | --- | --- |
| 功能创新 | Session-grounded tool registry，把教材、图谱、整合决策、报告、token 用量统一暴露给 Agent | 教师复核时最怕“聊天里说了但系统状态没变”，因此 Agent 必须先读 session facts | `backend/agent/orchestrator.py` 的 `build_context()`；`backend/tools/*`；`tests/test_agent_tools.py` |
| 功能创新 | 教师反馈结构化写回，支持 explain/keep/remove/merge/split，并同步图谱状态和报告 stale note | 赛题要求教师多轮对话能真实修改整合结果，而不是只给自然语言安慰 | `backend/services/dialogue.py` 的 `_apply_intent()`、`_update_graph_status()`、`_mark_report_stale()`；`frontend/src/components/RightTabs.tsx` 教师对话 Tab |
| 技术创新 | Deterministic-vs-LLM 路由：状态、统计、token、压缩率等问题走 deterministic summary；解释类问题才调用 LLM | 决赛现场 LLM key、网络和 token 成本都不稳定，状态类问题不应浪费模型调用 | `backend/agent/orchestrator.py` 的 `_should_call_llm()`；`tests/test_orchestrator.py` |
| 技术创新 | 轻量混合 RAG：BM25 + hashed vector cosine + chapter/concept boost，并返回分项分数 | 在无法下载大 embedding 模型或向量库的环境下，仍保留“关键词 + 向量 + 教学语境”的混合检索信号 | `backend/services/retriever.py`；`tests/test_retriever.py` 覆盖 BM25、vector fallback、top-5、教材隔离 |
| 技术创新 | LLM-first graph extraction + deterministic fallback | LLM 可用时争取高质量抽取；LLM 不可用或 JSON 失败时仍能演示图谱与 RAG 主链路 | `backend/services/graph_builder.py`；`tests/test_graph_builder.py` 的 invalid AI JSON/shape fallback 用例 |
| 工程创新 | Token observability 贯穿 LLM client、Graph/RAG/Dialogue API 和前端 Token 面板 | 让评委能看到成本控制，而不是只听“我们很省 token” | `backend/schemas/session.py` 的 `TokenUsage`；`backend/services/llm_client.py`；`backend/api/graph.py`；`backend/services/retriever.py`；`frontend/src/components/RightTabs.tsx` |
| 工程创新 | Docker/ModelScope-ready 部署，容器内构建 React dist 并由 FastAPI 托管 | 评分要求公网可访问，魔搭创空间默认 7860，部署路径要足够短 | `Dockerfile` 暴露并启动 `7860`；`docker-compose.yml`；`docs/部署说明.md` |
| 体验创新 | ECharts force graph + Sankey 整合流同屏，搜索、点击详情、频次/重要度映射 | Force graph 展示概念关系，Sankey 展示“教材来源 -> 整合概念”的压缩路径，两者互补 | `frontend/src/components/KnowledgeWorkspace.tsx` 的 graph、search、detail、Sankey 配置 |
| 体验创新 | Agent 集群 Beta 面板先暴露未来角色边界 | 即使主链路是单 orchestrator，也让评委看到多 Agent cluster-ready 的演进方向 | `frontend/src/components/RightTabs.tsx` 的 `ClusterPanel()`；本文“Cluster-ready 方案” |

## P2 技术报告草案/实验设计

建议提交题目：`低成本混合 RAG 在多教材整合问答中的效果分析`。该主题最贴合现有代码，也最容易用实验数据支撑 P2：无需重写系统，只需把已有 `tests/test_retriever.py` 扩展成 20-50 题 benchmark。

### 研究问题

1. 在医学教材多本并行、术语重复率高的场景中，纯 term overlap、BM25、hashed vector、Hybrid rerank 哪一种更稳定？
2. 在 chunk size 为 300/700/1200 时，top-5 引用命中率、平均响应时间、输入 token 成本如何变化？
3. deterministic fallback 是否能在 LLM 不可用时保持“有引用、有证据、可演示”的最低质量线？

### 实验矩阵

| 实验 | Baseline | 变量 | 指标 | 当前证据 | P2 补数方式 |
| --- | --- | --- | --- | --- | --- |
| RAG 检索策略 | term overlap | BM25 / hashed vector / BM25+vector / Hybrid | top-1 命中、top-5 召回、引用准确率、MRR | `tests/test_retriever.py` 已覆盖 BM25 排序和 vector fallback | 准备 20-50 个教师问题，标注 expected chunk/chapter |
| 分块粒度 | 700/80 | 300/50、700/80、1200/120 | 引用命中、平均 source chunk 长度、LLM input tokens | `backend/services/chunker.py` 默认 700/80 符合赛题 500-800/50-100 | 临时参数化 chunker，重建 session chunks 后跑同一题集 |
| LLM 成本路由 | all-LLM | deterministic status route | LLM calls、input/output/total tokens、回答延迟 | `KIBotOrchestrator._should_call_llm()`；Token 面板 | 对 10 个状态类问题 + 10 个解释类问题做 A/B |
| 图谱抽取稳定性 | LLM only | LLM-first + schema validation + deterministic fallback | 失败恢复率、有效节点数、噪声节点率 | `tests/test_graph_builder.py` 覆盖 AI JSON 失败回退 | 构造无效 JSON、空关系、章节噪声样例 |
| 教师反馈闭环 | chat-only | structured writeback | 决策 action 命中率、图谱 status 更新率、报告 stale note 更新率 | `backend/services/dialogue.py`；`tests/test_dialogue.py` | 用 keep/remove/merge/split/explain 五类语句各 5 条 |
| 压缩质量 | naive truncation | integration decision compact note budget | 压缩比、教学完整性人工评分、保留来源覆盖率 | `integration_engine._compression_stats()` 控制 `ratio <= 0.30` | 对 7 本教材输出报告后抽样人工复核 |

### 建议结果表模板

| 策略 | top-1 命中率 | top-5 召回率 | 引用准确率 | 平均延迟 ms | 平均 input tokens | 结论 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Term overlap | 待测 | 待测 | 待测 | 待测 | 0 | 关键词重复时可用，短 query 和同义表达不稳 |
| BM25 | 待测 | 待测 | 待测 | 待测 | 0 | 对重复医学术语排序更稳 |
| Hashed vector | 待测 | 待测 | 待测 | 待测 | 0 | 无外部模型时提供轻量向量信号 |
| Hybrid | 待测 | 待测 | 待测 | 待测 | 0 | 预期最佳，兼顾术语、章节和图谱概念 |
| Hybrid + LLM answer | 待测 | 待测 | 待测 | 待测 | 待测 | 回答更自然，但成本更高 |

### 评测数据格式

```json
{
  "question": "炎症反应的核心机制是什么？",
  "type": "事实性",
  "expected_textbook": "病理学",
  "expected_chapter": "炎症",
  "expected_terms": ["血管反应", "防御性反应", "损伤因子"],
  "difficulty": 2
}
```

### 报告结论写法

若数据符合预期，P2 报告可以得出以下工程结论：KIBot 的 Hybrid RAG 在不依赖外部 embedding 服务的条件下，利用 BM25 保障术语召回，用 hashed vector 处理短 query 和词项组合，用 chapter/concept boost 对齐教学语境；再通过 deterministic-vs-LLM 路由把状态类问题从模型调用中剥离。该方案牺牲了一部分真实语义 embedding 能力，但换来了比赛现场可部署、可解释、可复现和成本可控的优势。

## P0/P1/P2 覆盖表（Agent/RAG/Prompt/Innovation）

| 视角 | P0 覆盖 | P1 覆盖 | P2/挑战加分潜力 | 证据路径 |
| --- | --- | --- | --- | --- |
| Agent 架构 | Single orchestrator、session store、tool registry、教师对话 | deterministic-vs-LLM 成本路由、token observability | cluster-ready: Corpus/Graph/Integration/Report/Review agents | `backend/agent/orchestrator.py`；`backend/tools/*`；本文“Cluster-ready 方案” |
| RAG Pipeline | 700/80 chunk、top-5、引用、source chunk | BM25 + hashed vector + chapter/concept boost，返回分项分数 | RAG benchmark：策略、分块、延迟、token A/B | `backend/services/chunker.py`；`backend/services/retriever.py`；`tests/test_retriever.py` |
| Prompt 工程 | JSON schema、few-shot、retrieved chunks only | confidence、防幻觉、schema fallback | prompt 模板对知识点准确率影响实验 | 本文“Prompt Engineering”；`backend/services/graph_builder.py`；`backend/services/retriever.py` |
| 图谱整合 | merge/keep/remove/split 决策、压缩率 <=30% | Sankey 可视化、教师复核写回 | 相似度阈值、embedding 模型、压缩质量评测 | `backend/services/integration_engine.py`；`frontend/src/components/KnowledgeWorkspace.tsx` |
| 工程部署 | FastAPI + React SPA、本地运行 | Docker、7860、ModelScope-ready | 性能监控、缓存、并发处理实验 | `Dockerfile`；`docker-compose.yml`；`docs/部署说明.md` |
| F 创新 | 超出 P0 的结构化闭环说明 | 多项功能/技术/工程/体验创新 | 用 P2 报告把创新量化为实验数据 | 本文“F 创新与自由发挥”；`docs/P2技术报告草案.md` |

## 评分标准逐项对照

### D. Agent 架构设计

| 子项 | 评分要求 | 文档/代码对应 |
| --- | --- | --- |
| 架构总览与清晰度 | 架构描述、职责清晰、Mermaid 图 | 本文“总体架构” Mermaid；`backend/agent/orchestrator.py`；`backend/tools/*` |
| 设计决策论证 | 说明为什么单 Agent，讨论替代方案 | “设计原则”和“架构方案对比”解释 Single Orchestrator vs LangGraph vs CrewAI，并给出 token/调试成本估算 |
| RAG Pipeline 设计 | 分块、embedding、检索、引用 | `backend/services/chunker.py` 使用 700/80；`backend/services/retriever.py` 使用 BM25 + hashed vector embedding + concept/chapter boost |
| Prompt 工程 | 格式约束、few-shot、防幻觉 | “Prompt Engineering” 章节；graph prompt 要求 JSON schema、confidence、evidence |
| 已知局限与改进 | 局限和具体路线图 | “Roadmap”和“Cluster-ready 方案” |

### P0 主链路

1. 上传教材：FastAPI `textbooks` router 负责流式保存文件，parser 输出统一 schema。
2. 构建图谱：Graph API 先尝试 LLM 抽取，失败回退 deterministic graph，保证演示可用。
3. 跨教材整合：Integration API 写入结构化决策，action 覆盖 merge/keep/remove/split。
4. RAG 问答：Retriever 返回 top-5 chunk、citation 和分数组成，LLM prompt 限定 retrieved chunks only。
5. 教师复核：DialogueService 解析 explain/keep/remove/merge/split，并写回决策、图谱状态和 report stale note。

### P1 加分链路

- 混合检索：BM25 负责精确术语召回，hashed vector embedding 负责轻量向量相似度，concept/chapter boost 做重排序。
- 可视化增强：ECharts graph + Sankey；颜色、大小、形状三维映射；搜索和点击详情。
- 成本观测：`TokenUsage` 在 LLM client、graph client 和前端 Token 面板中贯通。
- Docker 部署：Dockerfile 在镜像中构建 React dist 并启动 FastAPI，魔搭运行端口 7860。

### P2 技术报告候选

题目建议：`低成本混合 RAG 在多教材整合中的效果分析`。

实验设计可以直接复用当前工程：

| 实验组 | 检索策略 | 预计观察 |
| --- | --- | --- |
| Baseline | term overlap | 对重复医学术语有召回，但排序不稳定 |
| BM25 | BM25Okapi | 重复关键术语得分更合理 |
| BM25 + vector | BM25 + hashed vector cosine | 在无 BM25 或短 query 情况下仍保留向量相似度信号 |
| Hybrid | BM25 + vector + concept/chapter | 更贴近教学章节和图谱概念 |

已有自动化证据：`tests/test_retriever.py` 覆盖 BM25 排序、向量分数参与、未选教材隔离和 RAG API fallback。赛后可扩展为 20-50 个教师问题，计算 top-1/top-5 命中率、引用准确率、响应时间和 token 消耗。

## 创新点说明（摘要版）

1. Session-grounded tool registry：所有 Agent 回答先读取 session facts，再决定是否调用 LLM，避免把聊天历史当事实源。
2. Deterministic-vs-LLM 成本路由：状态类问题走 deterministic summary，解释类问题才调用 LLM，降低 token 成本。
3. 混合 RAG fallback：在无法下载大 embedding 模型的比赛环境中，用 hashed vector embedding 提供可解释、零依赖的向量检索信号，同时保留未来替换 BGE/FAISS 的接口。
4. 教师反馈写回结构化状态：keep/remove/merge/split 不只存在聊天文本中，会更新 integration decision、graph status 和 report stale 标记。
5. 可视化整合流：Sankey 把“教材来源 -> 整合概念”的压缩路径可视化，补充 force graph 难以表达的去重过程。
