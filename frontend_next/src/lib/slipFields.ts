import type { ParsedFields } from "@/types/slip";
import { INTERNAL_FIELDS, NAME_FIELDS, FIELD_LABELS } from "./constants";

// ตัดฟิลด์ภายใน (_issue, INTERNAL_FIELDS, currency) ออกจาก dict ที่จะ
// เอาไปโชว์เป็นฟอร์มแก้ไข -- เทียบเท่า _prepare_display_fields() เดิม
export function prepareDisplayFields(parsed: ParsedFields): ParsedFields {
  const result: ParsedFields = {};
  for (const [key, value] of Object.entries(parsed)) {
    if (key.endsWith("_issue")) continue;
    if (INTERNAL_FIELDS.has(key)) continue;
    if (key === "currency") continue;
    result[key] = value;
  }
  return result;
}

// ดึงเฉพาะฟิลด์ลงท้าย "_issue" ที่ parser ใส่มาตอนอ่านฟิลด์นั้นไม่ได้/
// ไม่มั่นใจ -- เทียบเท่า _get_issue_fields() เดิม
export function getIssueFields(parsed: ParsedFields): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(parsed)) {
    if (key.endsWith("_issue") && value) {
      result[key] = String(value);
    }
  }
  return result;
}

// เช็คฟิลด์ชื่อคนว่ามีตัวเลขนำหน้าปนมาไหม -- คืนเป็น label ภาษาไทยของ
// ฟิลด์ที่มีปัญหา -- เทียบเท่า _find_suspicious_name_fields() เดิม
export function findSuspiciousNameFields(displayFields: ParsedFields): string[] {
  const suspicious: string[] = [];
  for (const key of NAME_FIELDS) {
    const value = displayFields[key];
    if (value && /^\s*\d/.test(String(value))) {
      suspicious.push(FIELD_LABELS[key] ?? key);
    }
  }
  return suspicious;
}
