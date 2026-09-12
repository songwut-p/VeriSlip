export interface DocTypeIssueCount {
  has_issue: number;
  total: number;
}

export interface DashboardSummary {
  total: number;
  complete: number;
  has_issue: number;
  by_doc_type: Record<string, number>;
  issues_by_doc_type: Record<string, DocTypeIssueCount>;
}

// ส่วนอื่นของ response (กราฟ/รายการล่าสุด) จะเพิ่ม type ตอนทำขั้นถัดไป
// ตอนนี้ type แค่ที่ใช้จริง (summary) พอ
export interface DashboardSummaryResponse {
  summary: DashboardSummary;
  trend_by_month_bank_slip: MonthlyTrend[];
  recent_slips: RecentSlip[];
  [key: string]: unknown;
}

export interface MonthlyTrend {
  year: number;
  month: number;
  count: number;
  total_amount: number;
}

export interface RecentSlip {
  id: number;
  doc_type: string;
  filename: string;
  image_path: string;
  datetime_year: number | null;
  datetime_month: number | null;
  datetime_day: number | null;
  amount: number;
  currency: string;
  bank_name: string | null;
  sender_name: string | null;
  recipient_name: string | null;
  source_app: string | null;
  has_issue: number;
}
