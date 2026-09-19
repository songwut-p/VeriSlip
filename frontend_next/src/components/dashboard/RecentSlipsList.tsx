"use client";

import { useEffect, useRef, useState } from "react";
import type { RecentSlip } from "@/types/dashboard-types";
import ConfirmDialog from "@/components/ConfirmDialog";

function formatDate(slip: RecentSlip): string {
  if (!slip.datetime_year || !slip.datetime_month || !slip.datetime_day) {
    return "ไม่ระบุวันที่";
  }
  const date = new Date(
    slip.datetime_year,
    slip.datetime_month - 1,
    slip.datetime_day,
  );
  return new Intl.DateTimeFormat("th-TH-u-ca-gregory", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

export function RecentSlipsList({
  slips,
  onDelete,
  onDownload,
}: {
  slips: RecentSlip[];
  onDelete: (slipId: number) => void | Promise<void>;
  onDownload: (slipId: number, filename: string) => void;
}) {
  // ต้องอยู่เหนือ early return ด้านล่างเสมอ (กฎ hook order)
  const [pendingDelete, setPendingDelete] = useState<RecentSlip | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  async function handleConfirmDelete() {
    if (!pendingDelete) return;
    setIsDeleting(true);
    try {
      await onDelete(pendingDelete.id);
    } finally {
      setIsDeleting(false);
      shouldRefocus.current = true;
      setPendingDelete(null);
    }
  }

  const recent = slips.slice(0, 5);

  const listRef = useRef<HTMLDivElement>(null);
  // true = dialog เพิ่งปิดหลังพยายามลบ (ไว้แยกออกจากตอนโหลดหน้าครั้งแรก/กดยกเลิก)
  const shouldRefocus = useRef(false);

  useEffect(() => {
    if (pendingDelete !== null || !shouldRefocus.current) return;
    shouldRefocus.current = false;
    // ถ้าโฟกัสหลุดไป body แปลว่าปุ่มลบเดิมหายไปแล้วจริง (ลบสำเร็จ)
    // ถ้าลบล้มเหลว ปุ่มเดิมยังอยู่และ ConfirmDialog คืนโฟกัสให้แล้ว จึงไม่ต้องทำอะไร
    if (document.activeElement === document.body) {
      listRef.current?.focus();
    }
  }, [pendingDelete]);

  if (recent.length === 0) {
    return (
      <div
        ref={listRef}
        tabIndex={-1}
        className="text-sm text-text-secondary focus:outline-none"
      >
        ยังไม่มีรายการ
      </div>
    );
  }

  return (
    <>
      <div
        ref={listRef}
        tabIndex={-1}
        className="divide-y divide-border-input focus:outline-none"
      >
        {recent.map((slip) => (
          <div
            key={slip.id}
            // group (16 ก.ย. 2026): เปิดใช้ hover/focus reveal ของปุ่ม action --
            // border-l-4 border-transparent ไว้ล่วงหน้าเสมอ (ไม่ใช่แค่ตอน hover)
            // กัน layout shift ตอนเส้นซ้ายโผล่ขึ้นมา (ความกว้างคงที่ แค่เปลี่ยนสี)
            className="group flex items-center justify-between border-l-4 border-transparent px-4 py-3 transition-colors hover:border-emerald hover:bg-soft-green-bg focus-within:border-emerald focus-within:bg-soft-green-bg"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-text-primary">
                {slip.sender_name ?? "ไม่ระบุผู้โอน"} →{" "}
                {slip.recipient_name ?? "ไม่ระบุผู้รับ"}
              </p>
              <p className="text-xs text-text-secondary">
                {formatDate(slip)} ·{" "}
                {slip.bank_name ?? slip.source_app ?? "ไม่ระบุธนาคาร"}
              </p>
            </div>

            <div className="flex items-center gap-4">
              <div className="text-right">
                <p className="text-sm font-semibold text-text-primary">
                  {slip.amount.toLocaleString("th-TH")} บาท
                </p>
                {slip.has_issue === 1 ? (
                  <span className="mt-1 inline-block rounded-full bg-danger-bg px-2 py-0.5 text-xs font-medium text-danger">
                    ควรตรวจสอบ
                  </span>
                ) : (
                  <span className="mt-1 inline-block rounded-full bg-soft-green-bg px-2 py-0.5 text-xs font-medium text-emerald">
                    สมบูรณ์
                  </span>
                )}
              </div>

              {/* ปุ่ม action (16 ก.ย. 2026): ซ่อนด้วย opacity-0 ปกติ โผล่ตอน
                  hover ทั้งแถว (group-hover) หรือตอน focus อยู่ในแถวนั้นผ่าน
                  keyboard (group-focus-within) -- ปุ่มยังอยู่ใน DOM เสมอ
                  (แค่โปร่งใส) ไม่ใช่ display:none เพื่อให้ Tab ไล่ถึงได้ */}
              <div className="flex items-center gap-2 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
                <button
                  onClick={() => onDownload(slip.id, slip.filename)}
                  className="rounded-lg border border-border-input px-3 py-1.5 text-xs text-text-primary hover:bg-page-bg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
                >
                  ดาวน์โหลด
                </button>

                <button
                  onClick={() => setPendingDelete(slip)}
                  className="rounded-lg border border-danger/30 px-3 py-1.5 text-xs text-danger hover:bg-danger-bg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
                >
                  ลบ
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="ลบสลิปนี้?"
        message="การลบไม่สามารถย้อนกลับได้"
        itemName={pendingDelete?.filename}
        confirmLabel="ลบ"
        isBusy={isDeleting}
        onConfirm={handleConfirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </>
  );
}
