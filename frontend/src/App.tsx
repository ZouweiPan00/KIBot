import ReactECharts from "echarts-for-react";
import {
  Activity,
  Bot,
  BookOpen,
  CheckCircle2,
  ClipboardList,
  Database,
  FileText,
  GitBranch,
  Layers,
  MessageSquareText,
  Network,
  PanelRight,
  Search,
  ShieldCheck,
  Sparkles,
  Stethoscope,
  UploadCloud,
} from "lucide-react";

const textbooks = [
  {
    name: "局部解剖学",
    edition: "赛方教材 01",
    units: 16,
    chunks: 642,
    focus: "结构定位",
    status: "已入库",
  },
  {
    name: "生理学",
    edition: "赛方教材 03",
    units: 15,
    chunks: 588,
    focus: "机制链路",
    status: "已索引",
  },
  {
    name: "组织学与胚胎学",
    edition: "赛方教材 02",
    units: 17,
    chunks: 731,
    focus: "组织结构",
    status: "已索引",
  },
  {
    name: "病理学",
    edition: "赛方教材 05",
    units: 13,
    chunks: 512,
    focus: "病变映射",
    status: "融合中",
  },
  {
    name: "医学微生物学",
    edition: "赛方教材 04",
    units: 12,
    chunks: 486,
    focus: "病原机制",
    status: "已入库",
  },
  {
    name: "传染病学",
    edition: "赛方教材 06",
    units: 11,
    chunks: 439,
    focus: "疾病路径",
    status: "待复核",
  },
  {
    name: "病理生理学",
    edition: "赛方教材 07",
    units: 22,
    chunks: 916,
    focus: "机制整合",
    status: "融合中",
  },
];

const summaryMetrics = [
  { label: "医学教材", value: "7", detail: "统一解析完成" },
  { label: "知识实体", value: "1,284", detail: "跨书对齐" },
  { label: "RAG 片段", value: "6,730", detail: "可追溯证据" },
  { label: "报告段落", value: "24", detail: "待教师确认" },
];

const workflow = [
  {
    title: "Graph Builder",
    label: "知识图谱",
    value: "87%",
    icon: Network,
    detail: "实体消歧与章节关系对齐",
  },
  {
    title: "RAG Evidence",
    label: "证据检索",
    value: "71%",
    icon: Database,
    detail: "召回原文、图注与表格片段",
  },
  {
    title: "Report Writer",
    label: "报告生成",
    value: "42%",
    icon: FileText,
    detail: "生成融合说明和引用清单",
  },
];

const decisions = [
  {
    topic: "炎症反应概念合并",
    source: "病理学 / 病理生理学 / 生理学",
    state: "需复核",
  },
  {
    topic: "免疫应答路径保留",
    source: "医学微生物学 / 传染病学",
    state: "已融合",
  },
  {
    topic: "组织损伤与修复证据链",
    source: "组织学与胚胎学 / 病理学",
    state: "写入报告",
  },
  {
    topic: "病原体入侵到疾病结局",
    source: "医学微生物学 / 传染病学 / 病理生理学",
    state: "待确认",
  },
];

const graphOption = {
  tooltip: {
    trigger: "item",
  },
  legend: {
    top: 8,
    left: 12,
    itemWidth: 10,
    itemHeight: 10,
    textStyle: {
      color: "#526273",
      fontSize: 12,
    },
  },
  color: ["#2f7d6d", "#3867b7", "#c17c22", "#a74855", "#64748b"],
  series: [
    {
      type: "graph",
      layout: "force",
      roam: true,
      categories: [
        { name: "核心主题" },
        { name: "基础医学" },
        { name: "疾病机制" },
        { name: "病原与免疫" },
        { name: "证据片段" },
      ],
      label: {
        show: true,
        color: "#17212f",
        fontSize: 12,
        formatter: "{b}",
      },
      force: {
        repulsion: 310,
        edgeLength: [85, 145],
      },
      lineStyle: {
        color: "source",
        opacity: 0.48,
        width: 2,
      },
      data: [
        { name: "医学课程核心", value: 56, symbolSize: 82, category: 0 },
        { name: "炎症反应", value: 48, symbolSize: 66, category: 2 },
        { name: "免疫应答", value: 42, symbolSize: 58, category: 3 },
        { name: "组织损伤", value: 36, symbolSize: 54, category: 1 },
        { name: "病原体", value: 30, symbolSize: 50, category: 3 },
        { name: "病理改变", value: 34, symbolSize: 52, category: 2 },
        { name: "功能代偿", value: 32, symbolSize: 50, category: 1 },
        { name: "原文证据", value: 26, symbolSize: 46, category: 4 },
      ],
      links: [
        { source: "医学课程核心", target: "炎症反应" },
        { source: "医学课程核心", target: "免疫应答" },
        { source: "炎症反应", target: "组织损伤" },
        { source: "病原体", target: "免疫应答" },
        { source: "病原体", target: "炎症反应" },
        { source: "组织损伤", target: "病理改变" },
        { source: "病理改变", target: "功能代偿" },
        { source: "炎症反应", target: "原文证据" },
        { source: "免疫应答", target: "原文证据" },
      ],
    },
  ],
};

export default function App() {
  return (
    <main className="appShell">
      <aside className="panel leftPanel" aria-label="教材管理">
        <div className="panelHeader">
          <div>
            <span className="sectionKicker">Medical Corpus</span>
            <h2>教材管理</h2>
          </div>
          <button className="iconButton" type="button" aria-label="上传医学教材">
            <UploadCloud size={19} />
          </button>
        </div>

        <div className="sessionCard">
          <div>
            <span className="mutedLabel">当前项目</span>
            <strong>7 本医学教材融合</strong>
          </div>
          <span className="statusPill ready">
            <CheckCircle2 size={14} />
            运行中
          </span>
        </div>

        <div className="metricGrid" aria-label="教材解析指标">
          <div>
            <span>章节单元</span>
            <strong>108</strong>
          </div>
          <div>
            <span>证据切片</span>
            <strong>4,314</strong>
          </div>
        </div>

        <div className="textbookList">
          {textbooks.map((book) => (
            <article className="textbookItem" key={book.name}>
              <div className="bookIcon" aria-hidden="true">
                <BookOpen size={18} />
              </div>
              <div className="bookBody">
                <div className="bookTitleRow">
                  <strong>{book.name}</strong>
                  <span>{book.edition}</span>
                </div>
                <div className="bookMeta">
                  {book.units} 单元 / {book.chunks} 片段 / {book.focus}
                </div>
              </div>
              <span className="tinyState">{book.status}</span>
            </article>
          ))}
        </div>
      </aside>

      <section className="centerPanel" aria-label="KIBot 医学知识集成仪表盘">
        <header className="topBar">
          <div className="brandBlock">
            <span className="sectionKicker">Knowledge Integration</span>
            <h1>KIBot</h1>
            <p>A Knowledge Integration Agent</p>
          </div>
          <div className="topActions">
            <button className="toolButton" type="button">
              <Search size={17} />
              检索证据
            </button>
            <button className="toolButton primary" type="button">
              <Sparkles size={17} />
              启动融合
            </button>
          </div>
        </header>

        <div className="summaryStrip" aria-label="融合概览">
          {summaryMetrics.map((metric) => (
            <div key={metric.label}>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <small>{metric.detail}</small>
            </div>
          ))}
        </div>

        <div className="visualWorkspace">
          <div className="workspaceHeader">
            <div>
              <h2>医学知识图谱</h2>
              <span>跨教材实体、证据与诊疗关系</span>
            </div>
            <div className="segmentedControl" aria-label="图谱模式">
              <button type="button" aria-pressed="false">
                融合前
              </button>
              <button className="active" type="button" aria-pressed="true">
                融合后
              </button>
            </div>
          </div>
          <ReactECharts className="knowledgeChart" option={graphOption} />
        </div>

        <div className="decisionTable">
          <div className="tableTitle">
            <GitBranch size={18} />
            <h2>融合决策与报告队列</h2>
          </div>
          {decisions.map((decision) => (
            <div className="decisionRow" key={decision.topic}>
              <span>{decision.topic}</span>
              <span>{decision.source}</span>
              <strong>{decision.state}</strong>
            </div>
          ))}
        </div>
      </section>

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

        <div className="agentStatus">
          <div className="pulseDot" />
          <div>
            <strong>Orchestrator Agent</strong>
            <span>正在协调图谱、RAG 与报告生成</span>
          </div>
        </div>

        <div className="agentStack">
          {workflow.map((item) => {
            const Icon = item.icon;

            return (
              <article className="agentCard" key={item.title}>
                <div className="cardTitle">
                  <Icon size={17} />
                  <span>{item.label}</span>
                </div>
                <div className="toolCall">
                  <span>{item.title}</span>
                  <strong>{item.value}</strong>
                </div>
                <div className="progressTrack" aria-label={`${item.label}进度`}>
                  <span style={{ width: item.value }} />
                </div>
                <p>{item.detail}</p>
              </article>
            );
          })}

          <article className="agentCard insightCard">
            <div className="cardTitle">
              <MessageSquareText size={17} />
              <span>教师确认建议</span>
            </div>
            <p>
              “炎症反应”节点已汇总 6 条跨书证据，建议优先确认病理学定义与病理生理学机制引用。
            </p>
          </article>
        </div>

        <div className="queueList">
          <h3>工作流</h3>
          <div className="queueItem">
            <Layers size={15} />
            <span>教材切片与元数据标准化</span>
          </div>
          <div className="queueItem">
            <Network size={15} />
            <span>图谱实体对齐与关系补全</span>
          </div>
          <div className="queueItem">
            <Activity size={15} />
            <span>RAG 证据召回与冲突检测</span>
          </div>
          <div className="queueItem">
            <ClipboardList size={15} />
            <span>融合报告生成与人工复核</span>
          </div>
        </div>

        <div className="agentFooter">
          <div>
            <span className="mutedLabel">Safety Gate</span>
            <strong>引用完整性 98.6%</strong>
          </div>
          <ShieldCheck size={20} />
          <Stethoscope size={20} />
          <PanelRight size={20} />
        </div>
      </aside>
    </main>
  );
}
