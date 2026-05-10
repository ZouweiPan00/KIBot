export type SessionId = string;

export interface TokenUsage {
  calls: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export interface ReportState {
  markdown: string;
  updated_at?: string | null;
}

export interface KIBotSession {
  session_id: SessionId;
  selected_textbooks: unknown[];
  textbooks: Textbook[];
  chapters: unknown[];
  chunks: TextbookChunk[];
  graph_nodes: GraphNode[];
  graph_edges: GraphEdge[];
  integration_decisions: IntegrationDecision[];
  messages: unknown[];
  memory_summary: string;
  token_usage: TokenUsage;
  report: ReportState;
}

export interface Textbook {
  textbook_id: string;
  filename: string;
  title: string;
  file_type: "pdf" | "txt" | "md" | "markdown";
  total_pages: number;
  total_chars: number;
  chapters: ParsedChapter[];
  status: string;
}

export interface ParsedChapter {
  chapter_id: string;
  title: string;
  page_start: number;
  page_end: number;
  content: string;
  char_count: number;
}

export interface TextbookChunk {
  chunk_id?: string;
  textbook_id?: string;
  textbook_title?: string;
  chapter?: string;
  page_start?: number;
  page_end?: number;
  content?: string;
  char_count?: number;
}

export interface GraphNode {
  id: string;
  name?: string;
  label?: string;
  definition?: string;
  category?: string;
  textbook_id?: string;
  textbook_title?: string;
  chapter?: string;
  page?: number;
  frequency?: number;
  importance?: number;
  status?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation_type?: string;
  description?: string;
  confidence?: number;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface RAGStatus {
  session_id: string;
  ready: boolean;
  chunk_count: number;
  selected_textbook_count: number;
  searchable_chunk_count: number;
  graph_node_count: number;
  retrieval_status: string;
}

export interface RAGCitation {
  chunk_id?: string;
  textbook_id?: string;
  textbook_title?: string;
  chapter?: string;
  page_start?: number;
  page_end?: number;
}

export interface RetrievedChunk {
  rank: number;
  score: number;
  chunk: TextbookChunk;
  citation: RAGCitation;
}

export interface RAGResponse {
  answer: string;
  answer_source: "fallback" | "llm" | string;
  retrieval_status: string;
  llm_error?: string;
  citations: RAGCitation[];
  retrieved_chunks: RetrievedChunk[];
}

export interface ChatResponse {
  assistant_message: string;
  parsed_intent: Record<string, unknown>;
  state_summary: Record<string, unknown>;
}

export interface IntegrationDecision {
  decision_id?: string;
  concept_name?: string;
  topic?: string;
  title?: string;
  action?: string;
  source?: string;
  sources?: IntegrationSource[];
  status?: string;
  state?: string;
  rationale?: string;
  reason?: string;
  compact_note?: string;
  teacher_note?: string;
  confidence?: number;
}

export interface IntegrationSource {
  name?: string;
  concept_name?: string;
  textbook_id?: string;
  textbook_title?: string;
  chapter?: string;
  node_id?: string;
  id?: string;
}

export interface IntegrationStats {
  original_chars: number;
  compressed_chars: number;
  ratio: number;
}

export interface IntegrationRunResponse {
  session_id: string;
  decisions: IntegrationDecision[];
  stats: IntegrationStats;
  sankey: SankeyPayload;
}

export interface SankeyNode {
  name: string;
}

export interface SankeyLink {
  source: string;
  target: string;
  value: number;
}

export interface SankeyPayload {
  nodes: SankeyNode[];
  links: SankeyLink[];
}

export interface OptionalData<T> {
  data: T | null;
  unavailable: boolean;
}
