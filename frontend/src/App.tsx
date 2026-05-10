import { useCallback, useEffect, useMemo, useState } from "react";

import {
  bootstrapSession,
  buildGraph,
  getGraph,
  getIntegrationDecisions,
  getRagStatus,
  getReport,
  getSankey,
  listTextbooks,
  queryRag,
  selectTextbook,
  uploadTextbook,
} from "./api";
import { KnowledgeWorkspace } from "./components/KnowledgeWorkspace";
import { RightTabs } from "./components/RightTabs";
import { TextbookPanel } from "./components/TextbookPanel";
import type {
  GraphResponse,
  IntegrationDecision,
  KIBotSession,
  RAGResponse,
  RAGStatus,
  ReportState,
  SankeyPayload,
  Textbook,
} from "./types";

const EMPTY_GRAPH: GraphResponse = { nodes: [], edges: [] };

export default function App() {
  const [session, setSession] = useState<KIBotSession | null>(null);
  const [textbooks, setTextbooks] = useState<Textbook[]>([]);
  const [graph, setGraph] = useState<GraphResponse>(EMPTY_GRAPH);
  const [sankey, setSankey] = useState<SankeyPayload | null>(null);
  const [decisions, setDecisions] = useState<IntegrationDecision[]>([]);
  const [ragStatus, setRagStatus] = useState<RAGStatus | null>(null);
  const [ragAnswer, setRagAnswer] = useState<RAGResponse | null>(null);
  const [report, setReport] = useState<ReportState | null>(null);
  const [loading, setLoading] = useState(true);
  const [graphLoading, setGraphLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [ragLoading, setRagLoading] = useState(false);
  const [sankeyUnavailable, setSankeyUnavailable] = useState(false);
  const [decisionsUnavailable, setDecisionsUnavailable] = useState(false);
  const [reportUnavailable, setReportUnavailable] = useState(false);
  const [leftError, setLeftError] = useState<string | null>(null);
  const [rightError, setRightError] = useState<string | null>(null);

  const selectedIds = useMemo(() => {
    return new Set(
      (session?.selected_textbooks || [])
        .map((item) => (typeof item === "string" ? item : null))
        .filter((item): item is string => Boolean(item)),
    );
  }, [session?.selected_textbooks]);

  const sessionId = session?.session_id || null;

  const refreshTextbooks = useCallback(
    async (activeSessionId: string) => {
      setLeftError(null);
      const listed = await listTextbooks(activeSessionId);
      setTextbooks(listed);
    },
    [],
  );

  const refreshGraph = useCallback(
    async (activeSessionId: string) => {
      const nextGraph = await getGraph(activeSessionId);
      setGraph(nextGraph);
    },
    [],
  );

  const refreshOptionalPanels = useCallback(
    async (activeSessionId: string, activeSession: KIBotSession | null) => {
      const [decisionResult, sankeyResult, reportResult] = await Promise.all([
        getIntegrationDecisions(activeSessionId),
        getSankey(activeSessionId),
        getReport(activeSessionId),
      ]);

      setDecisions(decisionResult.data || activeSession?.integration_decisions || []);
      setDecisionsUnavailable(decisionResult.unavailable);
      setSankey(sankeyResult.data);
      setSankeyUnavailable(sankeyResult.unavailable);
      setReport(reportResult.data || activeSession?.report || null);
      setReportUnavailable(reportResult.unavailable);
    },
    [],
  );

  const refreshRagStatus = useCallback(
    async (activeSessionId: string) => {
      setRagStatus(await getRagStatus(activeSessionId));
    },
    [],
  );

  const refreshAll = useCallback(
    async (activeSessionId: string, activeSession: KIBotSession | null) => {
      await Promise.all([
        refreshTextbooks(activeSessionId),
        refreshGraph(activeSessionId),
        refreshRagStatus(activeSessionId),
        refreshOptionalPanels(activeSessionId, activeSession),
      ]);
    },
    [refreshGraph, refreshOptionalPanels, refreshRagStatus, refreshTextbooks],
  );

  useEffect(() => {
    let cancelled = false;

    async function boot() {
      setLoading(true);
      setLeftError(null);
      setRightError(null);

      try {
        const nextSession = await bootstrapSession();
        if (cancelled) {
          return;
        }
        setSession(nextSession);
        setTextbooks(nextSession.textbooks || []);
        setGraph({ nodes: nextSession.graph_nodes || [], edges: nextSession.graph_edges || [] });
        setDecisions(nextSession.integration_decisions || []);
        setReport(nextSession.report || null);
        await refreshAll(nextSession.session_id, nextSession);
      } catch (error) {
        if (!cancelled) {
          setLeftError(readableError(error, "无法初始化会话"));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void boot();
    return () => {
      cancelled = true;
    };
  }, [refreshAll]);

  async function handleUpload(file: File) {
    if (!sessionId) {
      return;
    }

    setUploading(true);
    setLeftError(null);
    try {
      await uploadTextbook(sessionId, file);
      await refreshTextbooks(sessionId);
      await refreshRagStatus(sessionId);
    } catch (error) {
      setLeftError(readableError(error, "上传失败"));
    } finally {
      setUploading(false);
    }
  }

  async function handleSelect(textbookId: string) {
    if (!sessionId) {
      return;
    }

    setLeftError(null);
    try {
      const nextSession = await selectTextbook(sessionId, textbookId);
      setSession(nextSession);
      await Promise.all([refreshRagStatus(sessionId), refreshOptionalPanels(sessionId, nextSession)]);
    } catch (error) {
      setLeftError(readableError(error, "选择教材失败"));
    }
  }

  async function handleBuildGraph() {
    if (!sessionId) {
      return;
    }

    setGraphLoading(true);
    setRightError(null);
    try {
      const nextGraph = await buildGraph(sessionId);
      setGraph(nextGraph);
      await Promise.all([refreshRagStatus(sessionId), refreshOptionalPanels(sessionId, session)]);
    } catch (error) {
      setRightError(readableError(error, "图谱构建失败"));
    } finally {
      setGraphLoading(false);
    }
  }

  async function handleRefreshGraph() {
    if (!sessionId) {
      return;
    }

    setGraphLoading(true);
    setRightError(null);
    try {
      await Promise.all([refreshGraph(sessionId), refreshOptionalPanels(sessionId, session)]);
    } catch (error) {
      setRightError(readableError(error, "刷新图谱失败"));
    } finally {
      setGraphLoading(false);
    }
  }

  async function handleAskRag(question: string) {
    if (!sessionId || !question.trim()) {
      return;
    }

    setRagLoading(true);
    setRightError(null);
    try {
      const answer = await queryRag(sessionId, question.trim());
      setRagAnswer(answer);
      await refreshRagStatus(sessionId);
    } catch (error) {
      setRightError(readableError(error, "RAG 查询失败"));
    } finally {
      setRagLoading(false);
    }
  }

  return (
    <main className="appShell">
      <TextbookPanel
        textbooks={textbooks}
        selectedIds={selectedIds}
        sessionId={sessionId}
        loading={loading}
        uploading={uploading}
        error={leftError}
        onUpload={handleUpload}
        onSelect={handleSelect}
        onRefresh={() => {
          if (sessionId) {
            void refreshTextbooks(sessionId);
          }
        }}
      />

      <KnowledgeWorkspace
        graph={graph}
        sankey={sankey}
        sankeyUnavailable={sankeyUnavailable}
        textbooks={textbooks}
        loading={graphLoading}
        onBuildGraph={handleBuildGraph}
        onRefreshGraph={handleRefreshGraph}
      />

      <RightTabs
        decisions={decisions}
        decisionsUnavailable={decisionsUnavailable}
        ragStatus={ragStatus}
        ragAnswer={ragAnswer}
        report={report}
        reportUnavailable={reportUnavailable}
        tokenUsage={session?.token_usage || { calls: 0, input_tokens: 0, output_tokens: 0, total_tokens: 0 }}
        busy={ragLoading}
        error={rightError}
        onAskRag={handleAskRag}
      />
    </main>
  );
}

function readableError(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return `${fallback}: ${error.message}`;
  }
  return fallback;
}
