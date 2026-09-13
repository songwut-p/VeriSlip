"use client";

import { useRef, useState } from "react";

export interface DateRange {
  start_date?: string; // ISO 'YYYY-MM-DD'
  end_date?: string;
}

const PRESETS = [
  { label: "1 เดือน", months: 1 },
  { label: "3 เดือน", months: 3 },
  { label: "6 เดือน", months: 6 },
  { label: "12 เดือน", months: 12 },
  { label: "ทั้งหมด", months: null },
] as const;

function toIsoDate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function presetToRange(months: number | null): DateRange {
  if (months === null) return {}; // "ทั้งหมด" -- ไม่กรองเลย
  const end = new Date();
  const start = new Date();
  start.setMonth(start.getMonth() - months);
  return { start_date: toIsoDate(start), end_date: toIsoDate(end) };
}

interface DateRangeFilterProps {
  onChange: (range: DateRange) => void;
}

// preset กับ manual date filter มีสิทธิ์เท่ากัน -- ไม่มีฝั่งไหนถูก disable
// เลย (13 ก.ย. 2026, ตกลงกันหลังพิจารณาหลายแบบ) กติกาเดียว: การกระทำล่าสุด
// ชนะเสมอ -- กด preset แล้ว manual ที่กรอกไว้ (ถ้ามี) จะถูกล้างทิ้ง,
// กรอก manual แล้ว preset ที่เลือกค้างไว้ (ถ้ามี) จะถูกยกเลิกอัตโนมัติ ไม่มี
// การบล็อกการกดฝั่งใดฝั่งหนึ่งในทุกกรณี
export default function DateRangeFilter({ onChange }: DateRangeFilterProps) {
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [manualStart, setManualStart] = useState("");
  const [manualEnd, setManualEnd] = useState("");
  // endDateRef (13 ก.ย. 2026): ใช้ .focus() เด้งไปช่อง "ถึง" อัตโนมัติทันที
  // หลังเลือกวันเริ่มเสร็จ ตามที่ขอ -- ไม่แตะช่อง "เริ่ม" (ไม่ต้อง ref)
  // เพราะ auto-focus ต้องการแค่ทิศทางเดียว (เริ่ม -> สิ้นสุด)
  const endDateRef = useRef<HTMLInputElement>(null);

  const handlePresetClick = (label: string, months: number | null) => {
    setActivePreset(label);
    // preset ชนะ -- ล้าง manual ที่เคยกรอกไว้ทิ้ง (ถ้ามี)
    setManualStart("");
    setManualEnd("");
    onChange(presetToRange(months));
  };

  const handleManualChange = (field: "start" | "end", value: string) => {
    // manual ชนะ -- ยกเลิก preset ที่เลือกค้างไว้ (ถ้ามี) ทันทีที่กรอกช่องไหนก็ตาม
    setActivePreset(null);
    const nextStart = field === "start" ? value : manualStart;
    const nextEnd = field === "end" ? value : manualEnd;
    if (field === "start") {
      setManualStart(value);
      // เด้งเปิด calendar popup ของช่อง "ถึง" อัตโนมัติทันทีที่เลือกวันเริ่ม
      // เสร็จ (ตามที่ขอ 13 ก.ย. 2026) -- showPicker() เปิด popup ตรงๆ เลย
      // ต่างจาก .focus() ที่แค่ขึ้น cursor ไม่เด้ง popup ให้ ต้องเรียกแบบมี
      // fallback (feature detect) เพราะ Firefox บางเวอร์ชันยังไม่รองรับ
      // API นี้ -- ห่อ try/catch เพิ่มเผื่อ browser ปฏิเสธเพราะไม่นับว่าเป็น
      // user-gesture โดยตรง (ยังคง .focus() ไว้เป็น fallback ที่ทำงานได้เสมอ)
      const endInput = endDateRef.current as
        | (HTMLInputElement & { showPicker?: () => void })
        | null;
      if (endInput && value) {
        endInput.focus();
        if (typeof endInput.showPicker === "function") {
          try {
            endInput.showPicker();
          } catch {
            // เบราว์เซอร์บางตัวปฏิเสธถ้าไม่นับว่าเป็น user-gesture โดยตรง --
            // ปล่อยผ่านเงียบๆ อย่างน้อย .focus() ด้านบนก็ยังทำงานอยู่
          }
        }
      }
    } else {
      setManualEnd(value);
    }
    onChange({
      start_date: nextStart || undefined,
      end_date: nextEnd || undefined,
    });
  };

  return (
    // ห่อด้วยกรอบ+พื้นหลัง+label (13 ก.ย. 2026, ตาม feedback) -- เดิมเป็นแค่
    // ปุ่ม+input ลอยอยู่กลางหน้า ไม่มี label กำกับ กลืนกับพื้นหลังหน้าเว็บ
    // ทำให้ดูไม่เด่น ใช้ pattern เดียวกับกล่อง "ประเภทรายการ" ในฟอร์ม
    // human-in-the-loop (กรอบ+พื้นหลัง+label ด้านบน)
    <div className="mb-8 rounded-lg border border-border-gray bg-card-bg p-4">
      <label className="mb-3 block text-sm font-medium text-text-primary">ช่วงเวลา</label>
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex gap-2">
          {PRESETS.map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => handlePresetClick(p.label, p.months)}
              className={`rounded-lg border px-3 py-2 text-sm transition-colors ${
                activePreset === p.label
                  ? "border-emerald bg-emerald text-white"
                  : "border-border-gray bg-page-bg text-text-primary hover:bg-soft-green-bg"
              }`}
            >
              {p.label}
            </button>
          ))}
        </div>

        <span className="h-6 w-px bg-border-gray" />

        <div className="flex items-center gap-2 rounded-lg border border-border-gray bg-page-bg px-3 py-1.5">
          <input
            type="date"
            value={manualStart}
            onChange={(e) => handleManualChange("start", e.target.value)}
            className="text-sm text-text-primary"
          />
          <span className="text-sm text-text-secondary">ถึง</span>
          <input
            ref={endDateRef}
            type="date"
            value={manualEnd}
            onChange={(e) => handleManualChange("end", e.target.value)}
            className="text-sm text-text-primary"
          />
        </div>
      </div>
    </div>
  );
}
