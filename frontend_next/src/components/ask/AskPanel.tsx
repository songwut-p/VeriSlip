"use client";

import { useEffect, useRef, useState } from "react";
import { X, Send } from "lucide-react";
import { apiFetch, ApiRequestError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";

interface AskPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

// shape ของ /ask response แต่ละ mode (ดู rag/query_router.py) -- ยังไม่มี
// response formatter ฝั่ง backend เลยต้องแปลงเป็นข้อความอ่านง่ายฝั่งนี้เอง
// ชั่วคราวก่อน (16 ก.ย. 2026) พรุ่งนี้ค่อยดูแนวทางที่ดีกว่านี้
interface AskResult {
  mode: string;
  sql?: string;
  rows?: Record<string, unknown>[];
  matches?: { filename: string; document: string; distance: number }[];
  message?: string;
  reason?: string;
  error?: string;
  closest_distance?: number | null;
}

// ผลจาก intent ยอดรวม (rag/query_router.py: _direction_totals) -- แยกรายรับ/รายจ่าย
// ตัวเลขจัดรูปแบบในโค้ด ไม่ให้ LLM แต่ง
const DIRECTION_LABEL: Record<"income" | "expense", string> = {
  income: "รายรับ",
  expense: "รายจ่าย",
};

function formatBaht(n: unknown): string {
  return Number(n ?? 0).toLocaleString("th-TH", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function directionLine(kind: "income" | "expense", total: unknown, count: unknown): string {
  const c = Number(count ?? 0);
  if (c === 0) return `ไม่พบรายการ${DIRECTION_LABEL[kind]}`;
  return `${DIRECTION_LABEL[kind]}รวม ${formatBaht(total)} บาท (${c} รายการ)`;
}

function formatDirectionTotals(row: Record<string, unknown>): string {
  const lines: string[] = [];
  const d = row.direction;
  if (d === "income" || d === "expense") {
    lines.push(directionLine(d, row.total, row.count));
  } else {
    lines.push(directionLine("income", row.income_total, row.income_count));
    lines.push(directionLine("expense", row.expense_total, row.expense_count));
  }
  const untyped = Number(row.untyped_count ?? 0);
  if (untyped > 0) {
    lines.push(
      `หมายเหตุ: มีอีก ${untyped} สลิปที่ยังไม่ได้ระบุว่าเป็นรายรับหรือรายจ่าย จึงไม่ได้นับรวมในยอดนี้`
    );
  }
  return lines.join("\n");
}

// แปลงแถวผลลัพธ์ทั่วไป (pattern/LLM-SQL) เป็นข้อความอ่านง่าย -- คอลัมน์ที่ไม่รู้จักยังโชว์ key: value
// ไม่ทิ้งข้อมูล ตัวเลขจัดรูปแบบในโค้ด ไม่ให้ LLM แต่ง
const THAI_MONTHS = [
  "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
  "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
];

const COUNT_KEYS = new Set(["slip_count", "count"]);
const AMOUNT_LABELS: Record<string, string> = {
  total_amount: "ยอดรวม",
  total: "ยอดรวม",
  amount: "จำนวนเงิน",
  avg_amount: "ยอดเฉลี่ย",
  max_amount: "สูงสุด",
  min_amount: "ต่ำสุด",
};
const COLUMN_LABELS: Record<string, string> = {
  sender_name: "ผู้โอน",
  recipient_name: "ผู้รับ",
  bank_name: "ธนาคาร",
  source_app: "แอป",
  filename: "ไฟล์",
  datetime_raw: "วันเวลา",
  symbol: "หุ้น",
};

function formatMonthYear(month: unknown, year: unknown): string {
  const m = Number(month);
  // เดือนเป็น NULL ได้ถ้า OCR อ่านวันที่ไม่ออก -- ไม่เดา บอกตรง ๆ ว่าไม่ทราบ
  const monthText = month != null && m >= 1 && m <= 12 ? THAI_MONTHS[m - 1] : "ไม่ทราบเดือน";
  if (year == null) return monthText;
  return `${monthText} ${Number(year) + 543}`; // DB เก็บปี ค.ศ. แสดงเป็น พ.ศ.
}

function formatTransactionType(value: unknown): string {
  if (value === "income" || value === "expense") return DIRECTION_LABEL[value];
  // NULL = สลิปเก่าที่ยังไม่ได้เลือกประเภท -- ไม่เดา บอกตรง ๆ
  if (value == null || value === "") return "ไม่ระบุประเภท";
  return String(value); // ค่าที่ไม่รู้จัก โชว์ตามจริง ไม่ทิ้ง
}

function formatRow(row: Record<string, unknown>): string {
  const parts: string[] = [];
  if ("datetime_month" in row) {
    parts.push(formatMonthYear(row.datetime_month, row.datetime_year));
  } else if ("datetime_year" in row) {
    parts.push(row.datetime_year == null ? "ไม่ทราบปี" : `ปี ${Number(row.datetime_year) + 543}`);
  }
  if ("transaction_type" in row) {
    parts.push(formatTransactionType(row.transaction_type));
  }
  for (const [key, value] of Object.entries(row)) {
    if (key === "datetime_month" || key === "datetime_year" || key === "transaction_type") continue;
    if (COUNT_KEYS.has(key)) {
      parts.push(`${Number(value ?? 0)} ใบ`);
    } else if (key in AMOUNT_LABELS) {
      parts.push(`${AMOUNT_LABELS[key]} ${formatBaht(value)} บาท`);
    } else {
      const label = COLUMN_LABELS[key] ?? key;
      const text = value == null || value === "" ? "ไม่ระบุ" : String(value);
      parts.push(`${label}: ${text}`);
    }
  }
  return parts.join(" · ");
}

function formatAskResult(result: AskResult): string {
  switch (result.mode) {
    case "pattern":
    case "llm_sql": {
      const rows = result.rows ?? [];
      if (rows.length === 0) return "ไม่พบข้อมูลที่ตรงกับคำถามนี้";
      if (rows.length === 1 && "direction" in rows[0]) return formatDirectionTotals(rows[0]);
            if (rows.length === 1) return formatRow(rows[0]);
      // หลายแถว -- ใส่เลขลำดับ โชว์สูงสุด 5 แถวแรก กันข้อความยาวเกินไป
      const shown = rows
        .slice(0, 5)
        .map((r, i) => `${i + 1}. ${formatRow(r)}`)
        .join("\n");
      const more = rows.length > 5 ? `\n(และอีก ${rows.length - 5} รายการ)` : "";
      return `${shown}${more}`;
    }
    case "semantic": {
      const matches = result.matches ?? [];
      if (matches.length === 0) return "ไม่พบสลิปที่ตรงกับคำถามนี้";
      return matches.map((m) => `${m.filename}: ${m.document}`).join("\n");
    }
    case "no_confident_match":
    case "no_match":
      return result.message ?? "ไม่พบข้อมูลที่เกี่ยวข้อง";
    case "rejected":
      return `ขอโทษครับ ยังตอบคำถามนี้ไม่ได้ (${result.reason ?? "SQL ไม่ผ่านการตรวจสอบ"})`;
    case "sql_error":
      return `เกิดข้อผิดพลาดตอนค้นหาข้อมูล (${result.error ?? "unknown error"})`;
    default:
      return "ไม่สามารถประมวลผลคำตอบได้";
  }
}

const FOCUSABLE_SELECTOR =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export default function AskPanel({ isOpen, onClose }: AskPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const { token } = useAuth();

  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "assistant", text: "สวัสดีครับ ถามเกี่ยวกับสลิปหรือยอดเงินได้เลย" },
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);

  const handleSend = async (question: string) => {
    const q = question.trim();
    if (!q || isSending) return;

    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setInput("");
    setIsSending(true);

    try {
      const result = await apiFetch<AskResult>("/ask", {
        method: "POST",
        token,
        body: JSON.stringify({ question: q }),
      });
      setMessages((prev) => [...prev, { role: "assistant", text: formatAskResult(result) }]);
    } catch (e) {
      const msg = e instanceof ApiRequestError ? e.message : "เกิดข้อผิดพลาด กรุณาลองใหม่";
      setMessages((prev) => [...prev, { role: "assistant", text: msg }]);
    } finally {
      setIsSending(false);
    }
  };

  useEffect(() => {
    if (!isOpen) return;
    const panel = panelRef.current;
    if (!panel) return;

    const focusables = panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
    focusables[0]?.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab") return;

      const els = panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      if (els.length === 0) return;
      const first = els[0];
      const last = els[els.length - 1];

      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <div
      ref={panelRef}
      role="dialog"
      aria-modal="true"
      aria-label="กล่องถาม AI"
      className={`fixed top-0 right-0 bottom-0 z-40 flex w-full max-w-[550px] flex-col bg-white border-l border-border-gray transition-transform duration-300 ease-out motion-reduce:transition-none motion-reduce:duration-0 ${
        isOpen ? "translate-x-0" : "translate-x-full"
      }`}
      style={{ overscrollBehavior: "contain" }}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border-gray px-4 py-3">
        <span className="text-[15px] font-medium">ถามข้อมูล</span>
        <button
            type="button"
            onClick={onClose}
            aria-label="ปิดกล่องถาม AI"
            className="flex h-8 w-8 items-center justify-center rounded-md border border-border-gray text-gray-700 hover:bg-gray-100 hover:text-gray-900"
                >
            <X size={20} aria-hidden="true" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`max-w-[85%] whitespace-pre-wrap rounded-xl px-3 py-2 text-[19.5px] leading-relaxed ${
              m.role === "user"
                ? "self-end rounded-br-sm bg-emerald-600 text-white"
                : "self-start rounded-bl-sm bg-gray-100"
            }`}
          >
            {m.text}
          </div>
        ))}

        {isSending && (
          <div className="self-start max-w-[85%] rounded-xl rounded-bl-sm bg-gray-100 px-3 py-2">
            <p className="text-base leading-relaxed text-gray-500">กำลังค้นข้อมูล...</p>
          </div>
        )}

        {messages.length === 1 && (
          <div className="flex flex-wrap gap-1.5 self-start max-w-[90%]">
            <button
              type="button"
              onClick={() => handleSend("ยอดใช้จ่ายเดือนนี้เท่าไหร่")}
              className="whitespace-nowrap rounded-full border border-gray-300 px-2.5 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
            >
              ยอดใช้จ่ายเดือนนี้เท่าไหร่
            </button>
            <button
              type="button"
              onClick={() => handleSend("สลิปล่าสุดกี่ใบ")}
              className="whitespace-nowrap rounded-full border border-gray-300 px-2.5 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
            >
              สลิปล่าสุดกี่ใบ
            </button>
          </div>
        )}
      </div>

      {/* Input footer */}
      <div className="flex items-center gap-2 border-t border-border-gray px-4 py-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSend(input);
          }}
          placeholder="พิมพ์คำถาม…"
          aria-label="พิมพ์คำถาม"
          disabled={isSending}
          className="h-9 flex-1 rounded-lg border border-gray-300 bg-gray-50 px-3 text-base disabled:opacity-60"
        />
        <button
          type="button"
          onClick={() => handleSend(input)}
          disabled={isSending || !input.trim()}
          aria-label="ส่งคำถาม"
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50"
        >
          <Send size={16} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
