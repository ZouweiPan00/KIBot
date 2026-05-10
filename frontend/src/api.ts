import type {
  GraphResponse,
  ChatResponse,
  IntegrationDecision,
  IntegrationRunResponse,
  IntegrationStats,
  KIBotSession,
  OptionalData,
  RAGResponse,
  RAGStatus,
  ReportState,
  SankeyPayload,
  SessionId,
  Textbook,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE || "";
const SESSION_KEY = "kibot.session_id";

class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers:
      init?.body instanceof FormData
        ? init.headers
        : { "Content-Type": "application/json", ...init?.headers },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(response.status, detail || response.statusText);
  }

  return (await response.json()) as T;
}

async function optionalRequest<T>(path: string, init?: RequestInit): Promise<OptionalData<T>> {
  try {
    return { data: await request<T>(path, init), unavailable: false };
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return { data: null, unavailable: true };
    }
    throw error;
  }
}

function withSession(path: string, sessionId: SessionId): string {
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}session_id=${encodeURIComponent(sessionId)}`;
}

export function readStoredSessionId(): SessionId | null {
  return localStorage.getItem(SESSION_KEY);
}

export function storeSessionId(sessionId: SessionId): void {
  localStorage.setItem(SESSION_KEY, sessionId);
}

export async function bootstrapSession(): Promise<KIBotSession> {
  const stored = readStoredSessionId();
  if (stored) {
    try {
      return await request<KIBotSession>(`/api/session/${encodeURIComponent(stored)}`);
    } catch (error) {
      if (!(error instanceof ApiError) || ![400, 404].includes(error.status)) {
        throw error;
      }
    }
  }

  const session = await request<KIBotSession>("/api/session", { method: "POST" });
  storeSessionId(session.session_id);
  return session;
}

export async function getSession(sessionId: SessionId): Promise<KIBotSession> {
  return request<KIBotSession>(`/api/session/${encodeURIComponent(sessionId)}`);
}

export async function listTextbooks(sessionId: SessionId): Promise<Textbook[]> {
  return request<Textbook[]>(withSession("/api/textbooks", sessionId));
}

export async function uploadTextbook(sessionId: SessionId, file: File): Promise<Textbook> {
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("file", file);
  return request<Textbook>("/api/textbooks/upload", {
    method: "POST",
    body: formData,
  });
}

export async function selectTextbook(
  sessionId: SessionId,
  textbookId: string,
): Promise<KIBotSession> {
  return request<KIBotSession>(withSession(`/api/textbooks/${encodeURIComponent(textbookId)}/select`, sessionId), {
    method: "POST",
  });
}

export async function buildGraph(sessionId: SessionId): Promise<GraphResponse> {
  return request<GraphResponse>("/api/graph/build", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, use_ai: true }),
  });
}

export async function getGraph(sessionId: SessionId): Promise<GraphResponse> {
  return request<GraphResponse>(withSession("/api/graph", sessionId));
}

export async function getRagStatus(sessionId: SessionId): Promise<RAGStatus> {
  return request<RAGStatus>(withSession("/api/rag/status", sessionId));
}

export async function queryRag(sessionId: SessionId, question: string): Promise<RAGResponse> {
  return request<RAGResponse>("/api/rag/query", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, question, use_llm: true }),
  });
}

export async function sendChatMessage(sessionId: SessionId, message: string): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat/message", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId, message }),
  });
}

export async function getIntegrationDecisions(
  sessionId: SessionId,
): Promise<OptionalData<IntegrationDecision[]>> {
  const response = await optionalRequest<{ decisions: IntegrationDecision[] }>(
    withSession("/api/integration/decisions", sessionId),
  );
  return {
    data: response.data?.decisions || null,
    unavailable: response.unavailable,
  };
}

export async function getSankey(sessionId: SessionId): Promise<OptionalData<SankeyPayload>> {
  return optionalRequest<SankeyPayload>(withSession("/api/integration/sankey", sessionId));
}

export async function runIntegration(sessionId: SessionId): Promise<IntegrationRunResponse> {
  return request<IntegrationRunResponse>("/api/integration/run", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function getIntegrationStats(sessionId: SessionId): Promise<OptionalData<IntegrationStats>> {
  const response = await optionalRequest<{ stats: IntegrationStats }>(
    withSession("/api/integration/stats", sessionId),
  );
  return {
    data: response.data?.stats || null,
    unavailable: response.unavailable,
  };
}

export async function getReport(sessionId: SessionId): Promise<OptionalData<ReportState>> {
  return optionalRequest<ReportState>(withSession("/api/report", sessionId));
}

export async function generateReport(sessionId: SessionId): Promise<ReportState> {
  return request<ReportState>("/api/report/generate", {
    method: "POST",
    body: JSON.stringify({ session_id: sessionId }),
  });
}
