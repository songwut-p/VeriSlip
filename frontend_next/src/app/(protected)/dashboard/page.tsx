"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { apiFetch, ApiRequestError } from "@/lib/api";
import type { DashboardSummaryResponse, RecentSlip } from "@/types/dashboard-types";
import { MonthlyCountChart } from "@/components/dashboard/MonthlyCountChart";
import { RecentSlipsList } from "@/components/dashboard/RecentSlipsList";
import { SummaryCards } from "@/components/dashboard/SummaryCards";
import DateRangeFilter, { type DateRange } from "@/components/dashboard/DateRangeFilter";

export default function DashboardPage() {
  const { token } = useAuth();
  const [data, setData] = useState<DashboardSummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<RecentSlip[] | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  // dateRange (13 ก.ย. 2026): มาจาก DateRangeFilter (preset หรือ manual --
  // ดูตรรกะ "ใครกดหลังสุดชนะ" ใน DateRangeFilter.tsx เอง) คุมทั้งการ์ดสรุป
  // และกราฟรายเดือน เพราะทั้งคู่มาจาก endpoint /dashboard/summary เดียวกัน
  const [dateRange, setDateRange] = useState<DateRange>({});

  function fetchSummary(range: DateRange) {
    if (!token) return;
    setIsLoading(true);
    const params = new URLSearchParams();
    if (range.start_date) params.set("start_date", range.start_date);
    if (range.end_date) params.set("end_date", range.end_date);
    const query = params.toString();
    apiFetch<DashboardSummaryResponse>(
      `/dashboard/summary${query ? `?${query}` : ""}`,
      { token }
    )
      .then(setData)
      .catch((err) => {
        setError(err instanceof ApiRequestError ? err.message : "โหลดข้อมูลไม่สำเร็จ");
      })
      .finally(() => setIsLoading(false));
  }

  useEffect(() => {
    fetchSummary(dateRange);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ตั้งใจ trigger เฉพาะตอน token หรือ dateRange เปลี่ยน
  }, [token, dateRange]);

  function handleSearch() {
    if (!token || !searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    setIsSearching(true);
    apiFetch<{ results: RecentSlip[] }>(
      `/dashboard/search?query=${encodeURIComponent(searchQuery)}`,
      { token }
    )
      .then((res) => setSearchResults(res.results))
      .catch(() => setSearchResults([]))
      .finally(() => setIsSearching(false));
  }

  function handleDelete(slipId: number) {
    if (!token) return;
    if (!window.confirm("ยืนยันการลบรายการนี้?")) return;

    apiFetch("/delete-slip", {
      method: "POST",
      token,
      body: JSON.stringify({ slip_id: slipId }),
    })
      .then(() => {
        setSearchResults(null);
        setSearchQuery("");
        fetchSummary(dateRange);
      })
      .catch((err) => {
        alert(err instanceof ApiRequestError ? err.message : "ลบไม่สำเร็จ");
      });
  }

  async function handleDownload(slipId: number, filename: string) {
    if (!token) return;
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"}/slips/${slipId}/image`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (!res.ok) throw new Error("ดาวน์โหลดไม่สำเร็จ");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert("ดาวน์โหลดรูปไม่สำเร็จ");
    }
  }

  return (
    <div className="p-6">
      <h1 className="mb-6 text-xl font-semibold text-text-primary">แดชบอร์ด</h1>

      {/* DateRangeFilter ต้องอยู่นอกเงื่อนไข isLoading/data เสมอ (13 ก.ย. 2026,
          บั๊กที่เจอ) -- เดิม isLoading ทำให้ทั้งหน้า early-return เป็นข้อความ
          "กำลังโหลด..." แทนที่ ซึ่ง unmount ทั้ง component tree รวมถึง
          DateRangeFilter ไปด้วย พอโหลดเสร็จ component ถูกสร้างใหม่ทั้งหมด
          ทำให้ state ภายใน (activePreset/manualStart/manualEnd) รีเซ็ตกลับ
          ค่าเริ่มต้นทุกครั้งที่กรองใหม่ -- ทั้งปุ่ม preset ไม่ค้างสีที่เลือก
          และช่อง manual date เหมือนกดไม่ติด ทั้งที่ค่าจริงถูกส่งไป backend
          ถูกต้องอยู่แล้ว (แค่ UI ไม่สะท้อนสถานะให้เห็น) */}
      <DateRangeFilter onChange={setDateRange} />

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {isLoading && !data && (
        <div className="text-text-primary">กำลังโหลด...</div>
      )}

      {data && (
        <>
          <SummaryCards summary={data.summary} incomeExpense={data.income_expense} />

          <div className="mt-8">
            <h2 className="mb-4 text-lg font-medium text-text-primary">ยอดเงินรวมต่อเดือน</h2>
            <MonthlyCountChart
              data={data.trend_by_month_bank_slip}
              startDate={dateRange.start_date}
              endDate={dateRange.end_date}
            />
          </div>

          <div className="mt-8 flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => {
                const value = e.target.value;
                setSearchQuery(value);
                if (value.trim() === "") {
                  setSearchResults(null);
                }
              }}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="ค้นหาจากชื่อไฟล์ ผู้โอน ผู้รับ หรือธนาคาร"
              className="flex-1 rounded-lg border border-border-input px-3 py-2 text-sm text-text-primary"
            />
            <button
              onClick={handleSearch}
              disabled={isSearching}
              className="rounded-lg bg-emerald-800 px-4 py-2 text-sm text-white"
            >
              {isSearching ? "กำลังค้นหา..." : "ค้นหา"}
            </button>
          </div>

          <div className="mt-4">
            <h2 className="mb-4 text-lg font-medium text-text-primary">
              {searchResults ? "ผลการค้นหา" : "รายการล่าสุด"}
            </h2>
            <RecentSlipsList
              slips={searchResults ?? data.recent_slips}
              onDelete={handleDelete}
              onDownload={handleDownload}
            />
          </div>
        </>
      )}
    </div>
  );
}
