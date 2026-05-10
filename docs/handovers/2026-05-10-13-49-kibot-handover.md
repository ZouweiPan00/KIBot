# KIBot Handover - 2026-05-10 13:49

本文件记录当前上下文窗口即将满时的 KIBot 开发状态。请从这里继续，不要重新梳理全历史。

## 当前分支与状态

- 工作区：`/Users/zouweipan00/1_Program/1_12_ZJU_Hackathon/project/.worktrees/kibot-core`
- 分支：`feature/kibot-core`
- 最新已提交 commit：`7e66818 fix: expose integration compression flow`
- GitHub remote：`https://github.com/ZouweiPan00/KIBot.git`
- 当前有未提交改动，集中在教材标题/章节识别、图谱过滤、前端对话与文案修复。

当前 `git status --short`：

```text
 M backend/services/graph_builder.py
 M backend/services/textbook_parser.py
 M frontend/src/App.tsx
 M frontend/src/api.ts
 M frontend/src/components/KnowledgeWorkspace.tsx
 M frontend/src/components/RightTabs.tsx
 M frontend/src/components/TextbookPanel.tsx
 M frontend/src/styles.css
 M frontend/src/types.ts
 M tests/test_graph_builder.py
 M tests/test_textbook_parser.py
```

## 已完成主体功能

当前主功能已经完成并合入 `feature/kibot-core`：

- FastAPI 后端骨架与 `/api/health`
- React/Vite 前端 dashboard
- JSON session store
- PDF/TXT/Markdown 上传与解析
- 700 字符 chunking，80 字符 overlap
- OpenAI-compatible LLM client，token usage tracking
- session-grounded agent tools
- knowledge graph API
- RAG retrieval API，默认本地 fallback，LLM 需显式 `use_llm=true`
- cross-textbook integration decisions
- Sankey integration flow
- integration stats，压缩比例目标 `<= 30%`
- teacher dialogue API
- report generation API
- docs/README
- Dockerfile、docker-compose、FastAPI 静态托管 React build

已验证过的稳定基线：

- 后端全量测试曾达到 `89 tests OK`
- 前端 `npm run build` 多次通过，仅有 ECharts large chunk warning
- `docker compose config` 通过
- secret scan 无真实 key 命中
- 本地 FastAPI smoke：
  - `/api/health` 返回 `{"status":"ok","service":"KIBot"}`
  - `/` 返回 `200 text/html`

## 已提交的最近关键修复

### `7e66818 fix: expose integration compression flow`

修复目的：解决前端没有显式触发 30% 压缩和 Sankey 整合流为空的问题。

内容：

- 左侧新增 `选择全部已上传教材`
- 中间新增 `整合到30%`
- 前端调用 `/api/integration/run`
- 前端显示压缩比例，标注 `目标≤30%`
- 刷新真实 Sankey、integration decisions、report
- 修复 `getIntegrationDecisions` 响应结构

验证：

- `npm run build` 通过
- 后端相关测试 `16 tests OK`
- secret scan 无命中
- subagent read-only review 通过
- 用真实 session 跑后端整合链路：
  - selected textbooks：7
  - decisions：1
  - Sankey nodes：151
  - Sankey links：150
  - original chars：3,436,979
  - compressed chars：794
  - ratio：0.0002

注意：当前压缩比例满足 `<=30%`，但内容偏短，后续可优化 compact note/report 质量，让“精华版”更像真实教材压缩产物。

## 用户刚反馈的问题

用户实际测试后指出：

1. 教材上传后显示为 `01__...`、`02__...`，没有显示正确教材名。
2. chapter 数量识别不对，例如 `02` 识别为 `1章/35万字`，怀疑 PDF 转换/章节识别问题。
3. 知识点没有经过 AI/过滤，例如 `第二章` 也被算作知识点。
4. 文案中 `医学教材知识整合工作台`、`医学知识图谱` 应该去掉 `医学`。
5. 看起来还没有对话能力。

## 当前未提交修复内容

这些改动已经写入文件，但还没有 commit。

### 1. 教材标题映射

文件：

- `backend/services/textbook_parser.py`
- `frontend/src/components/TextbookPanel.tsx`
- `frontend/src/components/KnowledgeWorkspace.tsx`

后端新增 `MEDICAL_TEXTBOOK_TITLES_BY_PREFIX`：

```text
01 -> 局部解剖学
02 -> 组织学与胚胎学
03 -> 生理学
04 -> 医学微生物学
05 -> 病理学
06 -> 传染病学
07 -> 病理生理学
```

解析新上传文件时，如果文件名前缀是 `01` 到 `07`，`ParsedTextbook.title` 会自动映射成正确教材名。

前端也新增 `displayTextbookTitle(book, index)`，用于将已有 session 中的 `01__` 等占位标题显示成正确教材名。`KnowledgeWorkspace` 也会 prettify Sankey label 中的旧标题。

### 2. 章节识别增强

文件：

- `backend/services/textbook_parser.py`
- `tests/test_textbook_parser.py`

改动：

- 新增 `FLEXIBLE_CHAPTER_HEADING_RE`
- 支持 PDF 提取出来的空格式章节标题，例如：
  - `第 一 章 细胞`
  - `第 2 节 结构`
- 新增 `_normalize_chapter_title`
  - `第 一 章 细胞` -> `第一章 细胞`
  - `第 2 节 结构` -> `第2节 结构`
- 新增测试 `test_parse_txt_detects_pdf_extracted_spaced_chapter_headings`

说明：这会改善 PDF 抽取后的章节识别，但不保证所有教材目录/页眉干扰都完美。后续若仍有少章问题，需要看真实 PDF 文本提取样本。

### 3. 图谱概念噪声过滤

文件：

- `backend/services/graph_builder.py`
- `tests/test_graph_builder.py`

改动：

- 图谱概念抽取不再把 `textbook_title` 和 `chapter` 拼入概念来源，只从 chunk content 抽取。
- 新增中文结构词过滤：
  - `第一章`
  - `第二章`
  - `第一节`
  - `第二节`
  - `目录`
  - `教材`
  - `学习目标`
  - `复习题`
  - 等
- 新增 `_clean_cjk_concept`，遇到 `第二章上皮组织` 会去掉章节前缀，保留 `上皮组织`。
- 新增测试 `test_filters_chapter_heading_tokens_from_chinese_concepts`。

说明：这还不是 LLM/AI 图谱抽取，只是规则图谱降噪。若想真正“过 AI”，下一步应把 graph builder 接入 LLM client，让 LLM 输出概念 JSON，再以规则抽取兜底。

### 4. 去掉“医学”文案

文件：

- `frontend/src/components/KnowledgeWorkspace.tsx`

改动：

- `KIBot 医学知识集成仪表盘` -> `KIBot 知识集成仪表盘`
- `医学教材知识整合工作台` -> `教材知识整合工作台`
- `医学知识图谱` -> `知识图谱`

### 5. 前端接入真实教师对话

文件：

- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `frontend/src/App.tsx`
- `frontend/src/components/RightTabs.tsx`

改动：

- 新增 `ChatResponse`
- 新增 `sendChatMessage(sessionId, message)`
- `App.tsx` 新增 `chatAnswer`、`chatLoading` 和 `handleTeacherMessage`
- `RightTabs` 的 `TeacherPanel` 不再是 placeholder：
  - 有 textarea
  - 有 `发送意见` button
  - 调用 `/api/chat/message`
  - 显示 KIBot 的 `assistant_message`

说明：后端 dialogue service 之前已经完成，支持 explain/keep/remove/merge/split 的规则意图解析和 session state 更新。

### 6. 小 UX 修补

文件：

- `frontend/src/components/TextbookPanel.tsx`
- `frontend/src/components/KnowledgeWorkspace.tsx`
- `frontend/src/styles.css`

改动：

- `选择全部已上传教材` 增加 loading 状态。
- `整合到30%` 在没有 selected textbook 时禁用。
- 新增 `.wideAction` 样式，避免按钮裸奔。

## 当前未提交修复已跑过的验证

已跑：

```text
.venv/bin/python -B -m unittest tests.test_textbook_parser tests.test_graph_builder tests.test_chat_api tests.test_dialogue tests.test_app_routes
```

结果：

```text
Ran 22 tests in 0.383s
OK
```

已跑：

```text
.venv/bin/python -m py_compile backend/services/textbook_parser.py backend/services/graph_builder.py
```

结果：通过，无输出。

已跑：

```text
npm run build
```

结果：通过，仅 ECharts large chunk warning。

最近一次 build 输出摘要：

```text
✓ 2213 modules transformed.
dist/index.html 0.52 kB
dist/assets/index-CaBIjmo0.css 8.18 kB
dist/assets/index-D8UDhtMU.js 1,281.47 kB
✓ built in 2.15s
```

## 下一步建议

### 立即下一步

1. 再跑一次完整验证：

```bash
cd /Users/zouweipan00/1_Program/1_12_ZJU_Hackathon/project/.worktrees/kibot-core
.venv/bin/python -B -m unittest discover tests
npm run build --prefix frontend
rg -n "s""k-|api\\.zouwei|OPENAI_API_KEY=.*s""k" README.md docs frontend/src backend app.py .env.example Dockerfile docker-compose.yml .dockerignore
```

2. 如果都通过，commit 当前未提交修复：

```bash
git add backend/services/textbook_parser.py backend/services/graph_builder.py tests/test_textbook_parser.py tests/test_graph_builder.py frontend/src/App.tsx frontend/src/api.ts frontend/src/types.ts frontend/src/components/TextbookPanel.tsx frontend/src/components/KnowledgeWorkspace.tsx frontend/src/components/RightTabs.tsx frontend/src/styles.css
git commit -m "fix: improve demo data quality and teacher dialogue"
```

3. 之后再决定是否合并到 `main` 并 push 给 GitHub 中期 AI Reviewer。

### 中期评审提交建议

由于赛事方 AI Reviewer 大概率抓默认分支 `main`，建议：

1. 完成并 commit 当前修复。
2. 运行最终验证。
3. 合并到 main。
4. push origin main。
5. 给赛事方提交仓库主页：`https://github.com/ZouweiPan00/KIBot`

不要只推 `feature/kibot-core`，除非可以明确告诉评审看该分支。

## 已知风险

- 当前知识图谱仍是规则抽取，不是真 LLM 概念抽取。已过滤明显噪声，但“AI 图谱质量”仍是后续高 ROI 优化项。
- 章节识别增强后对新上传文件有效；已经上传过的 session 数据不会自动重新解析，除非重新上传或写 migration。
- 当前真实 session 数据在 `data/sessions/...`，不应提交。
- 30% 压缩满足数值要求，但 compact note 偏短，报告内容质量可继续增强。
- Docker build 尚未真正跑过，本机 Docker daemon socket 不可用；`docker compose config` 通过。

## 当前对话约定

- 与用户对话使用中文。
- 与 subagent 对话使用英文。
- 尽可能并行，但要用独立 worktree 或明确写入范围，避免文件冲突。
