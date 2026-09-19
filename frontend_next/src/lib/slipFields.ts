import type { ParsedFields } from "@/types/slip";
import { INTERNAL_FIELDS, NAME_FIELDS, FIELD_LABELS, HIDDEN_FIELDS } from "./constants";

// ตัดฟิลด์ภายใน (_issue, INTERNAL_FIELDS, currency) ออกจาก dict ที่จะ
// เอาไปโชว์เป็นฟอร์มแก้ไข -- เทียบเท่า _prepare_display_fields() เดิม
export function prepareDisplayFields(parsed: ParsedFields): ParsedFields {
  const result: ParsedFields = {};
  for (const [key, value] of Object.entries(parsed)) {
    if (key.endsWith("_issue")) continue;
    if (INTERNAL_FIELDS.has(key)) continue;
    if (key === "currency") continue;
    if (HIDDEN_FIELDS.has(key)) continue;
    result[key] = value;
  }
  return result;
}

// ดึงเฉพาะฟิลด์ลงท้าย "_issue" ที่ parser ใส่มาตอนอ่านฟิลด์นั้นไม่ได้/
// ไม่มั่นใจ -- เทียบเท่า _get_issue_fields() เดิม
export function getIssueFields(parsed: ParsedFields): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(parsed)) {
    if (
      key.endsWith("_issue") &&
      value &&
      !HIDDEN_FIELDS.has(key.replace(/_issue$/, ""))
    ) {
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

// คำนำหน้าชื่อที่ต้องข้ามก่อนนับชื่อ/นามสกุล (นางสาว ต้องมาก่อน นาง)
const TITLE_PREFIX = /^\s*(นางสาว|นาง|นาย|น\.ส\.)\s+/;

// คำที่เหลืออักษรตัวเดียวจริง (ไม่นับจุดย่อ) -- ไม่ตัดสระ/วรรณยุกต์ออก
// เพื่อไม่ให้นามสกุลสั้นจริงอย่าง "ดี" โดนเตือนโดยไม่จำเป็น
function isSingleLetter(word: string): boolean {
  return Array.from(word.replace(/\./g, "")).length === 1;
}

export type ShortNamePart = "first" | "last";

// ตัดคำนำหน้า แล้วดูว่าชื่อ (คำแรก) หรือนามสกุล (คำสุดท้าย) เหลือตัวเดียวไหม
// ชื่อคำเดียว (เช่น "Shopee", "รหัสพร้อมเพย์") ข้ามไป ไม่เตือน
export function findShortNamePart(name: string): ShortNamePart | null {
  const words = name.replace(TITLE_PREFIX, "").trim().split(/\s+/).filter(Boolean);
  if (words.length < 2) return null;
  if (isSingleLetter(words[0])) return "first";
  if (isSingleLetter(words[words.length - 1])) return "last";
  return null;
}

export interface NameWarning {
  field: string;
  label: string;
  message: string;
}

// คำเตือนชื่อแบบนุ่ม ๆ คำนวณจากค่าปัจจุบันของช่อง -- ผู้ใช้เติมชื่อเต็มแล้วคำเตือนหายเอง
export function findNameWarnings(values: Record<string, unknown>): NameWarning[] {
  const warnings: NameWarning[] = [];
  for (const field of NAME_FIELDS) {
    const raw = values[field];
    if (!raw) continue;
    const part = findShortNamePart(String(raw));
    if (!part) continue;
    warnings.push({
      field,
      label: FIELD_LABELS[field] ?? field,
      message:
        part === "last"
          ? "ไม่แน่ใจนามสกุล เห็นแค่ตัวเดียว ลองเช็คอีกทีนะ"
          : "ไม่แน่ใจชื่อ เห็นแค่ตัวเดียว ลองเช็คอีกทีนะ",
    });
  }
  return warnings;
}

export interface WarningItem {
  field: string;
  label: string;
  message: string;
}

// คีย์ธง (ตัด _issue แล้ว) ที่ชื่อไม่ตรงกับคีย์ค่าในฟอร์ม: datetime_issue -> datetime_raw
const VALUE_KEY: Record<string, string> = { datetime: "datetime_raw" };

// ธงชื่อของ parser (ตั้งจาก detect_short_name_issue ที่เดียว) -- แบนเนอร์เลิกใช้
// แล้วตรวจชื่อจากค่าปัจจุบันของช่องแทน (findNameWarnings)
const NAME_ISSUE_KEYS = new Set(["sender_name_issue", "recipient_name_issue"]);
const ACCOUNT_FIELDS = ["sender_account", "recipient_account"];
// อักขระที่ไม่ควรอยู่ในเลขบัญชี (OCR อ่านหลุด เช่น %) -- ไม่รวม + - x * เพราะเลขบัญชี/เบอร์จริงมี
const BAD_ACCOUNT_CHARS = /[%$#@!^&~|\\<>?=]/;

// เดือนที่ยอมรับ: ไทยย่อครบรูป หรืออังกฤษ 3 ตัวแรก (เดียวกับที่ parser รู้จัก)
const THAI_MONTHS = new Set([
  "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
  "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
]);
const EN_MONTHS = new Set([
  "jan", "feb", "mar", "apr", "may", "jun",
  "jul", "aug", "sep", "oct", "nov", "dec",
]);
// รูปแบบ "วัน เดือน ปี เวลา" (ปี 2 หรือ 4 หลัก, คั่นด้วย , หรือ - ได้)
const DATETIME_PATTERN = /^\s*\d{1,2}\s+(\S+)\s+\d{2,4}\s*[,\-]?\s*\d{1,2}:\d{2}/;

// คืนข้อความเตือนเรื่องวันเวลา หรือ null ถ้าดูปกติ
export function findDatetimeWarning(raw: string): string | null {
  const text = raw.trim();
  if (!text) return "อ่านวันเวลาไม่ได้ ลองกรอกตามสลิปนะ";
  const m = DATETIME_PATTERN.exec(text);
  if (!m) return "อ่านวันเวลาได้ไม่ครบ ลองเช็คกับสลิปอีกทีนะ";
  const month = m[1].replace(/,$/, "");
  if (THAI_MONTHS.has(month) || EN_MONTHS.has(month.slice(0, 3).toLowerCase())) {
    return null;
  }
  return `อ่านเดือนไม่ชัด (ได้ "${month}") ลองเช็คกับสลิปอีกทีนะ`;
}

// รวมคำเตือนทุกแหล่งเป็นลิสต์เดียว -- คำนวณจากค่าปัจจุบัน (values) ไม่ใช่ค่า OCR เดิม
export function getWarningItems(
  parsed: ParsedFields,
  values: Record<string, unknown>,
): WarningItem[] {
  const items: WarningItem[] = [];

  // 1) ธงจาก parser (ไม่รวมธงชื่อ) -- ถ้าผู้ใช้แก้เป็นค่าใหม่ที่ไม่ว่าง ถือว่าจัดการแล้ว
  //    ถ้าล้างช่องจนว่าง คำเตือนยังอยู่
  for (const [key, message] of Object.entries(getIssueFields(parsed))) {
    if (NAME_ISSUE_KEYS.has(key)) continue;
    const field = key.replace(/_issue$/, "");
    const valueKey = VALUE_KEY[field] ?? field;
    const current = String(values[valueKey] ?? "").trim();
    const original = String(parsed[valueKey] ?? "").trim();
    if (current !== "" && current !== original) continue;
    items.push({ field: valueKey, label: FIELD_LABELS[valueKey] ?? valueKey, message });
  }

  // 2) ชื่อขึ้นต้นด้วยตัวเลข (สัญญาณ OCR อ่านหลุด)
  for (const field of NAME_FIELDS) {
    const raw = values[field];
    if (raw && /^\s*\d/.test(String(raw))) {
      items.push({
        field,
        label: FIELD_LABELS[field] ?? field,
        message: "ขึ้นต้นด้วยตัวเลข น่าจะอ่านคลาดเคลื่อน ลองเช็คอีกทีนะ",
      });
    }
  }

  // 3) ชื่อหรือนามสกุลเหลือตัวเดียว (ข้ามช่องที่โดนเตือนเรื่องตัวเลขไปแล้ว ไม่ให้ซ้ำ)
  const flagged = new Set(items.map((i) => i.field));
  for (const w of findNameWarnings(values)) {
    if (!flagged.has(w.field)) items.push(w);
  }

  // 4) ช่องที่ parser ไม่ได้ตั้งธง แต่ค่าดูผิดปกติ (ช่องโหว่ที่เจอจากสลิป K+ จริง)
  const flaggedNow = new Set(items.map((i) => i.field));

    // วันเวลาว่าง / อ่านไม่ครบ / เดือนอ่านไม่ออก (เฉพาะเอกสารที่มีช่องนี้ในฟอร์ม)
  if ("datetime_raw" in values && !flaggedNow.has("datetime_raw")) {
    const message = findDatetimeWarning(String(values.datetime_raw ?? ""));
    if (message) {
      items.push({
        field: "datetime_raw",
        label: FIELD_LABELS.datetime_raw ?? "datetime_raw",
        message,
      });
    }
  }

  // เลขบัญชีมีอักขระแปลก
  for (const field of ACCOUNT_FIELDS) {
    const raw = String(values[field] ?? "");
    if (BAD_ACCOUNT_CHARS.test(raw) && !flaggedNow.has(field)) {
      items.push({
        field,
        label: FIELD_LABELS[field] ?? field,
        message: "ไม่แน่ใจเลขบัญชี มีอักขระแปลก ๆ ลองเช็คอีกทีนะ",
      });
    }
  }

  return items;
}

// คีย์ธง (_issue) ของสลิปธนาคาร -> ช่องในฟอร์มที่ธงนั้นพูดถึง
// (ไม่รวม transaction_id_issue ที่ซ่อนช่องแล้ว)
const BANK_ISSUE_TO_FIELD: Record<string, string> = {
  bank_name_issue: "bank_name",
  amount_issue: "amount",
  sender_name_issue: "sender_name",
  sender_account_issue: "sender_account",
  recipient_name_issue: "recipient_name",
  recipient_account_issue: "recipient_account",
  datetime_issue: "datetime_raw",
};

// ธงที่ควรเก็บลง DB ตอนบันทึก = คำเตือนที่ยังเหลืออยู่ ณ ค่าสุดท้ายของช่อง
// ช่องที่ไม่มีคำเตือนแล้วได้ null (ล้างธงเก่าจาก OCR) ช่องที่ยังเตือนอยู่ได้ข้อความคำเตือนนั้น
export function getCurrentIssueFlags(
  parsed: ParsedFields,
  values: Record<string, unknown>,
): Record<string, string | null> {
  const messageByField = new Map(
    getWarningItems(parsed, values).map((w) => [w.field, w.message]),
  );
  const flags: Record<string, string | null> = {};
  for (const [issueKey, field] of Object.entries(BANK_ISSUE_TO_FIELD)) {
    flags[issueKey] = messageByField.get(field) ?? null;
  }
  return flags;
}

