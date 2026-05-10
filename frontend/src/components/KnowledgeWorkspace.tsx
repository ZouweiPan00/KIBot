import ReactECharts from "echarts-for-react";
import { GitBranch, Loader2, Network, RefreshCw, Sparkles } from "lucide-react";

import type { GraphResponse, SankeyPayload, Textbook } from "../types";

interface Props {
  graph: GraphResponse;
  sankey: SankeyPayload | null;
  sankeyUnavailable: boolean;
  textbooks: Textbook[];
  loading: boolean;
  onBuildGraph: () => void;
  onRefreshGraph: () => void;
}

export function KnowledgeWorkspace({
  graph,
  sankey,
  sankeyUnavailable,
  textbooks,
  loading,
  onBuildGraph,
  onRefreshGraph,
}: Props) {
  const graphOption = toGraphOption(graph);
  const sankeyOption = toSankeyOption(sankey, graph, textbooks);

  return (
    <section className="centerPanel" aria-label="KIBot 医学知识集成仪表盘">
      <header className="topBar">
        <div className="brandBlock">
          <span className="sectionKicker">Knowledge Integration</span>
          <h1>KIBot</h1>
          <p>医学教材知识整合工作台</p>
        </div>
        <div className="topActions">
          <button className="toolButton" type="button" onClick={onRefreshGraph}>
            <RefreshCw size={17} />
            刷新图谱
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
        <Metric label="流向" value={String(sankeyOption.series[0].links.length)} detail="整合链路" />
      </div>

      <div className="visualGrid">
        <div className="visualWorkspace">
          <div className="workspaceHeader">
            <div>
              <h2>医学知识图谱</h2>
              <span>实体、证据与教材来源</span>
            </div>
            <Network size={20} />
          </div>
          {graph.nodes.length ? (
            <ReactECharts className="knowledgeChart" option={graphOption} />
          ) : (
            <EmptyVisual title="暂无图谱" detail="选择教材后构建图谱" />
          )}
        </div>

        <div className="visualWorkspace flowWorkspace">
          <div className="workspaceHeader">
            <div>
              <h2>Sankey 整合流</h2>
              <span>{sankeyUnavailable ? "接口待接入，显示本地摘要" : "跨教材整合流向"}</span>
            </div>
            <GitBranch size={20} />
          </div>
          {sankeyOption.series[0].links.length ? (
            <ReactECharts className="sankeyChart" option={sankeyOption} />
          ) : (
            <EmptyVisual title="暂无整合流" detail="上传并选择教材后生成" />
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

function toGraphOption(graph: GraphResponse) {
  const categories = Array.from(new Set(graph.nodes.map((node) => node.category || "concept"))).map(
    (name) => ({ name }),
  );

  return {
    tooltip: { trigger: "item" },
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
          show: true,
          color: "#17212f",
          fontSize: 12,
          formatter: "{b}",
        },
        force: { repulsion: 280, edgeLength: [80, 150] },
        lineStyle: { color: "source", opacity: 0.46, width: 2 },
        data: graph.nodes.map((node) => ({
          name: node.name || node.label || node.id,
          id: node.id,
          value: node.frequency || 1,
          symbolSize: Math.max(34, Math.min(78, 30 + (node.importance || 1) * 18)),
          category: Math.max(
            0,
            categories.findIndex((category) => category.name === (node.category || "concept")),
          ),
        })),
        links: graph.edges.map((edge) => ({
          source: edge.source,
          target: edge.target,
          value: edge.confidence || 0.5,
        })),
      },
    ],
  };
}

function toSankeyOption(sankey: SankeyPayload | null, graph: GraphResponse, textbooks: Textbook[]) {
  const fallback = sankey || fallbackSankey(graph, textbooks);

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
        label: { color: "#17212f", fontSize: 12 },
        lineStyle: { color: "gradient", opacity: 0.34 },
        data: fallback.nodes,
        links: fallback.links,
      },
    ],
  };
}

function fallbackSankey(graph: GraphResponse, textbooks: Textbook[]): SankeyPayload {
  if (!textbooks.length || !graph.nodes.length) {
    return { nodes: [], links: [] };
  }

  const target = "整合知识图谱";
  const nodes = [...textbooks.map((book) => ({ name: book.title })), { name: target }];
  const links = textbooks.map((book) => ({
    source: book.title,
    target,
    value: Math.max(1, graph.nodes.filter((node) => node.textbook_id === book.textbook_id).length),
  }));
  return { nodes, links };
}
