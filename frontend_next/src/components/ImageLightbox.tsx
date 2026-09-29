"use client";

import { useEffect, useRef } from "react";
import { X } from "lucide-react";

// ImageLightbox (29 ก.ย. 2026): คลิกรูปสลิปแล้วขยายเต็มจอ -- หน้าอัปโหลด
// แบบพอดีจอ (727902d) ทำให้รูปในกล่องซ้ายเล็กลง อ่านเลขบัญชีได้ยาก ซึ่งเสีย
// จุดประสงค์ของขั้น human review (เทียบรูปกับฟอร์ม)
//
// แบบแผนเดียวกับ ConfirmDialog: ฉากหลัง bg-black/40 z-50, Esc ปิด, โฟกัส
// ไปที่ปุ่มตอนเปิด และคืนโฟกัสให้ตัวที่กดเปิดตอนปิด
// ต่างกัน: คลิกพื้นหลังปิด แต่คลิกตัวรูปไม่ปิด (กันเผลอปิดตอนกำลังเพ่งอ่าน)
type ImageLightboxProps = {
  open: boolean;
  src: string;
  alt: string;
  onClose: () => void;
};

export default function ImageLightbox({ open, src, alt, onClose }: ImageLightboxProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  // เหตุผลเดียวกับ ConfirmDialog: ให้ effect ด้านล่างผูกกับ [open] อย่างเดียว
  // ถ้า parent ส่ง onClose เป็นฟังก์ชัน inline effect จะรันซ้ำทุก render แล้วแย่ง focus
  const latest = useRef({ onClose });
  useEffect(() => {
    latest.current = { onClose };
  });

  useEffect(() => {
    if (!open) return;

    // จำว่าก่อนเปิด focus อยู่ที่ไหน (ตัวรูปที่กดเปิด) จะได้คืนให้ตอนปิด
    const previouslyFocused = document.activeElement as HTMLElement | null;
    closeRef.current?.focus();

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        latest.current.onClose();
        return;
      }
      // มีปุ่มเดียว -- Tab/Shift+Tab ให้วนอยู่ที่ปุ่มปิด ไม่หลุดไปหน้าข้างหลัง
      if (e.key === "Tab") {
        e.preventDefault();
        closeRef.current?.focus();
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
    <div
      role="dialog"
      aria-modal="true"
      aria-label={alt}
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
    >
      <div className="absolute inset-0 bg-black/70" aria-hidden="true" onClick={onClose} />

      {/* eslint-disable-next-line @next/next/no-img-element -- blob URL ใช้ next/image ไม่ได้ */}
      <img
        src={src}
        alt={alt}
        className="relative max-h-full max-w-full rounded-lg bg-white object-contain shadow-xl"
      />

      <button
        ref={closeRef}
        type="button"
        onClick={onClose}
        aria-label="ปิดรูปขยาย"
        title="ปิด (Esc)"
        className="absolute right-4 top-4 rounded-full bg-white/90 p-2 text-text-primary shadow hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
      >
        <X size={20} />
      </button>
    </div>
  );
}
