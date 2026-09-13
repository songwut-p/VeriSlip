import type { DashboardSummary, IncomeExpenseSummary } from "@/types/dashboard-types";

function formatBaht(n: number): string {
  return n.toLocaleString("th-TH", { maximumFractionDigits: 0 });
}

// การ์ดยอดสุทธิ (13 ก.ย. 2026): ตัวเลขใหญ่ด้านบน = สุทธิ (รายรับ - รายจ่าย),
// 2 บรรทัดเล็กด้านล่าง = รายรับ/รายจ่ายแยกกัน -- แพทเทิร์นเดียวกับตัวอย่าง
// mockup ที่ตกลงกันไว้ (ตัวเลขใหญ่ + ยอดย่อย 2 อันข้างล่างในการ์ดเดียวกัน)
// label หัวข้อบนสุดเป็นค่าชั่วคราว "ยอดสุทธิ" -- รอคำตอบจากเพื่อนผู้ใช้ก่อน
// เปลี่ยนเป็นคำสุดท้าย
//
// แก้ตาม feedback 13 ก.ย. 2026 (UI polish รอบ 2):
// (1) แยกสัญลักษณ์ ฿ เป็น span ขนาดเล็กกว่าตัวเลข + เว้นระยะ (mr-1) --
//     เดิมตัวอักษร ฿ กับตัวเลขขนาดเท่ากันชิดติดกันจนดูขัดตา
// (2) สีรายจ่ายเปลี่ยนจาก red-600 (แดงสดทึบ) เป็น red-500 (มิวต์ลง) +
//     เติมเครื่องหมาย "-" นำหน้า ให้สื่อทิศทาง cash outflow ชัดเจนขึ้น
//     โดยไม่ไปแย่ง visual weight จากตัวเลขยอดสุทธิด้านบน
function NetAmountCard({ data }: { data: IncomeExpenseSummary }) {
  const isNegative = data.net < 0;
  return (
    <div className="rounded-xl border border-border-gray bg-card-bg p-5">
      {/* ไอคอน info + tooltip (13 ก.ย. 2026): กันเข้าใจผิดว่า "ยอดสุทธิ" คือ
          ยอดเงินจริงในบัญชีธนาคาร -- อธิบายว่าเป็นผลรวมจากสลิปที่บันทึกไว้
          ในระบบเท่านั้น ใช้ native title attribute (โฮเวอร์ค้างแล้วเบราว์เซอร์
          ขึ้น tooltip ให้เอง) ไม่ต้องเขียน state/JS เพิ่มเติม */}
      <p className="flex items-center gap-1 text-sm text-text-secondary">
        ยอดสุทธิ
        <span
          title="คำนวณจากยอดรายรับ/รายจ่ายของสลิปที่บันทึกไว้ในระบบเท่านั้น ไม่ใช่ยอดเงินจริงในบัญชีธนาคาร"
          className="inline-flex h-5 w-5 cursor-help items-center justify-center rounded-full border border-border-gray text-sm text-text-secondary"
        >
          ⓘ
        </span>
      </p>
      <p
        className={`mt-1 flex items-baseline text-3xl font-semibold ${
          isNegative ? "text-red-600" : "text-text-primary"
        }`}
      >
        <span className="mr-1 text-lg">{isNegative ? "-" : ""}฿</span>
        {formatBaht(Math.abs(data.net))}
      </p>
      <div className="mt-3 flex items-center justify-between border-t border-border-gray pt-3 text-sm">
        <div>
          <p className="text-text-secondary">รายรับ</p>
          <p className="mt-1 font-medium text-green-600">฿{formatBaht(data.income)}</p>
        </div>
        <div className="text-right">
          <p className="text-text-secondary">รายจ่าย</p>
          <p className="mt-1 font-medium text-red-500">-฿{formatBaht(data.expense)}</p>
        </div>
      </div>
    </div>
  );
}

function StatusCard({
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
      {/* text-4xl (13 ก.ย. 2026, แก้ตาม feedback) -- เดิม text-3xl ทำให้
          พื้นที่ขวา/ล่างของการ์ดดูโล่งเกินไป เพิ่มขนาดฟอนต์ช่วยให้บาลานซ์
          กับพื้นที่การ์ดดีขึ้นโดยไม่ต้องเปลี่ยนโครงสร้าง layout */}
      <p className="mt-1 text-4xl font-semibold">{value.toLocaleString("th-TH")}</p>
    </div>
  );
}

interface SummaryCardsProps {
  summary: DashboardSummary;
  incomeExpense: IncomeExpenseSummary;
}

// การ์ดยอดสุทธิเป็นการ์ดที่ 4 เพิ่มเข้ามา -- 3 การ์ดสถานะไฟล์เดิม
// (ทั้งหมด/สมบูรณ์/มีปัญหา) ยังอยู่ครบ ไม่ได้ถูกแทนที่
export function SummaryCards({ summary, incomeExpense }: SummaryCardsProps) {
  return (
    // การ์ดยอดสุทธิครอง 2 ช่อง (col-span-2) ให้กว้างกว่าการ์ดสถานะทั้ง 3
    // ใบ -- ตรงกับ mockup ตัวอย่างที่ตกลงกันไว้ (13 ก.ย. 2026, ทดลองตาม
    // คำขอ "ลองแบบตัวอย่างก่อน" -- ถ้าไม่ถูกใจ เปลี่ยน lg:col-span-2 กลับเป็น
    // lg:col-span-1 บนบรรทัดของ NetAmountCard ก็พอ ไม่ต้องแก้จุดอื่น)
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <NetAmountCard data={incomeExpense} />
      </div>
      <StatusCard label="ทั้งหมด" value={summary.total} color="blue" />
      <StatusCard label="สมบูรณ์" value={summary.complete} color="green" />
      <StatusCard label="มีปัญหา" value={summary.has_issue} color="red" />
    </div>
  );
}
