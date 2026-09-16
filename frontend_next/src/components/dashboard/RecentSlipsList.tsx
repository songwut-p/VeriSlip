"use client";

import type { RecentSlip } from "@/types/dashboard-types";

function formatDate(slip: RecentSlip): string {
  if (!slip.datetime_year || !slip.datetime_month || !slip.datetime_day) {
    return "ไม่ระบุวันที่";
  }
  const d = String(slip.datetime_day).padStart(2, "0");
  const m = String(slip.datetime_month).padStart(2, "0");
  return `${d}/${m}/${slip.datetime_year}`;
}

export function RecentSlipsList({
  slips,
  onDelete,
  onDownload,
}: {
  slips: RecentSlip[];
  onDelete: (slipId: number) => void;
  onDownload: (slipId: number, filename: string) => void;
}) {
  const recent = slips.slice(0, 5);

  if (recent.length === 0) {
    return <p className="text-sm text-text-secondary">ยังไม่มีรายการ</p>;
  }

  return (
    <div className="divide-y divide-border-input rounded-xl border border-border-gray">
      {recent.map((slip) => (
        <div
          key={slip.id}
          className="flex items-center justify-between px-4 py-3"
        >
          <div>
            <p className="text-sm font-medium text-text-primary">
              {slip.sender_name ?? "ไม่ระบุผู้โอน"} → {slip.recipient_name ?? "ไม่ระบุผู้รับ"}
            </p>
            <p className="text-xs text-text-secondary">
              {formatDate(slip)} · {slip.bank_name ?? slip.source_app ?? "ไม่ระบุธนาคาร"}
            </p>
          </div>

          <div className="flex items-center gap-4">
            <div className="text-right">
              <p className="text-sm font-semibold text-text-primary">
                {slip.amount.toLocaleString("th-TH")} บาท
              </p>
              {slip.has_issue === 1 ? (
                <span className="mt-1 inline-block rounded-full bg-red-50 px-2 py-0.5 text-xs font-medium text-red-600">
                  ควรตรวจสอบ
                </span>
                ) : (
                <span className="mt-1 inline-block rounded-full bg-soft-green-bg px-2 py-0.5 text-xs font-medium text-emerald">
                  สมบูรณ์
                </span>
              )}
            </div>

            <button
              onClick={() => onDownload(slip.id, slip.filename)}
              className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs text-text-primary hover:bg-gray-50"
            >
              ดาวน์โหลด
            </button>

            <button
              onClick={() => onDelete(slip.id)}
              className="rounded-lg border border-red-200 px-3 py-1.5 text-xs text-red-600 hover:bg-red-50"
            >
              ลบ
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}