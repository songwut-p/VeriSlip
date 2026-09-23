"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { apiFetch, ApiRequestError } from "@/lib/api";
import type { DashboardSummaryResponse, RecentSlip } from "@/types/dashboard-types";
import { MonthlyCountChart } from "@/components/dashboard/MonthlyCountChart";
import { RecentSlipsList } from "@/components/dashboard/RecentSlipsList";
import { SummaryCards } from "@/components/dashboard/SummaryCards";
import DateRangeFilter, { type DateRange, DEFAULT_PRESET, presetToRange } from "@/components/dashboard/DateRangeFilter";
import AskTrigger from "@/components/ask/AskTrigger";

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
  const [dateRange, setDateRange] = useState<DateRange>(() => presetToRange(DEFAULT_PRESET.months));

  // คืน promise (18 ก.ย. 2026) เพื่อให้ handleDelete รอ refetch เสร็จได้
  // -- ConfirmDialog จะได้ปิดพร้อมกับที่รายการอัปเดตแล้ว ไม่ปิดก่อนแล้วแถวค้าง
  function fetchSummary(range: DateRange) {
    if (!token) return;
    // ไม่ setState ทันทีตรงนี้ (23 ก.ย. 2026) -- ฟังก์ชันนี้ถูกเรียกใน useEffect
    // กฎ react-hooks/set-state-in-effect ห้าม setState แบบ synchronous ใน effect
    // (เดิมมี setIsLoading(true) ซึ่งไม่จำเป็น: isLoading ใช้แค่โชว์ "กำลังโหลด..."
    // ตอน !data ครั้งแรก และค่าเริ่มต้นเป็น true อยู่แล้ว)
    const params = new URLSearchParams();
    if (range.start_date) params.set("start_date", range.start_date);
    if (range.end_date) params.set("end_date", range.end_date);
    const query = params.toString();
    return apiFetch<DashboardSummaryResponse>(
      `/dashboard/summary${query ? `?${query}` : ""}`,
      { token }
    )
      // ล้าง error ตอนโหลดสำเร็จ (23 ก.ย. 2026) -- เดิมไม่มีจุดไหน set กลับเป็น
      // null เลย กล่องแดงจึงค้างถาวรแม้ backend กลับมาแล้ว; อยู่ใน callback
      // หลัง fetch จึงไม่ผิดกฎ set-state-in-effect
      .then((res) => {
        setData(res);
        setError(null);
      })
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

  // เอา window.confirm ออก (18 ก.ย. 2026): การยืนยันย้ายไปอยู่ที่ ConfirmDialog
  // ใน RecentSlipsList แล้ว ฟังก์ชันนี้จึงลบทันทีที่ถูกเรียก
  // และเป็น async เพื่อให้ RecentSlipsList รอจนลบ + refetch เสร็จ (isBusy)
  async function handleDelete(slipId: number) {
    if (!token) return;

    try {
      await apiFetch("/delete-slip", {
        method: "POST",
        token,
        body: JSON.stringify({ slip_id: slipId }),
      });
      setSearchResults(null);
      setSearchQuery("");
      await fetchSummary(dateRange);
    } catch (err) {
      alert(err instanceof ApiRequestError ? err.message : "ลบไม่สำเร็จ");
    }
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

      {/* token danger (23 ก.ย. 2026): แทน red-200/red-50/red-700 ฮาร์ดโค้ด
          ขอบ danger/30 ตรงกับปุ่ม "ลบ" ใน RecentSlipsList */}
      {error && (
        <div className="mb-4 rounded-lg border border-danger/30 bg-danger-bg px-4 py-3 text-sm text-danger">
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

          {/* การ์ดใหญ่ (16 ก.ย. 2026): ห่อ search + รายการล่าสุด ให้เป็น
              การ์ดเดียวกัน แทนที่จะเป็น 2 บล็อกลอยแยกกัน -- ตาม reference
              design ที่ดู ระยะห่างจัดที่การ์ดนี้แล้ว บล็อกข้างในเลยลด
              mt-8/mt-4 เดิมออก เหลือแค่ mt-4 ระหว่าง search กับ list */}
          <div className="mt-8 rounded-xl border border-border-gray bg-card-bg p-6">
            <div className="flex gap-2">
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
              {/* ปุ่มค้นหา (23 ก.ย. 2026): เดิม bg-emerald-800 เป็นสีจาก palette
                  ของ Tailwind เอง ไม่ใช่ token --color-emerald ของเรา สีเลย
                  ไม่ตรงกับปุ่มหลักอื่น และไม่มี hover/focus/disabled เลย */}
              <button
                onClick={handleSearch}
                disabled={isSearching}
                className="rounded-lg bg-emerald px-4 py-2 text-sm text-white hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring disabled:bg-disabled-bg disabled:text-disabled-text"
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
          </div>
        </>
      )}
      <AskTrigger />
    </div>
  );
}
