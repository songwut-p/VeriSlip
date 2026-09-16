"use client";

import { useEffect, useRef } from "react";
import { X, Send } from "lucide-react";

interface AskPanelProps {
  isOpen: boolean;
  onClose: () => void;
}

const FOCUSABLE_SELECTOR =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

export default function AskPanel({ isOpen, onClose }: AskPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

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
        <div className="self-start max-w-[85%] rounded-xl rounded-bl-sm bg-gray-100 px-3 py-2">
          <p className="text-sm leading-relaxed">
            สวัสดีครับ ถามเกี่ยวกับสลิปหรือยอดเงินได้เลย
          </p>
        </div>

        <div className="flex flex-wrap gap-1.5 self-start max-w-[90%]">
          <button
            type="button"
            className="whitespace-nowrap rounded-full border border-gray-300 px-2.5 py-1.5 text-xs text-gray-600 hover:bg-gray-50"
          >
            ยอดใช้จ่ายเดือนนี้เท่าไหร่
          </button>
          <button
            type="button"
            className="whitespace-nowrap rounded-full border border-gray-300 px-2.5 py-1.5 text-xs text-gray-600 hover:bg-gray-50"
          >
            สลิปล่าสุดกี่ใบ
          </button>
        </div>
      </div>

      {/* Input footer */}
      <div className="flex items-center gap-2 border-t border-border-gray px-4 py-3">
        <input
          type="text"
          placeholder="พิมพ์คำถาม…"
          aria-label="พิมพ์คำถาม"
          className="h-9 flex-1 rounded-lg border border-gray-300 bg-gray-50 px-3 text-sm"
        />
        <button
          type="button"
          aria-label="ส่งคำถาม"
          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-emerald-600 text-white hover:bg-emerald-700"
        >
          <Send size={16} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}