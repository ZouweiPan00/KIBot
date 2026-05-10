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
const ARCHIVED_SESSION_KEY = "kibot.archived_session_ids";
const MAX_ARCHIVED_SESSIONS = 5;

class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers:
        init?.body instanceof FormData
          ? init.headers
          : { "Content-Type": "application/json", ...init?.headers },
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : "";
    throw new ApiError(
      0,
      `无法连接后端服务，请确认 API 服务已启动并可访问。${detail ? ` 原始错误：${detail}` : ""}`,
    );
  }

  if (!response.ok) {
    const detail = await response.text();
    throw new ApiError(response.status, formatHttpError(response.status, detail, response.statusText));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

function formatHttpError(status: number, body: string, statusText: string): string {
  const detail = extractErrorDetail(body) || statusText || "请求失败";
  return `后端返回 ${status}：${detail}`;
}

function extractErrorDetail(body: string): string {
  const trimmed = body.trim();
  if (!trimmed) {
    return "";
  }

  try {
    const parsed = JSON.parse(trimmed) as unknown;
    if (typeof parsed === "string") {
      return parsed;
    }
    if (parsed && typeof parsed === "object" && "detail" in parsed) {
      return stringifyDetail((parsed as { detail: unknown }).detail);
    }
    if (parsed && typeof parsed === "object" && "message" in parsed) {
      return stringifyDetail((parsed as { message: unknown }).message);
    }
  } catch {
    return trimmed;
  }

  return trimmed;
}

function stringifyDetail(detail: unknown): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail.map(stringifyDetail).filter(Boolean).join("；");
  }
  if (detail && typeof detail === "object") {
    if ("msg" in detail && typeof (detail as { msg?: unknown }).msg === "string") {
      return (detail as { msg: string }).msg;
    }
    return JSON.stringify(detail);
  }
  return detail == null ? "" : String(detail);
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

export function readArchivedSessionIds(): SessionId[] {
  const raw = localStorage.getItem(ARCHIVED_SESSION_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item): item is SessionId => typeof item === "string" && item.length > 0);
  } catch {
    return [];
  }
}

export function storeArchivedSessionIds(sessionIds: SessionId[]): void {
  localStorage.setItem(ARCHIVED_SESSION_KEY, JSON.stringify(sessionIds.slice(-MAX_ARCHIVED_SESSIONS)));
}

export async function archiveCurrentAndCreateSession(currentSessionId: SessionId | null): Promise<KIBotSession> {
  let archived = readArchivedSessionIds();
  if (currentSessionId) {
    archived = [...archived.filter((sessionId) => sessionId !== currentSessionId), currentSessionId];
  }

  const expired = archived.length > MAX_ARCHIVED_SESSIONS ? archived.slice(0, archived.length - MAX_ARCHIVED_SESSIONS) : [];
  const retained = archived.slice(-MAX_ARCHIVED_SESSIONS);
  storeArchivedSessionIds(retained);

  await Promise.all(expired.map((sessionId) => deleteSession(sessionId).catch(() => undefined)));
  return createSession();
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

  return createSession();
}

export async function createSession(): Promise<KIBotSession> {
  const session = await request<KIBotSession>("/api/session", { method: "POST" });
  storeSessionId(session.session_id);
  return session;
}

export async function getSession(sessionId: SessionId): Promise<KIBotSession> {
  return request<KIBotSession>(`/api/session/${encodeURIComponent(sessionId)}`);
}

export async function deleteSession(sessionId: SessionId): Promise<void> {
  await request<void>(`/api/session/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
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
