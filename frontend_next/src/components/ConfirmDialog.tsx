"use client";

import { useEffect, useRef } from "react";

type ConfirmDialogProps = {
  open: boolean;
  title: string;
  message: string;
  /** ชื่อรายการที่กำลังจะถูกกระทำ เช่น ชื่อไฟล์สลิป (ไม่ใส่ = ไม่แสดงกล่อง) */
  itemName?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** true ระหว่างรอ API — กันกดซ้ำและกันปิด modal กลางทาง */
  isBusy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export default function ConfirmDialog({
  open,
  title,
  message,
  itemName,
  confirmLabel = "ยืนยัน",
  cancelLabel = "ยกเลิก",
  isBusy = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);

  // เก็บค่าล่าสุดไว้ใน ref เพื่อให้ effect ด้านล่างผูกกับ [open] อย่างเดียว
  // (ถ้า parent ส่ง onCancel เป็นฟังก์ชัน inline effect จะรันซ้ำทุก render แล้วแย่ง focus)
  const latest = useRef({ onCancel, isBusy });
  useEffect(() => {
    latest.current = { onCancel, isBusy };
  });

  useEffect(() => {
    if (!open) return;

    // จำไว้ว่าก่อนเปิด focus อยู่ที่ไหน (ปุ่มลบ) จะได้คืนให้ตอนปิด
    const previouslyFocused = document.activeElement as HTMLElement | null;
    // ตั้งต้นที่ "ยกเลิก" — การลบย้อนกลับไม่ได้ กด Enter พลาดจะไม่ลบทันที
    cancelRef.current?.focus();

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        if (!latest.current.isBusy) latest.current.onCancel();
        return;
      }
      if (e.key !== "Tab") return;

      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        "button:not([disabled])"
      );
      if (!focusable || focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      previouslyFocused?.focus();
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/40"
        aria-hidden="true"
        onClick={() => {
          if (!isBusy) onCancel();
        }}
      />

      <div
        ref={dialogRef}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-message"
        className="relative w-full max-w-md rounded-lg bg-white p-6 shadow-xl"
      >
        <h2
          id="confirm-dialog-title"
          className="text-lg font-semibold text-text-primary"
        >
          {title}
        </h2>
        <p id="confirm-dialog-message" className="mt-2 text-sm text-text-primary">
          {message}
        </p>

        {itemName && (
          <p className="mt-3 rounded-md border border-border-gray bg-page-bg px-3 py-2 text-sm font-medium text-text-primary break-all">
            {itemName}
          </p>
        )}

        <div className="mt-6 flex justify-end gap-3">
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            disabled={isBusy}
            className="rounded-md border border-border-input px-4 py-2 text-sm text-text-primary hover:bg-page-bg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring disabled:cursor-not-allowed disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isBusy}
            className="rounded-md bg-danger px-4 py-2 text-sm font-medium text-white hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
