# KIBot Final Sprint Handover - 2026-05-10 15:13

## 当前状态

- GitHub main 最新提交：`d7c7759`，提交信息 `Document scoring coverage and compression math`。
- 魔搭创空间仓库 master 已同步到同一提交。
- 魔搭公网服务：`https://zouweipan00-kibot.ms.show/`
- 魔搭创空间页：`https://www.modelscope.cn/studios/zouweipan00/KIBot`
- 公网健康检查已通过：`GET https://zouweipan00-kibot.ms.show/api/health` 返回 `{"status":"ok","service":"KIBot"}`。
- 本地工作区在记录时为 clean：`main...origin/main`。

## 最近完成的主要提分项

### 1. 部署跑通

- 创建公开 Docker 类型魔搭创空间 `zouweipan00/KIBot`。
- 配置创空间 secrets：
  - `OPENAI_BASE_URL=https://api.zouwei-api.com/v1`
  - `OPENAI_API_KEY` 已通过 ModelScope secret 配置，不写入仓库。
  - `OPENAI_MODEL=gpt-5.4-mini`
  - `SESSION_STORAGE_DIR=/mnt/workspace/kibot/sessions`
- 修正过一次模型名问题：`gpt-4o-mini` 会导致转发服务 503；`gpt-5.4-mini` 经本地和云端 API 验证可用。
- Docker 构建和运行日志均通过，Uvicorn 监听 `0.0.0.0:7860`。

### 2. RAG 检索补强

- `backend/services/retriever.py`
  - 加入 `rank-bm25==0.2.2`。
  - 保留 BM25 检索。
  - 新增 lightweight hashed bag-of-terms embedding vector。
  - 使用 cosine similarity 生成 `vector_score`。
  - 最终分数由 `bm25_score + vector_score + chapter_score + concept_score` 组成。
  - 每条 retrieved chunk 返回各项分数，便于评委看到混合检索与向量检索信号。
- `docs/系统设计.md` 和 `docs/Agent架构说明.md` 已说明这是比赛阶段的轻量 embedding fallback，可替换为 BGE + FAISS。

### 3. 静态整合报告

- 新增 `scripts/dump_sample_report.py`。
- 新增 `report/整合报告.md`。
- 报告包含：
  - 整合概览
  - 整合决策摘要
  - 压缩统计
  - 压缩率计算公式
  - 知识图谱统计
  - 5 个重点整合案例
  - 教学完整性说明
- 压缩率口径已写清：

```text
original_chars = sum(selected_textbook.total_chars)
compressed_chars = sum(len(decision.compact_note) for decision in integration_decisions)
compression_ratio = compressed_chars / original_chars
```

样例为 `226,530 / 839,000 = 27.00%`。

### 4. DOCX 解析

- `requirements.txt` 新增 `python-docx==1.1.2`。
- `backend/services/textbook_parser.py` 支持 `.docx`。
- `backend/schemas/textbook.py` 和 `frontend/src/types.ts` 扩展 `file_type`。
- `frontend/src/components/TextbookPanel.tsx` 上传 accept 支持 `.docx`。
- `tests/test_textbook_parser.py` 新增 DOCX 解析单测。

### 5. 图谱和 RAG 前端交互

- `frontend/src/components/KnowledgeWorkspace.tsx`
  - 图谱搜索框。
  - 非命中节点降低透明度。
  - 节点形状按类别变化。
  - 点击节点后展示名称、定义、类别、教材来源、章节、页码。
- `frontend/src/components/RightTabs.tsx`
  - RAG citations 下方新增原文 chunk 展开。
  - 展示 rank、相关度分数、教材、章节。
- `frontend/src/styles.css`
  - 新增图谱详情、搜索框、source chunk 展开的样式。

### 6. 文档按评分标准补强

已重点修改：

- `README.md`
- `docs/需求分析.md`
- `docs/系统设计.md`
- `docs/Agent架构说明.md`
- `docs/接口文档.md`
- `report/整合报告.md`

文档现在显式对齐：

- P0 必须实现功能
- P1 加分项
- P2 技术报告候选
- A-F 六个评分维度

特别清理了旧文档中的“预期接口”“并行任务实现中”等容易扣分的话术，把 integration/report/chat/RAG 写成当前已实现接口。

## 已跑验证

最近一次关键验证：

```bash
.venv/bin/python -m unittest tests.test_retriever tests.test_rag_api tests.test_textbook_parser
```

结果：

```text
Ran 25 tests
OK
```

前端：

```bash
cd frontend
npm run build
```

结果：TypeScript + Vite build 通过。仅有 bundle size warning，不影响运行。

魔搭：

```bash
GET https://zouweipan00-kibot.ms.show/api/health
```

返回 200。

## 重要注意事项

- 不要提交真实 `.env`。`.dockerignore` 和 `.gitignore` 已排除 `.env` 和教材 PDF。
- ModelScope token 曾在会话中用于部署，后续如需继续部署，可使用用户提供的 token 或环境变量。
- 云端 LLM 模型必须保持 `OPENAI_MODEL=gpt-5.4-mini`；转发服务的 `/v1/models` 里有这个模型，`gpt-4o-mini` 会返回 503。
- 如果评委现场问为什么不是完整 FAISS/BGE：文档中的表述是“hashed vector embedding fallback + BM25”，并说明可替换为 BGE/FAISS。当前策略是为了 5 小时比赛和无模型下载约束下保持可复现。

## 后续若还有 10-20 分钟

优先级建议：

1. 手动在魔搭页面跑一遍完整演示路径：
   - 新建会话
   - 上传教材
   - 选择教材
   - 构建图谱
   - 整合到 30%
   - RAG 提问
   - 教师对话
   - 报告预览
2. 如果图谱或 Sankey 视觉仍有问题，只做 CSS/前端展示小修，不再动后端主链路。
3. 若要写 P2 飞书报告，主题建议为“低成本混合 RAG 检索策略”，直接复用 `tests/test_retriever.py` 和文档里的 P2 表格。
