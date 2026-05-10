import {
  BookOpen,
  CheckCircle2,
  Circle,
  FileUp,
  Loader2,
  RefreshCw,
} from "lucide-react";

import type { Textbook } from "../types";

const MEDICAL_TEXTBOOKS = [
  "局部解剖学",
  "组织学与胚胎学",
  "生理学",
  "医学微生物学",
  "病理学",
  "传染病学",
  "病理生理学",
];

interface Props {
  textbooks: Textbook[];
  selectedIds: Set<string>;
  sessionId: string | null;
  loading: boolean;
  uploading: boolean;
  selectingAll: boolean;
  error: string | null;
  onUpload: (file: File) => void;
  onSelect: (textbookId: string) => void;
  onSelectAll: () => void;
  onRefresh: () => void;
}

export function TextbookPanel({
  textbooks,
  selectedIds,
  sessionId,
  loading,
  uploading,
  selectingAll,
  error,
  onUpload,
  onSelect,
  onSelectAll,
  onRefresh,
}: Props) {
  const totalChars = textbooks.reduce((sum, book) => sum + (book.total_chars || 0), 0);
  const totalChapters = textbooks.reduce((sum, book) => sum + (book.chapters?.length || 0), 0);

  return (
    <aside className="panel leftPanel" aria-label="教材管理">
      <div className="panelHeader">
        <div>
          <span className="sectionKicker">Medical Corpus</span>
          <h2>教材管理</h2>
        </div>
        <button className="iconButton" type="button" onClick={onRefresh} aria-label="刷新教材列表">
          <RefreshCw size={18} />
        </button>
      </div>

      <div className="sessionCard">
        <div>
          <span className="mutedLabel">Session</span>
          <strong>{sessionId ? shortSession(sessionId) : "初始化中"}</strong>
        </div>
        <span className="statusPill ready">
          <CheckCircle2 size={14} />
          已连接
        </span>
      </div>

      <label className="uploadDrop">
        <FileUp size={20} />
        <span>{uploading ? "上传解析中" : "上传教材"}</span>
        <input
          type="file"
          accept=".pdf,.txt,.md,.markdown"
          disabled={!sessionId || uploading}
          onChange={(event) => {
            const file = event.currentTarget.files?.[0];
            event.currentTarget.value = "";
            if (file) {
              onUpload(file);
            }
          }}
        />
      </label>

      <div className="metricGrid" aria-label="教材解析指标">
        <div>
          <span>已上传</span>
          <strong>{textbooks.length}/7</strong>
        </div>
        <div>
          <span>已选择</span>
          <strong>{selectedIds.size}</strong>
        </div>
        <div>
          <span>章节</span>
          <strong>{totalChapters}</strong>
        </div>
        <div>
          <span>字符</span>
          <strong>{compactNumber(totalChars)}</strong>
        </div>
      </div>

      <button
        className="wideAction"
        type="button"
        disabled={selectingAll || !textbooks.length || selectedIds.size === textbooks.length}
        onClick={onSelectAll}
      >
        {selectingAll ? <Loader2 size={16} className="spin" /> : <CheckCircle2 size={16} />}
        {selectingAll ? "选择中" : "选择全部已上传教材"}
      </button>

      {error ? <div className="inlineError">{error}</div> : null}

      <div className="textbookList" aria-busy={loading}>
        {MEDICAL_TEXTBOOKS.map((slotName, index) => {
          const book = findSlotBook(textbooks, slotName, index);
          const selected = book ? selectedIds.has(book.textbook_id) : false;

          return (
            <article className={`textbookItem ${selected ? "selected" : ""}`} key={slotName}>
              <div className="bookIcon" aria-hidden="true">
                {selected ? <CheckCircle2 size={18} /> : <BookOpen size={18} />}
              </div>
              <div className="bookBody">
                <div className="bookTitleRow">
                  <strong title={book?.title || slotName}>{book?.title || slotName}</strong>
                  <span>{book ? book.file_type.toUpperCase() : "待上传"}</span>
                </div>
                <div className="bookMeta">
                  {book
                    ? `${book.chapters?.length || 0} 章 / ${compactNumber(book.total_chars)} 字`
                    : "保留教材槽位"}
                </div>
              </div>
              {book ? (
                <button
                  className="slotAction"
                  type="button"
                  onClick={() => onSelect(book.textbook_id)}
                  disabled={selected}
                >
                  {selected ? "已选" : "选择"}
                </button>
              ) : (
                <span className="emptySlot">
                  {loading ? <Loader2 size={14} className="spin" /> : <Circle size={12} />}
                </span>
              )}
            </article>
          );
        })}
      </div>
    </aside>
  );
}

function findSlotBook(textbooks: Textbook[], slotName: string, index: number): Textbook | undefined {
  return (
    textbooks.find((book) => book.title.includes(slotName) || book.filename.includes(slotName)) ||
    textbooks[index]
  );
}

function compactNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN", { notation: "compact" }).format(value);
}

function shortSession(sessionId: string): string {
  return sessionId.length > 12 ? `${sessionId.slice(0, 8)}...${sessionId.slice(-4)}` : sessionId;
}
