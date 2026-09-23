"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import type { MonthlyTrend } from "@/types/dashboard-types";

const THAI_MONTHS = [
  "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
  "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
];

// type ของ props ที่ recharts ส่งให้ tooltip/cursor (23 ก.ย. 2026) -- เดิมเป็น
// any ทั้งคู่ ผิดกฎ @typescript-eslint/no-explicit-any ประกาศเองเฉพาะ field
// ที่ใช้จริง ไม่ import type จาก recharts เพราะชื่อ/รูปร่างเปลี่ยนตามเวอร์ชัน
interface ChartPoint {
  label: string;
  amount: number;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: { value?: number }[];
  label?: string;
}

interface CustomCursorProps {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  payload?: { payload?: ChartPoint }[];
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
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

function CustomCursor(props: CustomCursorProps) {
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

// MAX_ZERO_FILL_MONTHS (23 ก.ย. 2026): ถ้าช่วงที่จะวาดยาวเกินนี้ เลิกเติมเดือน
// ว่าง โชว์เฉพาะเดือนที่มีข้อมูลแทน -- เดิมกด "ทั้งหมด" กับบัญชีที่มีสลิป
// ทดสอบปี 2022 ปนกับ 2026 ได้ 55 แท่ง มีข้อมูลจริงแค่ 5 แท่ง กราฟยืดเป็น
// แถบว่างยาว เลือก 24 = 2 เท่าของ preset ยาวสุด (12 เดือน) preset ทั้งหมด
// จึงไม่โดนกฎนี้ มีผลเฉพาะ "ทั้งหมด" หรือเลือกวันที่เองเป็นช่วงยาวเท่านั้น
// ข้อแลก: แกนเดือนจะไม่ต่อเนื่อง แต่ label มีปี พ.ศ. กำกับทุกแท่งอยู่แล้ว
const MAX_ZERO_FILL_MONTHS = 24;

function monthKey({ year, month }: YearMonth): number {
  return year * 12 + month;
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
  // เรียงครั้งเดียว ใช้ทั้งตอนหาช่วง "ทั้งหมด" และตอนเลิกเติมเดือนว่าง
  const sortedData = [...data].sort((a, b) => monthKey(a) - monthKey(b));

  if (startDate && endDate) {
    // มีตัวกรองช่วงวันที่ชัดเจน (preset หรือ manual) -- โชว์เฉพาะเดือนใน
    // ช่วงนั้นเป๊ะๆ ตามที่ขอ (เดิมโชว์ 12 เดือนเสมอไม่สนตัวกรอง)
    months = enumerateMonths(parseIsoDate(startDate), parseIsoDate(endDate));
  } else if (data.length > 0) {
    // "ทั้งหมด" (ไม่กรอง) -- derive ช่วงเดือนจากข้อมูลจริงที่มีอยู่ แทนที่จะ
    // ตายตัวเป็นปีปัจจุบัน เผื่อมีข้อมูลข้ามปีจริง
    const first = sortedData[0];
    const last = sortedData[sortedData.length - 1];
    months = enumerateMonths(
      { year: first.year, month: first.month },
      { year: last.year, month: last.month }
    );
  } else {
    // ไม่มีข้อมูลเลยและไม่มีตัวกรอง -- fallback โชว์แค่เดือนปัจจุบันเดือนเดียว
    // (ไม่มีข้อมูลอ้างอิงให้กำหนดช่วงกว้างกว่านี้ได้อย่างมีความหมาย)
    const now = new Date();
    months = [{ year: now.getFullYear(), month: now.getMonth() + 1 }];
  }

  if (months.length > MAX_ZERO_FILL_MONTHS) {
    // กันเดือนซ้ำเผื่อ data มีหลายแถวในเดือนเดียวกัน (ไม่ควรเกิด แต่กันไว้)
    const seen = new Set<number>();
    months = [];
    for (const { year, month } of sortedData) {
      const key = monthKey({ year, month });
      if (seen.has(key)) continue;
      seen.add(key);
      months.push({ year, month });
    }
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
