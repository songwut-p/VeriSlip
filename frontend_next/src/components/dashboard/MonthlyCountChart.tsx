"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import type { MonthlyTrend } from "@/types/dashboard-types";

const THAI_MONTHS = [
  "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
  "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
];

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload || !payload.length) return null;

  const amount = payload[0].value;
  if (!amount || amount === 0) return null;

  return (
    <div className="rounded-lg border border-gray-200 bg-white px-3 py-2 shadow-sm">
      <p className="text-sm font-medium text-text-primary">{label}</p>
      <p className="text-sm text-text-secondary">
        ยอดเงินรวม : {Number(amount).toLocaleString("th-TH")} บาท
      </p>
    </div>
  );
}

function CustomCursor(props: any) {
  const { x, y, width, height, payload } = props;
  const amount = payload?.[0]?.payload?.amount;
  if (!amount || amount === 0) return null;

    return <rect x={x} y={y} width={width} height={height} fill="#0F4C3A" fillOpacity={0.08} />;
}

interface YearMonth {
  year: number;
  month: number; // 1-12
}

// สร้างรายการ (year, month) ทุกเดือนตั้งแต่ start ถึง end แบบรวมปลายทั้งคู่
// (inclusive) -- ใช้แทนของเดิมที่ hardcode 12 เดือนของปีปัจจุบันตายตัว
function enumerateMonths(start: YearMonth, end: YearMonth): YearMonth[] {
  const months: YearMonth[] = [];
  let y = start.year;
  let m = start.month;
  // กันลูปไม่รู้จบถ้า start มาหลัง end ผิดพลาด (ไม่ควรเกิดขึ้นจริง)
  let guard = 0;
  while ((y < end.year || (y === end.year && m <= end.month)) && guard < 1000) {
    months.push({ year: y, month: m });
    m += 1;
    if (m > 12) {
      m = 1;
      y += 1;
    }
    guard += 1;
  }
  return months;
}

function parseIsoDate(iso: string): YearMonth {
  const [y, m] = iso.split("-").map(Number);
  return { year: y, month: m };
}

// แปลง ค.ศ. -> ตัวเลขท้าย 2 หลักของ พ.ศ. (เช่น 2026 -> "69") ใช้ต่อท้าย
// ชื่อเดือนเฉพาะตอนกราฟครอบคลุมมากกว่า 1 ปี ป้องกันเดือนซ้ำชื่อกันข้ามปี
// (ตัวเลขเดียวพอ ไม่ต้องเต็ม 4 หลัก เพราะพื้นที่แกน x จำกัด)
function shortBuddhistYear(year: number): string {
  return String((year + 543) % 100).padStart(2, "0");
}

interface MonthlyCountChartProps {
  data: MonthlyTrend[];
  // startDate/endDate (13 ก.ย. 2026): ช่วงวันที่ที่เลือกไว้จาก DateRangeFilter
  // (ทั้ง preset และ manual ส่งมาเป็น ISO string เดียวกัน) ใช้กำหนดว่ากราฟ
  // ควร zero-fill กี่เดือน/เดือนไหนบ้าง แทนที่จะโชว์ 12 เดือนของปีปัจจุบัน
  // ตายตัวเหมือนเดิม -- undefined ทั้งคู่ = ไม่ได้กรอง ("ทั้งหมด")
  startDate?: string;
  endDate?: string;
}

export function MonthlyCountChart({ data, startDate, endDate }: MonthlyCountChartProps) {
  let months: YearMonth[];

  if (startDate && endDate) {
    // มีตัวกรองช่วงวันที่ชัดเจน (preset หรือ manual) -- โชว์เฉพาะเดือนใน
    // ช่วงนั้นเป๊ะๆ ตามที่ขอ (เดิมโชว์ 12 เดือนเสมอไม่สนตัวกรอง)
    months = enumerateMonths(parseIsoDate(startDate), parseIsoDate(endDate));
  } else if (data.length > 0) {
    // "ทั้งหมด" (ไม่กรอง) -- derive ช่วงเดือนจากข้อมูลจริงที่มีอยู่ แทนที่จะ
    // ตายตัวเป็นปีปัจจุบัน เผื่อมีข้อมูลข้ามปีจริง
    const sorted = [...data].sort((a, b) => a.year * 12 + a.month - (b.year * 12 + b.month));
    months = enumerateMonths(
      { year: sorted[0].year, month: sorted[0].month },
      { year: sorted[sorted.length - 1].year, month: sorted[sorted.length - 1].month }
    );
  } else {
    // ไม่มีข้อมูลเลยและไม่มีตัวกรอง -- fallback โชว์แค่เดือนปัจจุบันเดือนเดียว
    // (ไม่มีข้อมูลอ้างอิงให้กำหนดช่วงกว้างกว่านี้ได้อย่างมีความหมาย)
    const now = new Date();
    months = [{ year: now.getFullYear(), month: now.getMonth() + 1 }];
  }

  const spansMultipleYears = new Set(months.map((m) => m.year)).size > 1;

  const chartData = months.map(({ year, month }) => {
    const match = data.find((item) => item.month === month && item.year === year);
    const baseLabel = THAI_MONTHS[month - 1];
    return {
      label: spansMultipleYears ? `${baseLabel} ${shortBuddhistYear(year)}` : baseLabel,
      amount: match ? match.total_amount : 0,
    };
  });

  return (
    <div style={{ width: "100%", height: 240 }}>
      <ResponsiveContainer>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" />
          <YAxis tickFormatter={(value) => value.toLocaleString("th-TH")} />
          <Tooltip content={<CustomTooltip />} cursor={<CustomCursor />} />
          <Bar dataKey="amount" fill="#0F4C3A" radius={[4, 4, 0, 0]} activeBar={false} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
