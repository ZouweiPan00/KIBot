import {
  BookOpen,
  CheckCircle2,
  Circle,
  FileUp,
  Loader2,
  PlusCircle,
  RotateCcw,
} from "lucide-react";
import type { ReactNode } from "react";

import type { Textbook } from "../types";

export const MEDICAL_TEXTBOOKS = [
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
  sessionBusy: boolean;
  error: string | null;
  onUpload: (file: File) => void;
  onSelect: (textbookId: string) => void;
  onSelectAll: () => void;
  onRefreshSession: () => void;
  onNewSession: () => void;
}

export function TextbookPanel({
  textbooks,
  selectedIds,
  sessionId,
  loading,
  uploading,
  selectingAll,
  sessionBusy,
  error,
  onUpload,
  onSelect,
  onSelectAll,
  onRefreshSession,
  onNewSession,
}: Props) {
  const totalChars = textbooks.reduce((sum, book) => sum + (book.total_chars || 0), 0);
  const totalChapters = textbooks.reduce((sum, book) => sum + (book.chapters?.length || 0), 0);
  const { slotBooks, customBooks } = assignTextbookGroups(textbooks);

  return (
    <aside className="panel leftPanel" aria-label="教材管理">
      <div className="panelHeader">
        <div>
          <span className="sectionKicker">Textbook Corpus</span>
          <h2>教材管理</h2>
        </div>
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

      <div className="sessionActions" aria-label="会话控制">
        <button
          className="toolButton"
          type="button"
          disabled={!sessionId || sessionBusy}
          onClick={onRefreshSession}
        >
          {sessionBusy ? <Loader2 size={16} className="spin" /> : <RotateCcw size={16} />}
          更新会话
        </button>
        <button className="toolButton primary" type="button" disabled={sessionBusy} onClick={onNewSession}>
          {sessionBusy ? <Loader2 size={16} className="spin" /> : <PlusCircle size={16} />}
          新建对话
        </button>
      </div>

      <label className="uploadDrop">
        <FileUp size={20} />
        <span>{uploading ? "上传解析中" : "上传教材"}</span>
        <input
          type="file"
          accept=".pdf,.txt,.md,.markdown,.docx"
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
          <strong>{textbooks.length}</strong>
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
          const book = slotBooks[index];
          const selected = book ? selectedIds.has(book.textbook_id) : false;

          return (
            <TextbookItem
              key={slotName}
              book={book}
              title={book ? displayTextbookTitle(book, index) : slotName}
              selected={selected}
              onSelect={onSelect}
              emptyAction={
                <span className="emptySlot">
                  {loading ? <Loader2 size={14} className="spin" /> : <Circle size={12} />}
                </span>
              }
            />
          );
        })}
      </div>

      {customBooks.length ? (
        <div className="customTextbookSection">
          <span className="mutedLabel">Custom Uploads</span>
          <div className="textbookList" aria-label="自定义上传教材">
            {customBooks.map((book) => {
              const selected = selectedIds.has(book.textbook_id);

              return (
                <TextbookItem
                  key={book.textbook_id}
                  book={book}
                  title={displayTextbookTitle(book)}
                  selected={selected}
                  onSelect={onSelect}
                />
              );
            })}
          </div>
        </div>
      ) : null}
    </aside>
  );
}

interface TextbookItemProps {
  book?: Textbook;
  title: string;
  selected: boolean;
  onSelect: (textbookId: string) => void;
  emptyAction?: ReactNode;
}

function TextbookItem({ book, title, selected, onSelect, emptyAction }: TextbookItemProps) {
  return (
    <article className={`textbookItem ${selected ? "selected" : ""}`}>
      <div className="bookIcon" aria-hidden="true">
        {selected ? <CheckCircle2 size={18} /> : <BookOpen size={18} />}
      </div>
      <div className="bookBody">
        <div className="bookTitleRow">
          <strong title={title}>{title}</strong>
          <span>{book ? book.file_type.toUpperCase() : "待上传"}</span>
        </div>
        <div className="bookMeta">
          {book ? `${book.chapters?.length || 0} 章 / ${compactNumber(book.total_chars)} 字` : "测试教材"}
        </div>
      </div>
      {book ? (
        <button className="slotAction" type="button" onClick={() => onSelect(book.textbook_id)} disabled={selected}>
          {selected ? "已选" : "选择"}
        </button>
      ) : (
        emptyAction
      )}
    </article>
  );
}

function assignTextbookGroups(textbooks: Textbook[]): {
  slotBooks: Array<Textbook | undefined>;
  customBooks: Textbook[];
} {
  const slots: Array<Textbook | undefined> = Array(MEDICAL_TEXTBOOKS.length).fill(undefined);
  const customBooks: Textbook[] = [];

  for (const book of textbooks) {
    const index = textbookSlotIndex(book);
    if (index >= 0 && index < slots.length && !slots[index]) {
      slots[index] = book;
    } else {
      customBooks.push(book);
    }
  }

  return { slotBooks: slots, customBooks };
}

function textbookSlotIndex(book: Textbook): number {
  const rawTitle = book.title || "";
  const filename = book.filename || "";
  const prefix = titlePrefix(rawTitle) || titlePrefix(filename);
  if (prefix) {
    const index = Number(prefix) - 1;
    const expectedTitle = MEDICAL_TEXTBOOKS[index];
    if (expectedTitle && containsPresetTitle(book, expectedTitle)) {
      return index;
    }
  }
  return MEDICAL_TEXTBOOKS.findIndex((slotName) => containsPresetTitle(book, slotName));
}

export function displayTextbookTitle(book: Textbook, index?: number): string {
  const rawTitle = book.title || book.filename || "";
  const prefix = titlePrefix(rawTitle) || titlePrefix(book.filename);
  if (prefix) {
    const prefixIndex = Number(prefix) - 1;
    const mapped = MEDICAL_TEXTBOOKS[prefixIndex];
    if (mapped && containsPresetTitle(book, mapped)) {
      return mapped;
    }
  }
  if (typeof index === "number" && looksLikePlaceholderTitle(rawTitle)) {
    return MEDICAL_TEXTBOOKS[index] || rawTitle;
  }
  return rawTitle;
}

function titlePrefix(value: string): string | null {
  const match = value.match(/^\s*0?([1-7])(?:[_\-\s.．、]|$)/);
  return match ? match[1] : null;
}

function looksLikePlaceholderTitle(value: string): boolean {
  return /^0?[1-7][_\-\s.．、]*_*$/.test(value.trim());
}

function containsPresetTitle(book: Textbook, presetTitle: string): boolean {
  const normalizedPresetTitle = normalizeTextbookSignal(presetTitle);
  return [book.title, book.filename]
    .filter((value): value is string => Boolean(value))
    .some((value) => normalizeTextbookSignal(value).includes(normalizedPresetTitle));
}

function normalizeTextbookSignal(value: string): string {
  return value
    .normalize("NFKC")
    .toLowerCase()
    .replace(/\.(pdf|txt|md|markdown)$/i, "")
    .replace(/[\s_\-.．、()（）[\]【】《》<>]+/g, "");
}

function compactNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN", { notation: "compact" }).format(value);
}

function shortSession(sessionId: string): string {
  return sessionId.length > 12 ? `${sessionId.slice(0, 8)}...${sessionId.slice(-4)}` : sessionId;
}
