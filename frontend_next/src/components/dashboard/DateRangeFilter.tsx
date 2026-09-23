"use client";

import { useRef, useState } from "react";
import { Calendar } from "lucide-react";

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

// DEFAULT_PRESET (23 ก.ย. 2026): เปิด dashboard มาเริ่มที่ "12 เดือน" แทน
// "ทั้งหมด" -- คนส่วนใหญ่สนใจช่วงล่าสุด และกราฟอ่านง่ายกว่า export ไว้ให้
// dashboard/page.tsx ใช้ตั้งค่า dateRange เริ่มต้นให้ตรงกับปุ่มที่ติดสี
// (ถ้าสองจุดนี้ไม่ตรงกัน ปุ่มจะโชว์ "12 เดือน" แต่ข้อมูลที่ดึงเป็นทั้งหมด)
// ยังนับแบบ "ย้อนจากวันนี้" เหมือนเดิม (12 เดือน = 13 แท่ง เดือนหัวท้ายไม่เต็ม)
// ตัดสินใจเก็บไว้แบบนี้ 23 ก.ย. 2026 หลังเทียบกับแบบเดือนปฏิทินแล้ว
export const DEFAULT_PRESET = PRESETS[3];

// toIsoDate (23 ก.ย. 2026): ประกอบวันที่จากเวลาเครื่อง (local) เอง -- เดิมใช้
// toISOString() ซึ่งเป็นเวลา UTC ทำให้กด preset ช่วงตี 0 ถึง 7 โมงเช้าเวลาไทย
// (UTC+7) แล้ววันที่เลื่อนไปเป็นเมื่อวาน สลิปของวันนั้นหลุดจากตัวกรอง
function toIsoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function presetToRange(months: number | null): DateRange {
  if (months === null) return {}; // "ทั้งหมด" -- ไม่กรองเลย
  const end = new Date();
  const start = new Date();
  start.setMonth(start.getMonth() - months);
  return { start_date: toIsoDate(start), end_date: toIsoDate(end) };
}

// formatThaiDate (16 ก.ย. 2026): แปลง ISO 'YYYY-MM-DD' ที่ <input type="date">
// เก็บภายใน ให้เป็น dd/mm/yyyy สำหรับโชว์ผู้ใช้เท่านั้น -- ตัว input จริง
// ยังเป็น native date picker เหมือนเดิมทุกอย่าง (แค่ซ่อนไว้ไม่ให้เห็น)
function formatThaiDate(iso: string): string {
  if (!iso) return "ว/ด/ป";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
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
  const [activePreset, setActivePreset] = useState<string | null>(DEFAULT_PRESET.label);
  const [manualStart, setManualStart] = useState("");
  const [manualEnd, setManualEnd] = useState("");
  const startDateRef = useRef<HTMLInputElement>(null);
  const endDateRef = useRef<HTMLInputElement>(null);

  // openPicker (16 ก.ย. 2026): ดึง logic showPicker()+fallback ที่เดิมอยู่
  // ในตัว handleManualChange โดยตรง ออกมาเป็นฟังก์ชันแยก เพราะตอนนี้ต้อง
  // เรียกจาก 2 จุด (ปุ่มโชว์วันที่ทั้งสองช่อง) ไม่ใช่แค่ auto-open ช่อง
  // "ถึง" แบบเดิม -- logic ข้างในเหมือนเดิมทุกอย่าง ไม่ได้เปลี่ยนพฤติกรรม
  const openPicker = (ref: React.RefObject<HTMLInputElement | null>) => {
    const input = ref.current as (HTMLInputElement & { showPicker?: () => void }) | null;
    if (!input) return;
    input.focus();
    if (typeof input.showPicker === "function") {
      try {
        input.showPicker();
      } catch {
        // เบราว์เซอร์บางตัวปฏิเสธถ้าไม่นับว่าเป็น user-gesture โดยตรง --
        // ปล่อยผ่านเงียบๆ อย่างน้อย .focus() ด้านบนก็ยังทำงานอยู่
      }
    }
  };

  const handlePresetClick = (label: string, months: number | null) => {
    setActivePreset(label);
    setManualStart("");
    setManualEnd("");
    onChange(presetToRange(months));
  };

  const handleManualChange = (field: "start" | "end", value: string) => {
    setActivePreset(null);
    const nextStart = field === "start" ? value : manualStart;
    const nextEnd = field === "end" ? value : manualEnd;
    if (field === "start") {
      setManualStart(value);
      if (value) openPicker(endDateRef);
    } else {
      setManualEnd(value);
    }
    onChange({
      start_date: nextStart || undefined,
      end_date: nextEnd || undefined,
    });
  };

  return (
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
          {/* จุดนี้ (16 ก.ย. 2026): input date จริงซ่อนไว้ (absolute + opacity-0)
              แต่ยังเป็น native date picker ทำงานปกติทุกอย่าง -- ปุ่มที่เห็น
              (โชว์ dd/mm/yyyy) เป็นแค่ trigger เรียก showPicker() ของมัน
              ไม่ต้องลง library เพิ่ม ยังใช้ปฏิทิน native เดิม */}
          <div className="relative">
            <input
              ref={startDateRef}
              type="date"
              value={manualStart}
              onChange={(e) => handleManualChange("start", e.target.value)}
              className="absolute inset-0 opacity-0 pointer-events-none"
              tabIndex={-1}
            />
            <button
              type="button"
              onClick={() => openPicker(startDateRef)}
              className="flex items-center gap-1.5 text-sm text-text-primary"
            >
              <Calendar size={14} className="text-text-secondary" />
              {formatThaiDate(manualStart)}
            </button>
          </div>

          <span className="text-sm text-text-secondary">ถึง</span>

          <div className="relative">
            <input
              ref={endDateRef}
              type="date"
              value={manualEnd}
              onChange={(e) => handleManualChange("end", e.target.value)}
              className="absolute inset-0 opacity-0"
              tabIndex={-1}
            />
            <button
              type="button"
              onClick={() => openPicker(endDateRef)}
              className="flex items-center gap-1.5 text-sm text-text-primary"
            >
              <Calendar size={14} className="text-text-secondary" />
              {formatThaiDate(manualEnd)}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
