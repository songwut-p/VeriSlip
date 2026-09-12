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

export function MonthlyCountChart({ data }: { data: MonthlyTrend[] }) {
  const currentYear = new Date().getFullYear();
  const chartData = THAI_MONTHS.map((label, index) => {
    const monthNumber = index + 1;
    const match = data.find(
      (item) => item.month === monthNumber && item.year === currentYear
    );
    return {
      label,
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
