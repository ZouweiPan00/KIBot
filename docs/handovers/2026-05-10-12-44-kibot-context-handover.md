# KIBot Context Handover - 2026-05-10 12:44

本文件用于在上下文窗口接近上限、subagent 被手动停止后，交接当前会话背景、设计决策、代码进展和下一步动作。

## 1. 当前快照

- 项目名：KIBot
- 前端展示名：`KIBot - A Knowledge Integration Agent`
- 项目定位：面向多教材去重、融合与 30% 精华压缩的学科知识整合智能体
- GitHub 仓库：https://github.com/ZouweiPan00/KIBot
- 本地主仓库：`/Users/zouweipan00/1_Program/1_12_ZJU_Hackathon/project`
- 当前开发 worktree：`/Users/zouweipan00/1_Program/1_12_ZJU_Hackathon/project/.worktrees/kibot-core`
- 当前分支：`feature/kibot-core`
- 当前 HEAD：`46f7587 feat: add textbook chunking`
- 当前状态：worktree 在写入本 handover 前为 clean；Task 6 chunking 已由 subagent 提交，但还需要主会话复核后再视为完成。

## 2. 赛题和产品决策

### 赛题要求

主办方题目是开发一个学科知识整合智能体，围绕多本教材的知识整合：

- 自动加载多本教材和书籍。
- 为每本教材构建知识图谱。
- 跨教材识别知识点重叠。
- 将多本教材内容整合压缩到不超过原始体量 30% 的精华版本。
- 通过与学科教师的多轮对话迭代优化整合方案。
- 最终提交网页端可交互界面供评委评判。

用户确认的最低可交付边界是赛题 PDF 第 3.1 节必须实现的功能。

### 产品路线

用户选择了高分展示路线，即“展示型智能体驾驶舱”。第一版优先做一个评委一看就能理解价值的可交互 dashboard，而不是只做后端脚本。

演示主路径：

```text
选择或上传 7 本医学教材
-> 解析章节和文本
-> 构建教材知识图谱
-> 跨教材去重融合
-> 压缩到 <= 30%
-> 基于证据片段进行 RAG 问答
-> 教师对话修改整合决策
-> 生成整合报告
```

默认先实现单智能体流程。多 agent 集群作为可选增强项，先在 UI 前排展示为 beta/preview，后续有时间再补实现。

### 7 本教材

第一版 UI 内置以下教材槽位，支持点击任意组合；同时保留上传新文件入口：

- 局部解剖学
- 组织学与胚胎学
- 生理学
- 医学微生物学
- 病理学
- 传染病学
- 病理生理学

现有 txt 转换文本乱码较多，先不入库；PDF 解析阶段需要做好容错。

## 3. 技术决策

- 前端：React + Vite + TypeScript
- 后端：FastAPI
- 可视化：ECharts graph / sankey
- PDF 解析：PyMuPDF
- 存储：JSON session 文件，第一版不引入数据库
- 部署：Docker 部署到魔搭创空间，服务监听 `0.0.0.0:7860`
- LLM 接入：OpenAI-compatible endpoint，通过环境变量配置
- 密钥规则：真实 API key 绝不写入 Git；仓库只保留 `.env.example`
- Agent 记忆：结构化 session JSON 是事实源；对话上下文过长时通过 `memory_summary` 做 compact
- 本地工具感知：大模型通过后端 tool registry 感知已选教材、压缩比、token 消耗、图谱摘要、整合决策等结构化状态

用户曾提供 sub2api 的 base URL 和 key 用于本地开发，但不要把真实 key 写入任何仓库文件或文档。

## 4. 重要文档

外层 workspace 已有背景和赛题总结：

- `/Users/zouweipan00/1_Program/1_12_ZJU_Hackathon/HACKATHON_BACKGROUND.md`
- `/Users/zouweipan00/1_Program/1_12_ZJU_Hackathon/HACKATHON_TASK.md`

项目仓库内已有计划文档：

- `docs/plans/2026-05-10-kibot-design.md`
- `docs/plans/2026-05-10-kibot-implementation.md`

Kimi 建议位于外层：

- `/Users/zouweipan00/1_Program/1_12_ZJU_Hackathon/from_kimi/`

已吸收的 Kimi 参考点包括：高分展示、解释性、Sankey/graph、token 统计、报告质量、单 agent 先落地、集群模式作为加分项。

## 5. 按时间线的工作记录

### 阶段 A：读题与方案收敛

1. 查看当前文件夹和 `hackathon_background.md`，了解比赛背景。
2. 阅读赛题 PDF 和现场主办方补充信息，整理为赛题文档。
3. 讨论实现路线，用户选择以高分展示为主。
4. 明确 FastAPI 负责后端 API、会话状态、文件解析、LLM 调用和工具注册；React 负责浏览器端交互界面。
5. 明确不能让前端直接持有 GPT API key，LLM 调用必须经后端代理。
6. 用户确认使用 sub2api/OpenAI-compatible key，仍保留 FastAPI 作为安全边界和业务状态层。
7. 用户选择“方案 2：展示型智能体驾驶舱”。
8. 讨论 session 管理和 agent context compact，明确结构化 session 为事实源，长对话由 summary compact。

### 阶段 B：功能边界与命名

1. 用户确认 7 本教材可点击选择任意组合，并支持上传新文件。
2. 明确大模型需要通过 tool use 感知本地规则和状态，例如选了哪些教材、压缩比、token 消耗。
3. 查看 `from_kimi/` 建议，保留可参考部分。
4. 讨论多 agent 架构：默认单 agent，可选 agent cluster 作为后续增强。
5. 用户给出部署和数据决策：
   - 部署到魔搭创空间。
   - 使用 Docker。
   - 后端先用 JSON。
   - 暂不放 txt。
   - 接受 PyMuPDF。
   - 第一版先在 UI 加集群模式，先跑通单 agent 全流程。
6. 项目名讨论后确定为 KIBot。

### 阶段 C：仓库和计划

1. 在 `project/` 下建立 KIBot Git 仓库。
2. 将 docs 规划文件放入项目仓库。
3. 建立 GitHub 仓库并同步初始内容：
   - https://github.com/ZouweiPan00/KIBot
4. 创建实现计划文档：
   - `docs/plans/2026-05-10-kibot-design.md`
   - `docs/plans/2026-05-10-kibot-implementation.md`
5. 采用 Subagent-Driven Development 模式推进开发。

### 阶段 D：实现进展

#### Task 2：FastAPI 后端骨架

提交：

- `274fdb5 feat: add FastAPI backend skeleton`
- `a8f8d49 fix: harden backend skeleton smoke checks`

主要内容：

- `app.py`
- `backend/core/config.py`
- `backend/core/paths.py`
- `requirements.txt`
- `tests/test_backend_skeleton.py`

实现 `/api/health`，返回：

```json
{"status":"ok","service":"KIBot"}
```

后续复核中做过加固：

- `openai_api_key` 默认值改为空字符串。
- `.env.example` 只保留 placeholder。
- settings 支持忽略额外 env。
- 添加基础 smoke test。

验证过：

```bash
.venv/bin/python -m unittest tests.test_backend_skeleton
```

#### Task 3：React dashboard 骨架

提交：

- `dd14377 feat: add React dashboard skeleton`
- `89d4375 fix: improve dashboard responsiveness and accessibility`

主要内容：

- `frontend/package.json`
- `frontend/src/App.tsx`
- `frontend/src/main.tsx`
- `frontend/src/styles.css`
- `frontend/index.html`

界面结构：

- 左侧：教材管理
- 中间：KIBot + 图谱展示
- 右侧：智能体面板

做过加固：

- 替换掉数学占位示例，改为医学教材列表。
- 修复 1181-1440 宽度下 dashboard 响应式布局。
- 分段控制增加 `aria-pressed`。

验证过：

```bash
npm run build
```

Vite 对 ECharts 有 large chunk warning，当前可接受。

#### Task 4：JSON Session Store

提交：

- `c7d650d feat: add JSON session store`
- `30c8631 fix: harden session storage boundaries`

主要内容：

- `backend/schemas/session.py`
- `backend/services/session_store.py`
- `backend/api/session.py`
- 对 `app.py` 注册 session router

API：

- `POST /api/session`
- `GET /api/session/{session_id}`
- `POST /api/session/{session_id}/reset`

Session state 包含：

- `selected_textbooks`
- `textbooks`
- `chapters`
- `chunks`
- `graph_nodes`
- `graph_edges`
- `integration_decisions`
- `messages`
- `memory_summary`
- `token_usage`
- `report`

做过加固：

- UUID session id 校验。
- 防路径穿越。
- store 通过依赖注入和 lazy creation 避免 import-time 文件系统副作用。
- 测试使用临时目录和 dependency override 隔离。

#### Task 5：教材上传和解析

提交：

- `42e1d57 feat: add textbook upload and parsing`
- `c41f383 fix: preserve gb18030 text fallback`
- `4411858 fix: harden textbook upload handling`

主要内容：

- `backend/schemas/textbook.py`
- `backend/services/textbook_parser.py`
- `backend/api/textbooks.py`
- `tests/test_textbook_parser.py`
- `tests/test_textbooks_api.py`

支持格式：

- PDF
- TXT
- Markdown

解析规则：

- PDF 用 PyMuPDF 按页解析。
- TXT 解码顺序为 `utf-8` -> strict `gb18030` -> `gb18030(errors="replace")`。
- 章节识别初版正则为 `^第[一二三四五六七八九十百0-9]+[章节]`。
- 无章节时 fallback 为 `全文`。

API：

- `POST /api/textbooks/upload`
- `GET /api/textbooks?session_id=...`
- `POST /api/textbooks/{textbook_id}/select?session_id=...`
- `DELETE /api/textbooks/{textbook_id}?session_id=...`

做过加固：

- GB18030 fallback 能保留有效中文。
- 同名文件用每次上传的 `textbook_id` 独立目录隔离，避免覆盖。
- 上传按 1 MiB streaming 写入，避免一次性读大文件。
- PDF 解析按页累积字符数，避免不必要的大列表。
- 解析失败返回 400，并清理失败上传文件。

#### Task 6：Textbook chunking

提交：

- `46f7587 feat: add textbook chunking`

由 subagent Bernoulli 完成并提交。用户随后手动停止 subagent，所以主会话还没有完成最终复核。

据提交说明，主要内容包括：

- `backend/services/chunker.py`
- `tests/test_chunker.py`
- 更新 `backend/schemas/textbook.py`
- 更新 `backend/api/textbooks.py`
- 更新 `tests/test_textbooks_api.py`

预期行为：

- chunk size 约 700 字符。
- overlap 约 80 字符。
- chunk metadata 包含：
  - `chunk_id`
  - `textbook_id`
  - `textbook_title`
  - `chapter`
  - `page_start`
  - `page_end`
  - `content`
  - `char_count`
- 上传教材后自动填充 `session.chunks`。
- 删除教材时同步删除关联 chunks。

subagent 声称完整测试为 32 tests OK，但由于 subagent 被停止，下一步必须由主会话重新复核：

```bash
.venv/bin/python -B -m unittest tests.test_chunker tests.test_textbooks_api tests.test_textbook_parser tests.test_session_store tests.test_session_api tests.test_backend_skeleton
.venv/bin/python -m py_compile backend/services/chunker.py backend/services/textbook_parser.py backend/api/textbooks.py
```

复核重点：

- overlap 是否严格稳定。
- 空文本、短文本、刚好 700 字、刚超过 700 字是否无空 chunk 和死循环。
- chunk id 是否唯一。
- page range/chapter metadata 是否保真。
- 删除教材是否清理对应 chunks。
- session JSON 是否不会出现意外膨胀或重复追加。

## 6. 环境和依赖状态

Python venv 曾经出现过混合版本问题：`pyvenv.cfg` 显示 3.13，但实际 symlink 指向 3.14。后续已删除并用 Python 3.13 重建。

当前已确认：

```text
.venv/bin/python --version => Python 3.13.12
node --version => v22.22.0
npm --version => 10.9.4
```

使用规则：

- 后端测试统一用 `.venv/bin/python`，不要直接用系统 `python3`。
- 依赖从 `requirements.txt` 安装到 worktree 内 `.venv`。
- 前端依赖在 `frontend/node_modules/`，不入库。
- `frontend/dist/` 不入库。
- `__pycache__` 和 `.DS_Store` 不应入库。

关于 npm：

- `npm install` 不带具体包名是正常命令，表示按 `package.json` 安装全部依赖。
- 该命令可能较久无输出，不代表一定卡死。
- 之前用户误以为卡住后手动停止过 subagent；后续需要重跑时应先检查 `frontend/package-lock.json` 和 `frontend/node_modules/` 状态。
- 当前非交互 shell 里 `proxy_on` 不一定可用；若网络失败，可按沙箱规则请求 escalated network 后重试。

## 7. 当前 Git 记录

当前分支最近提交：

```text
46f7587 feat: add textbook chunking
4411858 fix: harden textbook upload handling
c41f383 fix: preserve gb18030 text fallback
42e1d57 feat: add textbook upload and parsing
30c8631 fix: harden session storage boundaries
c7d650d feat: add JSON session store
89d4375 fix: improve dashboard responsiveness and accessibility
dd14377 feat: add React dashboard skeleton
a8f8d49 fix: harden backend skeleton smoke checks
274fdb5 feat: add FastAPI backend skeleton
79d46fd chore: ignore local worktrees
2a8ef18 chore: initialize KIBot planning repo
```

`origin/main` 当前只到初始化规划仓库，`feature/kibot-core` 的开发提交尚未合并到 main。

## 8. 下一步建议

### 立即下一步

先复核 Task 6 chunking。不要直接进入新功能，直到确认 chunking 没有数据一致性问题。

建议命令：

```bash
cd /Users/zouweipan00/1_Program/1_12_ZJU_Hackathon/project/.worktrees/kibot-core
.venv/bin/python -B -m unittest tests.test_chunker tests.test_textbooks_api tests.test_textbook_parser tests.test_session_store tests.test_session_api tests.test_backend_skeleton
.venv/bin/python -m py_compile backend/services/chunker.py backend/services/textbook_parser.py backend/api/textbooks.py
git status --short --branch
```

建议人工检查文件：

- `backend/services/chunker.py`
- `backend/api/textbooks.py`
- `backend/schemas/textbook.py`
- `tests/test_chunker.py`
- `tests/test_textbooks_api.py`

### Task 6 复核通过后

继续推进下一批 P0 功能，优先级建议：

1. 本地检索/RAG 基础能力：基于 chunks 做关键词或轻量相似度检索，先保证可引用证据。
2. 知识点抽取和图谱数据结构：先用规则/本地启发式兜底，再接 LLM。
3. 跨教材去重与整合决策：生成 merge/keep/split decisions，并计算压缩比。
4. Agent tool registry：提供 `get_selected_textbooks`、`get_compression_stats`、`get_token_usage`、`retrieve_chunks`、`get_graph_summary` 等工具。
5. 前后端联通：上传、选择、解析、chunk 统计、图谱预览和 report panel。
6. Docker/ModelScope 部署文件。

### 继续使用 subagent 时

可以继续 subagent-driven，但每个 subagent 的任务需要限定写入范围：

- 一个 subagent 只负责一个服务或一组测试。
- 避免多个 subagent 同时改 `app.py`、session schema 或同一个 API 文件。
- subagent 完成后，主会话必须做 spec review + quality review。
- 用户手动停止过 subagent，所以不要默认相信上一次未完成的 subagent 状态。

## 9. 已知注意事项

- 不要提交真实 API key、`.env`、PDF 教材、乱码 txt、`data/sessions/`、`data/uploads/`。
- PyMuPDF 在部分版本可能输出 SWIG deprecation warnings，当前可先视为噪声。
- Vite build 的 ECharts large chunk warning 当前可接受，后续可用动态 import 优化。
- 当前 backend 还是 JSON session store，适合 demo；并发写入和大规模文件不是第一版重点。
- 知识图谱节点来源优先从教材抽取；后续可保留“概念种子”混合模式。
- 集群模式先展示在 UI 中，真实多 agent 后续再实现。

## 10. 给下一轮 Codex 的最短指令

从这里继续时，先做：

```text
打开 docs/handovers/2026-05-10-12-44-kibot-context-handover.md；
进入 project/.worktrees/kibot-core；
复核 Task 6 chunking 的代码和测试；
通过后继续实现 RAG/graph/integration 的下一项 P0 功能。
```
