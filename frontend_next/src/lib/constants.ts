// ป้ายชื่อภาษาไทยของแต่ละฟิลด์ -- แทน FIELD_LABELS เดิมใน Streamlit
export const FIELD_LABELS: Record<string, string> = {
  bank_name: "ธนาคาร",
  recipient_bank: "ธนาคารผู้รับ",
  amount: "จำนวนเงิน (บาท)",
  sender_name: "ชื่อผู้โอน",
  sender_account: "เลขบัญชีผู้โอน",
  recipient_name: "ชื่อผู้รับ",
  recipient_account: "เลขบัญชีผู้รับ",
  transaction_id: "เลขที่รายการ",
  datetime_raw: "วันเวลาที่ทำรายการ",
};

// ฟิลด์ตัวเลข -- ต้อง validate ว่าเป็นตัวเลขก่อนบันทึก
export const NUMERIC_FIELDS = new Set(["amount"]);

// ฟิลด์ชื่อคน -- เช็คว่าขึ้นต้นด้วยตัวเลขไหม (สัญญาณ OCR อ่านหลุด)
export const NAME_FIELDS = new Set(["sender_name", "recipient_name"]);

// ฟิลด์ metadata ที่ไม่ใช่ข้อมูลสลิปจริง -- ไม่โชว์ในฟอร์มแก้ไข
export const INTERNAL_FIELDS = new Set(["datetime_parsed", "extraction_source"]);
