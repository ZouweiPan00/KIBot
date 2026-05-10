import { useMemo, useState } from "react";

import ReactECharts from "echarts-for-react";
import { GitBranch, Loader2, Network, RefreshCw, Sparkles } from "lucide-react";

import type { GraphNode, GraphResponse, IntegrationStats, SankeyPayload, Textbook } from "../types";
import { displayTextbookTitle } from "./TextbookPanel";

type ChartParams = {
  name?: string;
  data?: {
    id?: string;
    displayName?: string;
    definition?: string;
    category?: string;
    chapter?: string;
    page?: number;
    textbookTitle?: string;
    source?: string;
    target?: string;
    relationType?: string;
  };
};

interface Props {
  graph: GraphResponse;
  sankey: SankeyPayload | null;
  sankeyUnavailable: boolean;
  textbooks: Textbook[];
  selectedCount: number;
  loading: boolean;
  integrating: boolean;
  compressionStats: IntegrationStats | null;
  onBuildGraph: () => void;
  onRefreshGraph: () => void;
  onRunIntegration: () => void;
}

export function KnowledgeWorkspace({
  graph,
  sankey,
  sankeyUnavailable,
  textbooks,
  selectedCount,
  loading,
  integrating,
  compressionStats,
  onBuildGraph,
  onRefreshGraph,
  onRunIntegration,
}: Props) {
  const [graphQuery, setGraphQuery] = useState("");
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const graphOption = useMemo(() => toGraphOption(graph, graphQuery), [graph, graphQuery]);
  const selectedNode = useMemo(
    () => graph.nodes.find((node) => node.id === selectedNodeId) || null,
    [graph.nodes, selectedNodeId],
  );
  const graphEvents = useMemo(
    () => ({
      click: (params: ChartParams) => {
        const nodeId = params.data?.id;
        if (nodeId) {
          setSelectedNodeId(nodeId);
        }
      },
    }),
    [],
  );
  const sankeyOption = toSankeyOption(sankey, graph, textbooks, Boolean(compressionStats));
  const flowCount = sankeyOption.series[0].links.length;
  const flowSubtitle = flowCount
    ? sankey?.links?.length
      ? "跨教材整合流向"
      : "整合摘要预览"
    : "等待整合";

  return (
    <section className="centerPanel" aria-label="KIBot 知识集成仪表盘">
      <header className="topBar">
        <div className="brandBlock">
          <span className="sectionKicker">Knowledge Integration</span>
          <h1>KIBot</h1>
          <p>教材知识整合工作台</p>
        </div>
        <div className="topActions">
          <label className="graphSearch">
            <span>搜索节点</span>
            <input
              type="search"
              value={graphQuery}
              onChange={(event) => setGraphQuery(event.target.value)}
              placeholder="概念 / 章节"
              aria-label="搜索知识图谱节点"
            />
          </label>
          <button className="toolButton" type="button" onClick={onRefreshGraph}>
            <RefreshCw size={17} />
            刷新图谱
          </button>
          <button
            className="toolButton"
            type="button"
            onClick={onRunIntegration}
            disabled={integrating || loading || selectedCount === 0}
          >
            {integrating ? <Loader2 size={17} className="spin" /> : <GitBranch size={17} />}
            整合到30%
          </button>
          <button className="toolButton primary" type="button" onClick={onBuildGraph} disabled={loading}>
            {loading ? <Loader2 size={17} className="spin" /> : <Sparkles size={17} />}
            构建图谱
          </button>
        </div>
      </header>

      <div className="summaryStrip" aria-label="融合概览">
        <Metric label="教材" value={`${textbooks.length}/7`} detail="当前会话" />
        <Metric label="知识节点" value={String(graph.nodes.length)} detail="图谱实体" />
        <Metric label="关系" value={String(graph.edges.length)} detail="跨章节连接" />
        <Metric label="流向" value={String(flowCount)} detail="整合链路" />
        <Metric
          label="压缩"
          value={compressionStats ? `${Math.round(compressionStats.ratio * 100)}%` : "待整合"}
          detail="目标≤30%"
        />
      </div>

      <div className="visualGrid">
        <div className="visualWorkspace">
          <div className="workspaceHeader">
            <div>
              <h2>知识图谱</h2>
              <span>实体、证据与教材来源</span>
            </div>
            <Network size={20} />
          </div>
          {graph.nodes.length ? (
            <>
              <ReactECharts className="knowledgeChart" option={graphOption} onEvents={graphEvents} />
              <GraphNodeDetail node={selectedNode} />
            </>
          ) : (
            <EmptyVisual title="暂无图谱" detail="选择教材后构建图谱" />
          )}
        </div>

        <div className="visualWorkspace flowWorkspace">
          <div className="workspaceHeader">
            <div>
              <h2>Sankey 整合流</h2>
              <span>{sankeyUnavailable ? "接口待接入" : flowSubtitle}</span>
            </div>
            <GitBranch size={20} />
          </div>
          {flowCount ? (
            <ReactECharts className="sankeyChart" option={sankeyOption} />
          ) : (
            <EmptyVisual title="暂无整合流" detail="选择教材后点击整合到30%" />
          )}
        </div>
      </div>
    </section>
  );
}

function Metric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function EmptyVisual({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="emptyVisual">
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

function GraphNodeDetail({ node }: { node: GraphNode | null }) {
  if (!node) {
    return (
      <div className="graphNodeDetail empty">
        <strong>点击节点查看详情</strong>
        <span>展示名称、定义、教材来源、章节与页码。</span>
      </div>
    );
  }

  return (
    <article className="graphNodeDetail">
      <div>
        <span className="mutedLabel">Selected Concept</span>
        <strong>{node.name || node.label || node.id}</strong>
      </div>
      <p>{node.definition || "该节点来自教材章节抽取，暂无独立定义。"}</p>
      <div className="nodeMetaGrid">
        <span>{node.category || "concept"}</span>
        <span>{node.textbook_title || node.textbook_id || "来源教材待确认"}</span>
        <span>{node.chapter || "章节待确认"}</span>
        <span>{typeof node.page === "number" ? `第 ${node.page} 页` : "页码待确认"}</span>
      </div>
    </article>
  );
}

function toGraphOption(graph: GraphResponse, query: string) {
  const normalizedQuery = normalizeSearchText(query);
  const hasQuery = Boolean(normalizedQuery);
  const categories = Array.from(new Set(graph.nodes.map((node) => node.category || "concept"))).map(
    (name) => ({ name }),
  );
  const labeledNodeIds = new Set(
    [...graph.nodes]
      .sort((left, right) => (right.importance || 0) - (left.importance || 0))
      .slice(0, 32)
      .map((node) => node.id),
  );

  return {
    tooltip: {
      trigger: "item",
      formatter: (params: ChartParams) => tooltipLabel(params),
    },
    legend: {
      top: 8,
      left: 12,
      itemWidth: 10,
      itemHeight: 10,
      textStyle: { color: "#526273", fontSize: 12 },
    },
    color: ["#2f7d6d", "#3867b7", "#c17c22", "#a74855", "#64748b", "#7c5a9b"],
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        categories,
        label: {
          show: false,
          color: "#17212f",
          fontSize: 12,
          formatter: (params: ChartParams) => shortLabel(displayLabel(params)),
        },
        emphasis: {
          focus: "adjacency",
          label: {
            show: true,
            formatter: (params: ChartParams) => shortLabel(displayLabel(params), 14),
          },
        },
        force: { repulsion: 360, edgeLength: [95, 175], gravity: 0.08 },
        lineStyle: { color: "source", opacity: 0.28, width: 1.4 },
        data: graph.nodes.map((node) => {
          const displayName = node.name || node.label || node.id;
          const matchesQuery =
            !hasQuery ||
            [displayName, node.category, node.textbook_title, node.chapter]
              .filter((value): value is string => Boolean(value))
              .some((value) => normalizeSearchText(value).includes(normalizedQuery));

          return {
            name: node.id,
            id: node.id,
            displayName,
            definition: node.definition,
            categoryName: node.category,
            textbookTitle: node.textbook_title,
            chapter: node.chapter,
            page: node.page,
            value: node.frequency || 1,
            symbol: symbolForCategory(node.category),
            symbolSize: Math.max(34, Math.min(78, 30 + (node.importance || 1) * 18)),
            category: Math.max(
              0,
              categories.findIndex((category) => category.name === (node.category || "concept")),
            ),
            itemStyle: {
              opacity: matchesQuery ? 1 : 0.18,
            },
            label: {
              show: matchesQuery && (hasQuery || labeledNodeIds.has(node.id)),
            },
          };
        }),
        links: graph.edges.map((edge) => ({
          source: edge.source,
          target: edge.target,
          value: edge.confidence || 0.5,
          relationType: edge.relation_type,
        })),
      },
    ],
  };
}

function symbolForCategory(category?: string): "circle" | "rect" | "triangle" | "diamond" | "roundRect" {
  const normalized = (category || "concept").toLowerCase();
  if (normalized.includes("chapter") || normalized.includes("教材") || normalized.includes("source")) {
    return "rect";
  }
  if (normalized.includes("relation") || normalized.includes("path") || normalized.includes("edge")) {
    return "triangle";
  }
  if (normalized.includes("term") || normalized.includes("keyword") || normalized.includes("术语")) {
    return "diamond";
  }
  if (normalized.includes("case") || normalized.includes("example")) {
    return "roundRect";
  }
  return "circle";
}

function normalizeSearchText(value: string): string {
  return value.normalize("NFKC").toLowerCase().replace(/\s+/g, "");
}

function toSankeyOption(
  sankey: SankeyPayload | null,
  graph: GraphResponse,
  textbooks: Textbook[],
  integrationHasRun: boolean,
) {
  const hasServerFlow = Boolean(sankey?.links?.length);
  const payload = hasServerFlow || integrationHasRun ? sankey || fallbackSankey(graph, textbooks) : { nodes: [], links: [] };
  const fallback = prettifySankeyLabels(payload, textbooks);

  return {
    tooltip: { trigger: "item" },
    color: ["#2f7d6d", "#3867b7", "#c17c22", "#a74855", "#64748b"],
    series: [
      {
        type: "sankey",
        emphasis: { focus: "adjacency" },
        nodeGap: 12,
        nodeWidth: 14,
        draggable: true,
        label: {
          color: "#17212f",
          fontSize: 12,
          formatter: (params: ChartParams) => shortLabel(params.name || "", 12),
        },
        lineStyle: { color: "gradient", opacity: 0.34 },
        data: fallback.nodes,
        links: fallback.links,
      },
    ],
  };
}

function displayLabel(params: ChartParams): string {
  return params.data?.displayName || params.name || "";
}

function tooltipLabel(params: ChartParams): string {
  if (params.data?.source && params.data?.target) {
    const relation = params.data.relationType ? ` (${params.data.relationType})` : "";
    return `${params.data.source} -> ${params.data.target}${relation}`;
  }
  return displayLabel(params);
}

function shortLabel(value: string, maxLength = 10): string {
  const label = value.trim();
  if (label.length <= maxLength) {
    return label;
  }
  return `${label.slice(0, maxLength - 1)}...`;
}

function fallbackSankey(graph: GraphResponse, textbooks: Textbook[]): SankeyPayload {
  if (!textbooks.length || !graph.nodes.length) {
    return { nodes: [], links: [] };
  }

  const target = "整合知识图谱";
  const nodes = [...textbooks.map((book, index) => ({ name: displayTextbookTitle(book, index) })), { name: target }];
  const links = textbooks.map((book, index) => ({
    source: displayTextbookTitle(book, index),
    target,
    value: Math.max(1, graph.nodes.filter((node) => node.textbook_id === book.textbook_id).length),
  }));
  return { nodes, links };
}

function prettifySankeyLabels(sankey: SankeyPayload, textbooks: Textbook[]): SankeyPayload {
  const titlePairs = textbooks.map((book, index) => ({
    raw: book.title,
    pretty: displayTextbookTitle(book, index),
  }));

  function prettyName(name: string): string {
    for (const { raw, pretty } of titlePairs) {
      if (!raw || raw === pretty) {
        continue;
      }
      if (name === raw) {
        return pretty;
      }
      if (name.startsWith(`${raw}-`)) {
        return `${pretty}-${name.slice(raw.length + 1)}`;
      }
    }
    return name;
  }

  return {
    nodes: sankey.nodes.map((node) => ({ name: prettyName(node.name) })),
    links: sankey.links.map((link) => ({
      ...link,
      source: prettyName(link.source),
      target: prettyName(link.target),
    })),
  };
}
