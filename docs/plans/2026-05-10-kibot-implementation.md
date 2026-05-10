# KIBot Implementation Plan

> **For Claude:** REQUIRED SUBSKILL: Use superpowers:executing-plans to implement this plan task by task.

**Goal:** Build KIBot, a Docker-deployable web dashboard that integrates multiple textbooks into a <=30% knowledge core with graph visualization, RAG citations, teacher feedback, and report generation.

**Architecture:** React + Vite builds the dashboard. FastAPI serves APIs and the built frontend on `0.0.0.0:7860`. A single session-grounded orchestrator calls local tools and an OpenAI-compatible LLM endpoint through environment variables.

**Tech Stack:** Python 3.10+, FastAPI, PyMuPDF, Pydantic, React, Vite, TypeScript, ECharts, Docker, JSON session storage.

---

## Ground Rules

- Treat `project/` as the repository root for implementation.
- Do not commit PDF textbooks or real API keys.
- Put secrets in `.env`; commit only `.env.example`.
- The outer workspace root contains large local assets and should not be initialized as the Git repo.
- Keep the first version lightweight: JSON session files, no SQLite, no ChromaDB.
- Implement all P0 features before polishing P1/P2 extras.

## Phase 0: Repository And Runtime Skeleton

### Task 1: Initialize Project Repo

**Files:**
- Create: `project/.gitignore`
- Create: `project/README.md`
- Create: `project/.env.example`

**Step 1: Create project git repository**

Run:

```bash
cd /Users/zouweipan00/1_Program/1_12_ZJU_Hackathon/project
git init
```

Expected: `.git` exists under `project/`.

**Step 2: Create `.gitignore`**

Include:

```gitignore
.env
__pycache__/
*.pyc
.venv/
node_modules/
dist/
build/
data/sessions/
data/uploads/
data/textbooks/*.pdf
*.pdf
.DS_Store
```

**Step 3: Create `.env.example`**

```env
OPENAI_BASE_URL=https://example.com/v1
OPENAI_API_KEY=replace_me
OPENAI_MODEL=gpt-4o-mini
SESSION_STORAGE_DIR=data/sessions
APP_HOST=0.0.0.0
APP_PORT=7860
```

**Step 4: Commit**

Run:

```bash
git add .gitignore README.md .env.example
git commit -m "chore: initialize kibot project"
```

Expected: first project commit succeeds.

### Task 2: Create Backend Skeleton

**Files:**
- Create: `project/app.py`
- Create: `project/backend/__init__.py`
- Create: `project/backend/api/__init__.py`
- Create: `project/backend/core/config.py`
- Create: `project/backend/core/paths.py`
- Create: `project/requirements.txt`

**Step 1: Write dependencies**

`requirements.txt`:

```txt
fastapi==0.115.12
uvicorn[standard]==0.34.2
pydantic==2.11.4
pydantic-settings==2.9.1
python-multipart==0.0.20
PyMuPDF==1.25.5
httpx==0.28.1
orjson==3.10.18
```

**Step 2: Write config**

`backend/core/config.py`:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_base_url: str = "https://example.com/v1"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    session_storage_dir: str = "data/sessions"
    app_host: str = "0.0.0.0"
    app_port: int = 7860

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

**Step 3: Write FastAPI app**

`app.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="KIBot API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "KIBot"}
```

**Step 4: Smoke test**

Run:

```bash
cd /Users/zouweipan00/1_Program/1_12_ZJU_Hackathon/project
python3 -m pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 7860
```

Expected: `GET http://localhost:7860/api/health` returns `{"status":"ok","service":"KIBot"}`.

**Step 5: Commit**

```bash
git add app.py backend requirements.txt
git commit -m "feat: add FastAPI backend skeleton"
```

### Task 3: Create Frontend Skeleton

**Files:**
- Create: `project/frontend/package.json`
- Create: `project/frontend/index.html`
- Create: `project/frontend/src/App.tsx`
- Create: `project/frontend/src/main.tsx`
- Create: `project/frontend/src/styles.css`

**Step 1: Create Vite React app manually**

`frontend/package.json`:

```json
{
  "scripts": {
    "dev": "vite --host 0.0.0.0 --port 5173",
    "build": "tsc && vite build",
    "preview": "vite preview --host 0.0.0.0"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^4.4.1",
    "vite": "^6.3.5",
    "typescript": "^5.8.3",
    "react": "^19.1.0",
    "react-dom": "^19.1.0",
    "echarts": "^5.6.0",
    "echarts-for-react": "^3.0.2",
    "lucide-react": "^0.511.0"
  },
  "devDependencies": {}
}
```

**Step 2: Create first dashboard screen**

`frontend/src/App.tsx`:

```tsx
export default function App() {
  return (
    <main className="appShell">
      <aside className="leftPanel">教材管理</aside>
      <section className="graphPanel">
        <h1>KIBot</h1>
        <p>A Knowledge Integration Agent</p>
      </section>
      <aside className="rightPanel">智能体面板</aside>
    </main>
  );
}
```

**Step 3: Build**

Run:

```bash
cd /Users/zouweipan00/1_Program/1_12_ZJU_Hackathon/project/frontend
npm install
npm run build
```

Expected: `frontend/dist/` exists.

**Step 4: Commit**

```bash
cd /Users/zouweipan00/1_Program/1_12_ZJU_Hackathon/project
git add frontend
git commit -m "feat: add React dashboard skeleton"
```

## Phase 1: Session And Textbook Parsing

### Task 4: Implement JSON Session Store

**Files:**
- Create: `project/backend/schemas/session.py`
- Create: `project/backend/services/session_store.py`
- Create: `project/backend/api/session.py`
- Modify: `project/app.py`

**Step 1: Define session shape**

Create Pydantic models for:

- `TokenUsage`
- `ReportState`
- `KIBotSession`

**Step 2: Implement store**

`SessionStore` must support:

- `create_session()`
- `get_session(session_id)`
- `save_session(session)`
- `reset_session(session_id)`

Use UUIDs and `data/sessions/{session_id}/session.json`.

**Step 3: Add API**

Routes:

```text
POST /api/session
GET /api/session/{session_id}
POST /api/session/{session_id}/reset
```

**Step 4: Test manually**

Run:

```bash
curl -X POST http://localhost:7860/api/session
```

Expected: returns a `session_id` and creates `data/sessions/.../session.json`.

**Step 5: Commit**

```bash
git add backend app.py
git commit -m "feat: add JSON session store"
```

### Task 5: Implement Textbook Upload And Parsing

**Files:**
- Create: `project/backend/schemas/textbook.py`
- Create: `project/backend/services/textbook_parser.py`
- Create: `project/backend/api/textbooks.py`
- Modify: `project/app.py`

**Step 1: Implement parsers**

Support:

- PDF with PyMuPDF.
- TXT with UTF-8 fallback.
- Markdown as text.

Output:

```json
{
  "textbook_id": "...",
  "filename": "...",
  "title": "...",
  "file_type": "pdf",
  "total_pages": 0,
  "total_chars": 0,
  "chapters": []
}
```

**Step 2: Chapter detection**

Detect Chinese chapter headings with patterns:

```python
r"^第[一二三四五六七八九十百0-9]+章"
r"^第[一二三四五六七八九十百0-9]+节"
```

Fallback: one chapter named `全文`.

**Step 3: Add upload API**

Route:

```text
POST /api/textbooks/upload
```

Request:

- multipart file
- `session_id`

Response:

- textbook metadata
- parse status

**Step 4: Add selected textbook API**

Routes:

```text
GET /api/textbooks?session_id=...
POST /api/textbooks/{textbook_id}/select?session_id=...
DELETE /api/textbooks/{textbook_id}?session_id=...
```

**Step 5: Commit**

```bash
git add backend app.py
git commit -m "feat: add textbook upload and parsing"
```

### Task 6: Implement Chunking

**Files:**
- Create: `project/backend/services/chunker.py`
- Modify: `project/backend/services/textbook_parser.py`

**Step 1: Add chunker**

Implement character chunking:

- size: 700 chars
- overlap: 80 chars

Each chunk has:

- chunk_id
- textbook_id
- textbook_title
- chapter
- page_start
- page_end
- content
- char_count

**Step 2: Attach chunks to session**

After parsing, save chunks into `session["chunks"]`.

**Step 3: Commit**

```bash
git add backend
git commit -m "feat: add textbook chunking"
```

## Phase 2: Agent Tools And LLM Client

### Task 7: Add OpenAI-Compatible Client

**Files:**
- Create: `project/backend/services/llm_client.py`
- Modify: `project/backend/core/config.py`

**Step 1: Implement chat completion**

Use `httpx` to call:

```text
POST {OPENAI_BASE_URL}/chat/completions
```

Do not log API keys.

**Step 2: Track token usage**

If response contains `usage`, use it. Otherwise estimate:

```python
estimated_tokens = int(len(text) * 0.6)
```

**Step 3: Commit**

```bash
git add backend
git commit -m "feat: add LLM client with token tracking"
```

### Task 8: Implement Tool Registry

**Files:**
- Create: `project/backend/tools/textbook_tool.py`
- Create: `project/backend/tools/stats_tool.py`
- Create: `project/backend/tools/decision_tool.py`
- Create: `project/backend/tools/report_tool.py`
- Create: `project/backend/agent/orchestrator.py`

**Step 1: Implement read tools**

Tools:

- `get_selected_textbooks(session)`
- `get_compression_stats(session)`
- `get_token_usage(session)`
- `get_graph_summary(session)`
- `get_integration_decisions(session)`

**Step 2: Implement mutation tool**

`update_decision(session, decision_id, action, teacher_note)`.

**Step 3: Implement orchestrator**

The orchestrator builds context from tools and calls the LLM only when useful.

**Step 4: Commit**

```bash
git add backend
git commit -m "feat: add session-grounded agent tools"
```

## Phase 3: Graph, Integration, Compression

### Task 9: Generate Knowledge Graph

**Files:**
- Create: `project/backend/schemas/graph.py`
- Create: `project/backend/services/graph_builder.py`
- Create: `project/backend/api/graph.py`
- Modify: `project/app.py`

**Step 1: Create graph schema**

Nodes:

- id
- name
- definition
- category
- textbook_id
- textbook_title
- chapter
- page
- frequency
- importance
- status

Edges:

- id
- source
- target
- relation_type
- description
- confidence

**Step 2: Build graph from chunks**

First version:

- Ask LLM to extract JSON nodes and edges from selected chunks.
- Validate JSON.
- Fallback to keyword concept extraction.

Limit:

- max 30 nodes per textbook for first version.
- max 150 total visible nodes.

**Step 3: Add API**

Routes:

```text
POST /api/graph/build
GET /api/graph?session_id=...
```

**Step 4: Commit**

```bash
git add backend app.py
git commit -m "feat: build knowledge graph"
```

### Task 10: Implement Cross-Textbook Integration

**Files:**
- Create: `project/backend/schemas/integration.py`
- Create: `project/backend/services/integration_engine.py`
- Create: `project/backend/api/integration.py`
- Modify: `project/app.py`

**Step 1: Implement similarity**

Use lightweight scoring:

- exact normalized name match
- containment match
- keyword overlap
- optional LLM explanation for high-value pairs

**Step 2: Produce decisions**

Create decisions:

- `merge`
- `keep`
- `remove`
- `split`

Each decision has reason and confidence.

**Step 3: Control compression**

Compute:

```text
original_chars = sum(textbook.total_chars)
compressed_chars = sum(compact note char counts)
ratio = compressed_chars / original_chars
```

Ensure displayed ratio <= 0.30 by adjusting generated compact-note budget.

**Step 4: Add API**

Routes:

```text
POST /api/integration/run
GET /api/integration/decisions?session_id=...
POST /api/integration/decisions/{decision_id}
GET /api/integration/stats?session_id=...
```

**Step 5: Commit**

```bash
git add backend app.py
git commit -m "feat: add cross-textbook integration"
```

### Task 11: Generate Sankey Data

**Files:**
- Modify: `project/backend/services/integration_engine.py`
- Modify: `project/backend/api/integration.py`

**Step 1: Convert decisions to sankey**

Return:

```json
{
  "nodes": [{"name": "病理学-炎症"}, {"name": "整合-炎症"}],
  "links": [{"source": "病理学-炎症", "target": "整合-炎症", "value": 1}]
}
```

**Step 2: Commit**

```bash
git add backend
git commit -m "feat: expose integration sankey data"
```

## Phase 4: RAG And Teacher Dialogue

### Task 12: Implement Local RAG Retrieval

**Files:**
- Create: `project/backend/services/retriever.py`
- Create: `project/backend/api/rag.py`
- Modify: `project/app.py`

**Step 1: Implement keyword scoring**

Score chunks by:

- query term overlap
- concept name match
- chapter title match

Return top 5.

**Step 2: Generate answer**

Call LLM with retrieved chunks and strict citation rules.

Fallback: template answer with top chunks.

**Step 3: Add API**

Routes:

```text
GET /api/rag/status?session_id=...
POST /api/rag/query
```

**Step 4: Commit**

```bash
git add backend app.py
git commit -m "feat: add RAG query with citations"
```

### Task 13: Implement Teacher Dialogue

**Files:**
- Create: `project/backend/api/chat.py`
- Create: `project/backend/services/dialogue.py`
- Modify: `project/app.py`

**Step 1: Add intent parser**

Support:

- explain decision
- keep concept
- remove concept
- merge concepts
- split concept

Use LLM JSON intent when available and regex fallback.

**Step 2: Apply state changes**

Teacher modifications update:

- integration decision
- graph node status
- compression stats
- report markdown

**Step 3: Context compact**

When messages exceed 10 turns, summarize older turns into `memory_summary`.

**Step 4: Commit**

```bash
git add backend app.py
git commit -m "feat: add teacher dialogue state updates"
```

## Phase 5: Report And Docs

### Task 14: Generate Integration Report

**Files:**
- Create: `project/backend/services/report_generator.py`
- Create: `project/backend/api/report.py`
- Create: `project/report/整合报告.md`
- Modify: `project/app.py`

**Step 1: Generate Markdown**

Sections:

- 整合概览
- 整合决策摘要
- 知识图谱统计
- 重点整合案例
- 教学完整性说明
- 局限与改进

**Step 2: Add API**

Routes:

```text
POST /api/report/generate
GET /api/report?session_id=...
```

**Step 3: Commit**

```bash
git add backend report app.py
git commit -m "feat: generate integration report"
```

### Task 15: Write Required Docs

**Files:**
- Create: `project/docs/需求分析.md`
- Create: `project/docs/系统设计.md`
- Create: `project/docs/Agent架构说明.md`
- Create: `project/docs/接口文档.md`
- Modify: `project/README.md`

**Step 1: README**

Include:

- project intro
- tech stack
- environment variables
- install commands
- local run commands
- Docker deployment
- usage path

**Step 2: Agent docs**

Explain:

- single-orchestrator first
- cluster-ready design
- tool registry
- session state
- context compaction
- token observability

**Step 3: Commit**

```bash
git add README.md docs
git commit -m "docs: add required project documentation"
```

## Phase 6: Frontend Dashboard

### Task 16: Build Dashboard Layout

**Files:**
- Modify: `project/frontend/src/App.tsx`
- Modify: `project/frontend/src/styles.css`
- Create: `project/frontend/src/api.ts`
- Create: `project/frontend/src/types.ts`

**Step 1: Create three-panel layout**

Left: textbook manager.

Center: graph workspace.

Right: agent tabs.

**Step 2: Add session bootstrap**

On load:

- read `session_id` from localStorage
- if missing, call `POST /api/session`
- store session id

**Step 3: Commit**

```bash
git add frontend
git commit -m "feat: build dashboard layout"
```

### Task 17: Implement Textbook UI

**Files:**
- Create: `project/frontend/src/components/TextbookPanel.tsx`
- Modify: `project/frontend/src/App.tsx`

**Step 1: Upload UI**

Support file input and drag/drop.

**Step 2: Contest textbook slots**

Show 7 slots:

- 局部解剖学
- 组织学与胚胎学
- 生理学
- 医学微生物学
- 病理学
- 传染病学
- 病理生理学

Because no TXT/PDF is committed, slots should say "上传对应 PDF 后启用" or allow attaching files to slots.

**Step 3: Commit**

```bash
git add frontend
git commit -m "feat: add textbook management panel"
```

### Task 18: Implement Graph And Sankey UI

**Files:**
- Create: `project/frontend/src/components/GraphView.tsx`
- Create: `project/frontend/src/components/SankeyView.tsx`
- Modify: `project/frontend/src/App.tsx`

**Step 1: ECharts graph**

Show:

- nodes
- edges
- zoom
- pan
- click details
- search highlight

**Step 2: ECharts sankey**

Show integration flow from source textbook nodes to merged nodes.

**Step 3: Commit**

```bash
git add frontend
git commit -m "feat: add graph and sankey visualizations"
```

### Task 19: Implement Right Agent Panel

**Files:**
- Create: `project/frontend/src/components/AgentPanel.tsx`
- Create: `project/frontend/src/components/DecisionPanel.tsx`
- Create: `project/frontend/src/components/RagPanel.tsx`
- Create: `project/frontend/src/components/TeacherChat.tsx`
- Create: `project/frontend/src/components/ReportPanel.tsx`
- Create: `project/frontend/src/components/TokenPanel.tsx`
- Create: `project/frontend/src/components/ClusterPanel.tsx`

**Step 1: Add tabs**

Tabs:

- 整合决策
- RAG 问答
- 教师对话
- 整合报告
- Token
- Agent 集群 Beta

**Step 2: Wire API calls**

Connect to backend endpoints.

**Step 3: Commit**

```bash
git add frontend
git commit -m "feat: add agent workspace panels"
```

## Phase 7: Docker And ModelScope

### Task 20: Serve Frontend Through FastAPI

**Files:**
- Modify: `project/app.py`

**Step 1: Mount static frontend**

If `frontend/dist` exists, serve it with `StaticFiles`.

Fallback route returns `index.html`.

**Step 2: Test**

Run:

```bash
cd project/frontend
npm run build
cd ..
uvicorn app:app --host 0.0.0.0 --port 7860
```

Expected: opening `http://localhost:7860` shows React dashboard.

**Step 3: Commit**

```bash
git add app.py frontend/dist
git commit -m "feat: serve frontend from FastAPI"
```

### Task 21: Add Dockerfile

**Files:**
- Create: `project/Dockerfile`
- Create: `project/docker-compose.yml`
- Create: `project/scripts/start.sh`

**Step 1: Dockerfile**

Use Node build stage and Python runtime stage. Expose 7860.

**Step 2: Build locally**

Run:

```bash
cd project
docker build -t kibot .
docker run --rm -p 7860:7860 --env-file .env kibot
```

Expected: app opens at `http://localhost:7860`.

**Step 3: Commit**

```bash
git add Dockerfile docker-compose.yml scripts
git commit -m "chore: add Docker deployment"
```

### Task 22: Prepare ModelScope Deployment

**Files:**
- Modify: `project/README.md`

**Step 1: Confirm constraints**

- Docker mode.
- Listen on `0.0.0.0:7860`.
- Configure secrets in ModelScope Studio, not in code.

**Step 2: Push to GitHub**

Run:

```bash
cd project
git remote add origin <github-public-repo-url>
git push -u origin master
```

**Step 3: Deploy to ModelScope Studio**

Follow `部署SKILL.md`:

- create Docker Studio
- set environment variables
- push code
- trigger deploy
- check logs

**Step 4: Commit README deployment notes**

```bash
git add README.md
git commit -m "docs: add ModelScope deployment notes"
```

## Phase 8: Verification

### Task 23: P0 Acceptance Test

**Files:**
- Create: `project/docs/验收清单.md`

**Step 1: Run through P0**

Checklist:

- Upload PDF.
- Upload TXT.
- Upload Markdown.
- Parse chapters.
- Build graph.
- Click graph node.
- Run integration.
- Verify compression ratio <= 30%.
- Ask RAG question.
- Expand citation.
- Modify decision through teacher dialogue.
- Regenerate report.
- Open required docs.
- Run app through Docker.

**Step 2: Record results**

Write pass/fail and notes in `docs/验收清单.md`.

**Step 3: Commit**

```bash
git add docs/验收清单.md
git commit -m "test: record P0 acceptance results"
```

## Recommended Build Order Under Time Pressure

If time is tight, use this order:

1. Backend skeleton and session.
2. Upload and parse.
3. Frontend layout.
4. Graph with fallback nodes.
5. Integration decisions and compression stats.
6. RAG with citations.
7. Teacher dialogue update.
8. Report generation.
9. Required docs.
10. Docker deployment.

## Cut Lines

If the schedule slips:

- Keep ECharts graph, cut sankey first.
- Keep keyword RAG, cut embedding.
- Keep single Agent, leave cluster as UI and docs only.
- Keep Markdown report, cut PDF export.
- Keep local JSON, do not add database.

## Final Demo Script

Use this script:

```text
1. Open KIBot.
2. Create or restore session.
3. Upload the 7 contest PDFs.
4. Parse and show textbook stats.
5. Build graph and show node details.
6. Run integration and show <=30% compression.
7. Switch to sankey view and show merge flow.
8. Ask: “炎症和免疫应答在这些教材中如何关联？”
9. Show answer citations.
10. Tell teacher dialogue: “免疫应答不要删除，请保留。”
11. Show decision, graph, compression stats, and report updated.
12. Open report preview.
```
