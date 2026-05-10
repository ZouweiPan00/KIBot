# KIBot

KIBot 是一个面向教材整合场景的 Knowledge Integration Agent。当前版本提供 FastAPI 后端与 React/Vite 前端，用于上传多本教材、解析章节、生成文本切片、构建知识图谱、识别跨教材重复知识点、压缩到 30% 以内、进行教师对话复核，并生成可预览的整合报告。

## 技术栈

- 后端：FastAPI、Pydantic v2、uvicorn、httpx
- 前端：React 19、Vite、TypeScript、ECharts、lucide-react
- 教材解析：PyMuPDF 解析 PDF，python-docx 解析 Word，支持 `.pdf`、`.txt`、`.md`、`.markdown`、`.docx`
- 存储：本地 JSON session storage，默认 `data/sessions`
- 智能体：单 orchestrator 优先，基于 session-grounded tools 构造上下文
- LLM：OpenAI-compatible Chat Completions API，通过环境变量配置

## 环境变量

复制 `.env.example` 为 `.env`，填入自己的服务配置。不要提交真实密钥。

```bash
cp .env.example .env
```

| 变量 | 用途 | 示例 |
| --- | --- | --- |
| `OPENAI_BASE_URL` | OpenAI-compatible API 地址 | `https://example.com/v1` |
| `OPENAI_API_KEY` | LLM 服务密钥 | `replace_me` |
| `OPENAI_MODEL` | Chat Completions 模型名 | `gpt-5.4-mini` |
| `SESSION_STORAGE_DIR` | 会话 JSON 与上传文件目录 | `data/sessions` |
| `APP_HOST` | 后端监听地址 | `0.0.0.0` |
| `APP_PORT` | 后端端口 | `7860` |

## 安装

后端：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

前端：

```bash
cd frontend
npm install
```

## 本地运行

启动 API：

```bash
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 7860 --reload
```

启动前端开发服务器：

```bash
cd frontend
npm run dev
```

访问路径：

- 前端开发页：`http://localhost:5173`
- 后端健康检查：`http://localhost:7860/api/health`
- OpenAPI 文档：`http://localhost:7860/docs`

## 使用路径

1. 创建 session：`POST /api/session`
2. 上传教材：`POST /api/textbooks/upload?session_id=...`
3. 选择参与整合的教材：`POST /api/textbooks/{textbook_id}/select?session_id=...`
4. 构建知识图谱：`POST /api/graph/build`
5. 查看 RAG 状态：`GET /api/rag/status?session_id=...`
6. 提问并查看引用证据：`POST /api/rag/query`
7. 运行跨教材整合压缩：`POST /api/integration/run`
8. 教师复核对话：`POST /api/chat/message`
9. 生成实例报告：`POST /api/report/generate`

## 评分标准实现索引

| 赛题维度 | KIBot 对应实现 |
| --- | --- |
| A 文档完整性 | `docs/需求分析.md`、`docs/系统设计.md`、`docs/Agent架构说明.md`、`docs/接口文档.md`、`report/整合报告.md` |
| B 多格式解析 | PDF/TXT/Markdown/DOCX；上传后显示解析状态、章节数、字符数 |
| B 知识图谱 | `POST /api/graph/build`；LLM-first + schema validation + deterministic fallback；ECharts 可视化 |
| B 跨教材整合 | `POST /api/integration/run`；merge/keep/remove/split；压缩率 ≤30%；Sankey 整合流 |
| B RAG 问答 | 700/80 chunk；BM25 + hashed vector embedding + concept/chapter boost；top-5 引用；原文 chunk 展开 |
| B 多轮对话 | `POST /api/chat/message`；教师 feedback 写回 decision、graph status、report stale note |
| C 可视化 | 颜色=来源/类别，大小=频次/重要度，形状=类别；搜索高亮；点击节点详情；Sankey |
| D Agent 架构 | single-orchestrator + tool registry + session store + LLM client，含 Mermaid 和取舍分析 |
| E 工程规范 | FastAPI/React 模块化、类型注解、版本锁定、`.env.example`、Dockerfile、docker-compose、魔搭部署 |
| F 创新 | deterministic-vs-LLM 成本路由、session-grounded tools、混合 RAG fallback、教师反馈结构化写回 |

完整的 P0/P1/P2 对照写在 `docs/需求分析.md`、`docs/系统设计.md` 和 `docs/Agent架构说明.md` 中。

## P1加分项对照

| P1 项 | 当前证据 | 评审演示入口 |
| --- | --- | --- |
| 多图谱视图 / Sankey | `frontend/src/components/KnowledgeWorkspace.tsx` 同屏渲染 ECharts force graph 与 Sankey；`backend/services/integration_engine.py` 生成 `sankey.nodes/links` | 点击“构建图谱”后看知识图谱；点击“整合到30%”后看 Sankey 整合流 |
| 图谱搜索、筛选、悬停、点击 | 图谱搜索框按概念/章节高亮；ECharts tooltip 展示节点/边；点击节点打开详情卡；force graph 支持 roam、拖拽 | 中央“知识图谱”区域，搜索框和节点详情卡 |
| 多维视觉映射 | 节点颜色映射类别/来源，大小映射 `importance/frequency`，形状映射概念类型；Sankey 宽度映射来源流量 | 中央图谱和 Sankey 图 |
| 混合检索 vector + BM25 + rerank | `backend/services/retriever.py` 组合 `BM25Okapi`、hashed vector cosine、chapter boost、concept boost；响应返回 `bm25_score/vector_score/chapter_score/concept_score` | 右侧“RAG 问答”Tab，展开原文 chunk 可查看相关度 |
| Token 消耗可视化 | `backend/schemas/session.py` 记录 `TokenUsage`；`backend/tools/stats_tool.py` 暴露 token 统计；前端“Token”Tab 展示调用/输入/输出/总量 | 右侧“Token”Tab |
| DOCX 支持 | `backend/services/textbook_parser.py` 使用 `python-docx`；`frontend/src/components/TextbookPanel.tsx` 上传 accept 包含 `.docx`；`requirements.txt` 锁定 `python-docx` | 左侧教材上传区可上传 Word `.docx` |
| Docker 一键部署 | `Dockerfile` 构建前端并启动 FastAPI；`docker-compose.yml` 暴露 7860；`docs/部署说明.md` 给出 compose 命令 | `docker compose up --build` |
| 静态整合报告 | `report/整合报告.md` 已提交静态样例；`scripts/dump_sample_report.py` 可从当前系统状态导出报告 | 右侧“整合报告”Tab 或仓库 `report/整合报告.md` |
| RAG benchmark 证据 | `tests/test_retriever.py` 覆盖 BM25、vector 分数、教材隔离、API fallback；`docs/系统设计.md` 给出 20-50 题扩展指标 | 本地运行 `python -m unittest tests.test_retriever tests.test_rag_api` |
| 交互式整合反馈 | `backend/services/dialogue.py` 支持 explain/keep/remove/merge/split 写回决策和图谱状态 | 右侧“教师对话”Tab 发送复核意见 |

## Docker 部署说明

仓库已包含 Dockerfile 与 docker-compose 配置。镜像会构建前端静态文件并由 FastAPI 在 `0.0.0.0:7860` 同时提供 API 与网页。推荐把 `SESSION_STORAGE_DIR` 挂载为持久化卷，避免 session JSON 与上传教材随容器销毁。

示例运行要点：

```bash
docker build -t kibot .
docker run --env-file .env -p 7860:7860 -v "$PWD/data:/app/data" kibot
```

也可以使用 compose：

```bash
docker compose up --build
```

上线到魔搭创空间时，暴露端口保持 `7860`，在平台密钥管理中配置 `OPENAI_BASE_URL`、`OPENAI_API_KEY`、`OPENAI_MODEL`。

## 项目文档

- `docs/需求分析.md`
- `docs/系统设计.md`
- `docs/Agent架构说明.md`
- `docs/接口文档.md`
- `docs/部署说明.md`
