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

// income_expense (13 ก.ย. 2026): ยอดรวมแยกรายรับ/รายจ่าย/สุทธิ สำหรับการ์ด
// ยอดสุทธิใหม่บน Dashboard -- คำนวณจาก transaction_type ที่ผู้ใช้เลือกเองใน
// ฟอร์ม human-in-the-loop ตอนบันทึกสลิป (แถวเก่าที่ transaction_type เป็น
// NULL จะไม่ถูกนับเข้า income/expense เลย ไม่ใช่ถูกเดาเข้าฝั่งใดฝั่งหนึ่ง)
export interface IncomeExpenseSummary {
  income: number;
  expense: number;
  net: number;
}

// ส่วนอื่นของ response (กราฟ/รายการล่าสุด) จะเพิ่ม type ตอนทำขั้นถัดไป
// ตอนนี้ type แค่ที่ใช้จริง (summary + income_expense) พอ
export interface DashboardSummaryResponse {
  summary: DashboardSummary;
  trend_by_month_bank_slip: MonthlyTrend[];
  recent_slips: RecentSlip[];
  income_expense: IncomeExpenseSummary;
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
