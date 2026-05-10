import {
  Bot,
  ClipboardList,
  Database,
  FileText,
  MessageSquareText,
  Network,
  Send,
  ShieldCheck,
} from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";

import type {
  IntegrationDecision,
  RAGResponse,
  RAGStatus,
  ReportState,
  TokenUsage,
} from "../types";

type TabId = "decisions" | "rag" | "teacher" | "report" | "token" | "cluster";

const tabs: { id: TabId; label: string }[] = [
  { id: "decisions", label: "整合决策" },
  { id: "rag", label: "RAG 问答" },
  { id: "teacher", label: "教师对话" },
  { id: "report", label: "整合报告" },
  { id: "token", label: "Token" },
  { id: "cluster", label: "Agent 集群 Beta" },
];

interface Props {
  decisions: IntegrationDecision[];
  decisionsUnavailable: boolean;
  ragStatus: RAGStatus | null;
  ragAnswer: RAGResponse | null;
  report: ReportState | null;
  reportUnavailable: boolean;
  tokenUsage: TokenUsage;
  busy: boolean;
  error: string | null;
  onAskRag: (question: string) => void;
}

export function RightTabs({
  decisions,
  decisionsUnavailable,
  ragStatus,
  ragAnswer,
  report,
  reportUnavailable,
  tokenUsage,
  busy,
  error,
  onAskRag,
}: Props) {
  const [activeTab, setActiveTab] = useState<TabId>("decisions");
  const [question, setQuestion] = useState("炎症反应的核心机制是什么？");

  return (
    <aside className="panel rightPanel" aria-label="智能体面板">
      <div className="panelHeader">
        <div>
          <span className="sectionKicker">Agent Workspace</span>
          <h2>智能体面板</h2>
        </div>
        <div className="agentBadge" aria-hidden="true">
          <Bot size={20} />
        </div>
      </div>

      <div className="tabBar" role="tablist" aria-label="智能体功能">
        {tabs.map((tab) => (
          <button
            className={activeTab === tab.id ? "active" : ""}
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {error ? <div className="inlineError">{error}</div> : null}

      <div className="tabPanel" role="tabpanel" aria-busy={busy}>
        {activeTab === "decisions" ? (
          <DecisionPanel decisions={decisions} unavailable={decisionsUnavailable} />
        ) : null}

        {activeTab === "rag" ? (
          <RagPanel
            status={ragStatus}
            answer={ragAnswer}
            question={question}
            busy={busy}
            onQuestionChange={setQuestion}
            onAsk={() => onAskRag(question)}
          />
        ) : null}

        {activeTab === "teacher" ? <TeacherPanel /> : null}

        {activeTab === "report" ? (
          <ReportPanel report={report} unavailable={reportUnavailable} />
        ) : null}

        {activeTab === "token" ? <TokenPanel tokenUsage={tokenUsage} /> : null}

        {activeTab === "cluster" ? <ClusterPanel /> : null}
      </div>
    </aside>
  );
}

function DecisionPanel({
  decisions,
  unavailable,
}: {
  decisions: IntegrationDecision[];
  unavailable: boolean;
}) {
  if (!decisions.length) {
    return (
      <EmptyPanel
        icon={<ClipboardList size={19} />}
        title={unavailable ? "决策接口待接入" : "暂无整合决策"}
        detail="完成图谱整合后在此复核。"
      />
    );
  }

  return (
    <div className="decisionStack">
      {decisions.map((decision, index) => (
        <article className="agentCard" key={decision.decision_id || `${decision.topic}-${index}`}>
          <div className="cardTitle">
            <ClipboardList size={17} />
            <span>{decision.concept_name || decision.topic || decision.title || decision.action || "整合决策"}</span>
          </div>
          <p>{decision.rationale || decision.reason || decision.compact_note || sourceText(decision) || "等待教师复核。"}</p>
          <div className="decisionMeta">
            <strong>{decision.status || decision.state || decision.action || "待确认"}</strong>
            {typeof decision.confidence === "number" ? <span>{Math.round(decision.confidence * 100)}%</span> : null}
          </div>
        </article>
      ))}
    </div>
  );
}

function RagPanel({
  status,
  answer,
  question,
  busy,
  onQuestionChange,
  onAsk,
}: {
  status: RAGStatus | null;
  answer: RAGResponse | null;
  question: string;
  busy: boolean;
  onQuestionChange: (value: string) => void;
  onAsk: () => void;
}) {
  return (
    <div className="ragPanel">
      <div className="agentStatus compact">
        <div className={status?.ready ? "pulseDot" : "pulseDot muted"} />
        <div>
          <strong>{status?.ready ? "RAG 可检索" : "等待教材选择"}</strong>
          <span>{status ? `${status.searchable_chunk_count} 个可检索片段` : "状态加载中"}</span>
        </div>
      </div>

      <div className="questionBox">
        <textarea value={question} onChange={(event) => onQuestionChange(event.target.value)} />
        <button className="toolButton primary" type="button" disabled={busy || !question.trim()} onClick={onAsk}>
          <Send size={16} />
          提问
        </button>
      </div>

      {answer ? (
        <article className="answerBox">
          <strong>{answer.answer_source === "llm" ? "LLM 答复" : "检索答复"}</strong>
          <p>{answer.answer}</p>
          <div className="citationList">
            {answer.citations.map((citation, index) => (
              <span key={`${citation.chunk_id || index}`}>
                [{index + 1}] {citation.textbook_title || "教材"} {citation.chapter || ""}
              </span>
            ))}
          </div>
        </article>
      ) : null}
    </div>
  );
}

function TeacherPanel() {
  return (
    <div className="teacherPanel">
      <EmptyPanel
        icon={<MessageSquareText size={19} />}
        title="教师对话"
        detail="聊天接口合并后将承接修改意见、复核记录与报告再生成。"
      />
      <div className="messagePreview">
        <span>教师</span>
        <p>请优先保留跨教材共识，再标注定义差异。</p>
      </div>
      <div className="messagePreview assistant">
        <span>KIBot</span>
        <p>已准备记录复核意见。</p>
      </div>
    </div>
  );
}

function ReportPanel({
  report,
  unavailable,
}: {
  report: ReportState | null;
  unavailable: boolean;
}) {
  if (!report?.markdown) {
    return (
      <EmptyPanel
        icon={<FileText size={19} />}
        title={unavailable ? "报告接口待接入" : "暂无报告"}
        detail="报告生成后在此预览 Markdown。"
      />
    );
  }

  return (
    <article className="reportBox">
      <div className="cardTitle">
        <FileText size={17} />
        <span>整合报告</span>
      </div>
      <pre>{report.markdown}</pre>
      <small>{report.updated_at ? `更新于 ${report.updated_at}` : "未标记更新时间"}</small>
    </article>
  );
}

function TokenPanel({ tokenUsage }: { tokenUsage: TokenUsage }) {
  return (
    <div className="tokenGrid">
      <TokenMetric label="调用" value={tokenUsage.calls} />
      <TokenMetric label="输入" value={tokenUsage.input_tokens} />
      <TokenMetric label="输出" value={tokenUsage.output_tokens} />
      <TokenMetric label="总量" value={tokenUsage.total_tokens} />
    </div>
  );
}

function ClusterPanel() {
  return (
    <div className="agentStack">
      <AgentStep icon={<Network size={17} />} title="Graph Builder" detail="实体抽取、关系补全、图谱构建" />
      <AgentStep icon={<Database size={17} />} title="RAG Evidence" detail="证据召回、引用整理、冲突提示" />
      <AgentStep icon={<FileText size={17} />} title="Report Writer" detail="报告草拟、版本摘要、复核清单" />
      <div className="agentFooter">
        <div>
          <span className="mutedLabel">Safety Gate</span>
          <strong>引用完整性</strong>
        </div>
        <ShieldCheck size={20} />
      </div>
    </div>
  );
}

function AgentStep({ icon, title, detail }: { icon: ReactNode; title: string; detail: string }) {
  return (
    <article className="agentCard">
      <div className="cardTitle">
        {icon}
        <span>{title}</span>
      </div>
      <p>{detail}</p>
    </article>
  );
}

function TokenMetric({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{new Intl.NumberFormat("zh-CN").format(value || 0)}</strong>
    </div>
  );
}

function EmptyPanel({
  icon,
  title,
  detail,
}: {
  icon: ReactNode;
  title: string;
  detail: string;
}) {
  return (
    <div className="emptyPanel">
      {icon}
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

function sourceText(decision: IntegrationDecision): string {
  if (decision.source) {
    return decision.source;
  }
  if (decision.sources?.length) {
    return decision.sources
      .map((source) => source.textbook_title || source.name || source.concept_name || source.id || source.node_id)
      .filter(Boolean)
      .join(" / ");
  }
  return "";
}
