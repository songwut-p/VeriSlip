export type DocType = "bank_slip" | "stock_confirmation" | "unknown";

// parsed เป็น dict ที่ฟิลด์ไม่ตายตัว (bank_slip กับ stock_confirmation
// มีฟิลด์ไม่เหมือนกัน) -- ค่าเป็น string/number/null เท่านั้น
export type ParsedFields = Record<string, string | number | null>;

export interface UploadSlipResponse {
  filename: string;
  doc_type: DocType;
  ocr_text: string;
  parsed: ParsedFields;
}
