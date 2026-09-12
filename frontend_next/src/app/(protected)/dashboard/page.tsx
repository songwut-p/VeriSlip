"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { apiFetch, ApiRequestError } from "@/lib/api";
import type { DashboardSummaryResponse, RecentSlip } from "@/types/dashboard-types";
import { MonthlyCountChart } from "@/components/dashboard/MonthlyCountChart";
import { RecentSlipsList } from "@/components/dashboard/RecentSlipsList";

export default function DashboardPage() {
  const { token } = useAuth();
  const [data, setData] = useState<DashboardSummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<RecentSlip[] | null>(null);
  const [isSearching, setIsSearching] = useState(false);

  function fetchSummary() {
    if (!token) return;
    setIsLoading(true);
    apiFetch<DashboardSummaryResponse>("/dashboard/summary", { token })
      .then(setData)
      .catch((err) => {
        setError(err instanceof ApiRequestError ? err.message : "โหลดข้อมูลไม่สำเร็จ");
      })
      .finally(() => setIsLoading(false));
  }

  useEffect(() => {
    fetchSummary();
  }, [token]);

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
        fetchSummary();
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

  if (isLoading) {
    return <div className="p-6 text-text-primary">กำลังโหลด...</div>;
  }

  if (error) {
    return (
      <div className="m-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {error}
      </div>
    );
  }

  if (!data) return null;

  const { summary } = data;

  return (
    <div className="p-6">
      <h1 className="mb-6 text-xl font-semibold text-text-primary">แดชบอร์ด</h1>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <SummaryCard label="ทั้งหมด" value={summary.total} color="blue" />
        <SummaryCard label="สมบูรณ์" value={summary.complete} color="green" />
        <SummaryCard label="มีปัญหา" value={summary.has_issue} color="red" />
      </div>

      <div className="mt-8">
        <h2 className="mb-4 text-lg font-medium text-text-primary">ยอดเงินรวมต่อเดือน</h2>
        <MonthlyCountChart data={data.trend_by_month_bank_slip} />
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
          className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm"
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
    </div>
  );
}

function SummaryCard({
  label,
  value,
  color,
}: {
  label: string;
  value: number;
  color: "blue" | "green" | "red";
}) {
  const colorClasses = {
    blue: "border-blue-200 bg-blue-50 text-blue-700",
    green: "border-green-200 bg-green-50 text-green-700",
    red: "border-red-200 bg-red-50 text-red-700",
  }[color];

  return (
    <div className={`rounded-xl border p-5 ${colorClasses}`}>
      <p className="text-sm">{label}</p>
      <p className="mt-1 text-3xl font-semibold">{value.toLocaleString("th-TH")}</p>
    </div>
  );
}