# KIBot

KIBot 是一个面向教材整合场景的 Knowledge Integration Agent。当前版本提供 FastAPI 后端与 React/Vite 前端，用于上传多本教材、解析章节、生成文本切片、构建知识图谱、基于会话内教材证据进行 RAG 问答，并为后续跨教材融合与报告生成保留结构化会话状态。

## 技术栈

- 后端：FastAPI、Pydantic v2、uvicorn、httpx
- 前端：React 19、Vite、TypeScript、ECharts、lucide-react
- 教材解析：PyMuPDF 解析 PDF，支持 `.pdf`、`.txt`、`.md`、`.markdown`
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
| `OPENAI_MODEL` | Chat Completions 模型名 | `gpt-4o-mini` |
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
7. 跨教材融合与报告生成由并行任务实现中，预期接口见 `docs/接口文档.md`

## Docker 部署说明

当前 docs 分支不修改 Docker 文件；若主分支或部署环境已有 Dockerfile/compose，可按同样环境变量注入运行。推荐容器内监听 `0.0.0.0:7860`，并把 `SESSION_STORAGE_DIR` 挂载为持久化卷，避免 session JSON 与上传教材随容器销毁。

示例运行要点：

```bash
docker build -t kibot .
docker run --env-file .env -p 7860:7860 -v "$PWD/data:/app/data" kibot
```

前端可在开发模式使用 Vite，也可由部署流水线先执行 `npm run build` 后交给后端或静态服务托管，具体以最终 Docker 文件为准。

## 项目文档

- `docs/需求分析.md`
- `docs/系统设计.md`
- `docs/Agent架构说明.md`
- `docs/接口文档.md`
- `docs/部署说明.md`

