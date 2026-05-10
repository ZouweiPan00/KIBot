# KIBot Design

## Product Name

KIBot

Subtitle:

```text
A Knowledge Integration Agent
```

Long subtitle for the frontend:

```text
A Knowledge Integration Agent for Multi-Textbook Compression
```

Chinese positioning:

```text
面向多教材去重、融合与 30% 精华压缩的学科知识整合智能体
```

## Goal

Build a web-based intelligent dashboard that helps teachers integrate multiple textbooks into a compact, evidence-backed knowledge core. The product should emphasize visible workflow, graph-based understanding, cross-textbook deduplication, RAG citations, teacher feedback, and report generation.

The target demo is:

```text
Upload or select 7 textbooks
-> parse chapters
-> build textbook-level knowledge graphs
-> merge overlapping knowledge points
-> compress to <= 30%
-> ask RAG questions with citations
-> modify integration decisions through teacher dialogue
-> generate an integration report
```

## Core Decisions

- Product direction: high-score showcase dashboard.
- Deployment target: ModelScope Studio with Docker.
- Frontend: React + Vite.
- Backend: FastAPI.
- Runtime port: `0.0.0.0:7860`.
- Persistence: JSON session files, not SQLite in the first version.
- PDF parser: PyMuPDF.
- LLM provider: OpenAI-compatible API through environment variables.
- Graph visualization: ECharts graph and ECharts sankey.
- Agent architecture: single orchestrator first, cluster-ready later.
- Demo data: do not commit current TXT extracts because they contain too much garbled text.
- Minimum delivery boundary: all P0 requirements from section 3.1 of the contest PDF.

## UI Shape

The app is a single-page dashboard.

Left panel: textbook management.

- Upload PDF, Markdown, and TXT.
- Show the 7 contest textbooks as selectable slots.
- Let the user add any combination of textbooks to the current session.
- Show parse status, file type, size, chapter count, and character count.

Center panel: knowledge visualization.

- Main ECharts graph for knowledge points and relationships.
- Sankey view for cross-textbook merge flow.
- Before/after integration toggle.
- Node color indicates source textbook or integration status.
- Node size indicates cross-textbook frequency or importance.
- Clicking a node shows definition, source textbook, chapter, evidence snippet, and decision status.

Right panel: agent workspace.

- Integration decisions.
- RAG Q&A.
- Teacher dialogue.
- Integration report.
- Token usage.
- Agent cluster beta panel.

## Backend Shape

FastAPI serves both API routes and the React production build.

Suggested runtime layout:

```text
project/
├── app.py
├── backend/
│   ├── api/
│   ├── core/
│   ├── services/
│   ├── tools/
│   └── schemas/
├── frontend/
├── data/
│   └── sessions/
├── docs/
├── report/
├── Dockerfile
├── requirements.txt
└── package.json
```

Session data:

```text
data/sessions/{session_id}/session.json
data/sessions/{session_id}/uploads/
data/sessions/{session_id}/reports/
```

`session.json` is the source of truth:

```json
{
  "session_id": "...",
  "selected_textbooks": [],
  "textbooks": [],
  "chapters": [],
  "chunks": [],
  "graph_nodes": [],
  "graph_edges": [],
  "integration_decisions": [],
  "messages": [],
  "memory_summary": "",
  "token_usage": {
    "calls": 0,
    "input_tokens": 0,
    "output_tokens": 0,
    "total_tokens": 0
  },
  "report": {
    "markdown": "",
    "updated_at": null
  }
}
```

## Agent Architecture

The first version uses one orchestrator agent with a tool registry.

```text
Orchestrator Agent
├── Session Memory Tool
├── Textbook Tool
├── Graph Tool
├── Integration Tool
├── RAG Tool
├── Report Tool
└── Token Tool
```

The orchestrator never relies on chat history as the only memory. It reads and writes structured session state. The model can explain and propose actions, but the backend validates and applies state changes.

Tool examples:

- `get_selected_textbooks()`
- `get_compression_stats()`
- `get_token_usage()`
- `get_graph_summary()`
- `get_integration_decisions()`
- `retrieve_chunks(query)`
- `update_decision(decision_id, action)`

Optional second-stage architecture:

```text
Supervisor Agent
├── Book Agent 01
├── Book Agent 02
├── Book Agent 03
└── ...
```

The first version only exposes this as a beta UI panel. If time allows, each book analysis can become an independent concurrent task that reuses the same analysis function.

## Context Management

The app needs explicit context compaction for teacher dialogue and agent calls.

Rules:

- Structured session JSON is the source of truth.
- Each model call receives only necessary context.
- Old dialogue turns are summarized into `memory_summary`.
- Recent turns remain in full for conversational continuity.
- Teacher modifications must be written into `integration_decisions` and graph state, not only into message history.

Prompt context should include:

```text
system instruction
current task
selected textbook summary
compression stats
related decisions or graph nodes
retrieved chunks if needed
memory_summary
recent dialogue turns
```

## LLM And Secrets

Use environment variables only:

```text
OPENAI_BASE_URL=
OPENAI_API_KEY=
OPENAI_MODEL=
```

The frontend must never see the API key. The repository should only contain `.env.example`, not `.env`.

Every model call records usage. If the API returns no usage, estimate tokens by character count and mark the result as estimated.

Every LLM-backed feature must have a fallback:

- RAG answer fallback: show top retrieved chunks and a template answer.
- Integration fallback: use local name and keyword similarity.
- Dialogue fallback: apply simple intent rules for keep, remove, merge, split, and explain.

## Textbook Parsing

Primary parser: PyMuPDF.

Parser requirements:

- Read PDF page by page.
- Extract text and page number.
- Detect chapter headings with regex patterns such as `第X章`.
- Remove obvious headers and footers when possible.
- Produce chapters and chunks with metadata.

Supported formats:

- PDF.
- Markdown.
- TXT.

Chunking:

- Target chunk size: 500-800 Chinese characters.
- Overlap: 50-100 characters.
- Metadata: textbook title, chapter title, page or page range, chunk index.

## Knowledge Graph Strategy

The goal is high-quality visual output and credible evidence.

Primary flow:

```text
chapter/chunk text
-> LLM extracts knowledge nodes and relations
-> local schema validator normalizes output
-> graph service deduplicates names within each textbook
-> integration service aligns nodes across textbooks
```

Node fields:

- id
- name
- definition
- category
- textbook_id
- textbook_title
- chapter
- page
- source_chunk_id
- frequency
- importance
- status

Edge fields:

- id
- source
- target
- relation_type
- description
- confidence
- textbook_id

Relation types:

- `prerequisite`
- `parallel`
- `contains`
- `applies_to`

Future hybrid mode:

- Reuse high-quality extracted concepts as concept seeds.
- Use seeds to stabilize future extraction.
- Still attach evidence chunks from uploaded textbooks.

## Integration And Compression

Cross-textbook integration produces decisions:

- `merge`
- `keep`
- `remove`
- `split`

Decision fields:

- decision_id
- action
- concept
- affected_nodes
- result_node
- reason
- confidence
- status
- teacher_note

Compression ratio:

```text
compression_ratio = compressed_chars / original_chars
```

The system must keep the ratio <= 30%.

For the showcase, compressed content is generated at the knowledge-point level:

```text
merged/kept node
-> concise teaching note
-> source citations
-> char count
```

The integration report and dashboard must use the same character-counting logic.

## RAG Strategy

First version: local retrieval + GPT generation.

Retrieval:

- Build chunks from parsed textbooks.
- Score chunks with keyword and BM25-style matching.
- Return top 5 chunks.
- Keep citation metadata.

Generation:

- Prompt the model to answer only from retrieved context.
- Require citations.
- If context is insufficient, say the current knowledge base has no relevant information.

Frontend output:

- Answer body.
- Citation cards.
- Textbook, chapter, page, relevance score.
- Expandable source chunk.
- Token usage and response time.

Embedding and rerank can be documented as extension points, not first-version blockers.

## Teacher Dialogue

Teacher dialogue supports:

- Explain a decision.
- Keep a removed concept.
- Remove a concept.
- Merge two concepts.
- Split one concept into two.
- Regenerate report after changes.

The model may propose an action in JSON, but the backend executes it only after validation.

Example action:

```json
{
  "intent": "update_decision",
  "target_concept": "免疫应答",
  "new_action": "keep",
  "reason": "教师认为该知识点具有独立教学价值"
}
```

## Report

The app generates and previews `report/整合报告.md`.

Required sections:

- Integration overview.
- Original textbook count and character count.
- Compressed character count and ratio.
- Merge, keep, remove, split counts.
- Graph statistics before and after integration.
- 3-5 key integration cases.
- Teaching continuity explanation.
- Known limitations and next improvements.

## Documentation Requirements

Required docs:

- `README.md`
- `docs/需求分析.md`
- `docs/系统设计.md`
- `docs/Agent架构说明.md`
- `docs/接口文档.md`
- `report/整合报告.md`

`docs/Agent架构说明.md` must explicitly describe:

- Why the first version uses a single orchestrator.
- How it can become a textbook-agent cluster.
- Tool registry and session-grounded state.
- Context compaction.
- Token observability.
- Known limitations.

## Deployment

Use ModelScope Studio Docker mode.

Important constraints from the deployment skill:

- Docker app must listen on `0.0.0.0:7860`.
- Do not use port `8080`.
- Do not hardcode secrets.
- Use environment variables for model credentials.
- Docker mode may require Alibaba Cloud account binding and real-name verification.
- Persistent data should use `/mnt/workspace` if needed.

The first version should serve the built frontend through FastAPI so ModelScope only needs one exposed service.

## Golden Demo Path

The main demo path is all 7 books:

```text
1. Open KIBot.
2. Add the 7 contest textbooks.
3. Parse all textbooks.
4. Build graphs.
5. Run integration.
6. Show compression ratio <= 30%.
7. Open graph view and sankey view.
8. Inspect one merge case.
9. Ask a RAG question and show citations.
10. Use teacher dialogue to modify one decision.
11. Show graph/report/statistics updated.
12. Preview the integration report.
```

## Minimum Delivery Boundary

The first submitted version must cover all P0 items from section 3.1 of the contest PDF:

- Multi-format textbook loading and parsing.
- Single textbook knowledge graph construction and visualization.
- Knowledge graph interaction.
- Cross-textbook graph integration.
- RAG question answering with citations.
- Agent architecture explanation document.
- Integration advice and multi-turn dialogue.
- Web UI.
- Integration report.
- Development documents.

