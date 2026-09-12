"use client";

import { useState, useEffect } from "react";
import { apiFetch, ApiRequestError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { FIELD_LABELS, NUMERIC_FIELDS } from "@/lib/constants";
import {
  prepareDisplayFields, getIssueFields, findSuspiciousNameFields,
} from "@/lib/slipFields";
import type { UploadSlipResponse, ParsedFields } from "@/types/slip";

const DOC_TYPE_LABELS: Record<string, string> = {
  bank_slip: "สลิปโอนเงิน",
  stock_confirmation: "คำสั่งซื้อหุ้น",
  unknown: "ไม่ทราบประเภท",
};

interface SaveSlipResponse {
  filename: string;
  status: string;
  db_row: { id: number; [key: string]: unknown };
}

// เดิมคือ UploadPage ทั้งหน้า -- ตอนนี้แยกออกมาเป็น component
// รับ "ไฟล์ที่เลือกไว้แล้ว" เป็น prop แทนที่จะมี <input> ของตัวเอง
// เนื้อใน (OCR/แก้ฟอร์ม/บันทึก) ไม่ถูกแก้แม้แต่บรรทัดเดียว
export default function SingleUploadFlow({ file }: { file: File }) {
  const { token } = useAuth();
  const [previewUrl] = useState<string>(() => URL.createObjectURL(file));
  const [result, setResult] = useState<UploadSlipResponse | null>(null);
  const [editedValues, setEditedValues] = useState<Record<string, string>>({});
  const [baselineValues, setBaselineValues] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);

  // เดิมทำงานตอน onChange ของ <input> -- ตอนนี้ทำตอน component นี้ mount
  // แทน เพราะพ่อแม่ (หน้ารวม) เลือกไฟล์มาให้ก่อนแล้วถึงสร้าง component นี้
  useEffect(() => {
    const runOcr = async () => {
      setIsLoading(true);
      const formData = new FormData();
      formData.append("file", file);
      try {
        const data = await apiFetch<UploadSlipResponse>("/upload-slip", {
          method: "POST",
          body: formData,
          token,
        });
        setResult(data);
        const displayFields = prepareDisplayFields(data.parsed);
        const initial: Record<string, string> = {};
        for (const [key, value] of Object.entries(displayFields)) {
          initial[key] = value === null ? "" : String(value);
        }
        setEditedValues(initial);
        setBaselineValues(initial);
      } catch (err) {
        setError(err instanceof ApiRequestError ? err.message : "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้");
      } finally {
        setIsLoading(false);
      }
    };
    runOcr();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ตั้งใจรันแค่ครั้งเดียวตอน mount ต่อไฟล์
  }, []);

  const handleSave = async () => {
    if (!result) return;

    const errors: string[] = [];
    for (const [key, value] of Object.entries(editedValues)) {
      if (value.trim() && NUMERIC_FIELDS.has(key) && Number.isNaN(Number(value))) {
        errors.push(`'${FIELD_LABELS[key] ?? key}' ต้องเป็นตัวเลข (ได้รับ: ${value})`);
      }
    }
    if (errors.length > 0) {
      setValidationErrors(errors);
      return;
    }
    setValidationErrors([]);

    const finalParsed: ParsedFields = { ...result.parsed };
    let editedAny = false;
    for (const [key, value] of Object.entries(editedValues)) {
      if (value !== (baselineValues[key] ?? "")) editedAny = true;
      if (value.trim() === "") {
        finalParsed[key] = null;
      } else if (NUMERIC_FIELDS.has(key)) {
        finalParsed[key] = Number(value);
      } else {
        finalParsed[key] = value;
      }
    }

    setIsSaving(true);
    setError(null);
    try {
      const saveResult = await apiFetch<SaveSlipResponse>("/save-slip", {
        method: "POST",
        token,
        body: JSON.stringify({
          filename: result.filename,
          doc_type: result.doc_type,
          parsed: finalParsed,
          ocr_text: result.ocr_text,
          extraction_flag: editedAny ? "user_edited" : "ai_extract_100",
        }),
      });

      const imageForm = new FormData();
      imageForm.append("file", file);
      await apiFetch(`/slips/${saveResult.db_row.id}/image`, {
        method: "POST",
        token,
        body: imageForm,
      });

      setSaveSuccess(true);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "บันทึกไม่สำเร็จ เชื่อมต่อเซิร์ฟเวอร์ไม่ได้");
    } finally {
      setIsSaving(false);
    }
  };

  const displayFields = result ? prepareDisplayFields(result.parsed) : {};
  const issueFields = result ? getIssueFields(result.parsed) : {};
  const suspiciousNameFields = result ? findSuspiciousNameFields(displayFields) : [];

  return (
    <div>
      {isLoading && <p className="text-text-primary">กำลังอ่านไฟล์ด้วย OCR...</p>}

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {saveSuccess && (
        <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
          ✅ บันทึกสำเร็จแล้ว
        </div>
      )}

      {result && (
        <>
          {suspiciousNameFields.length > 0 ? (
            <div className="mb-4 rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-700">
              ⚠️ ตรวจพบข้อความสุ่มเสี่ยง: โปรดตรวจสอบ {suspiciousNameFields.join(" และ ")} (มีตัวเลขนำหน้า)
            </div>
          ) : Object.keys(issueFields).length > 0 ? (
            <div className="mb-4 rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-700">
              ⚠️ ตรวจพบจุดที่ AI อ่านไม่มั่นใจ {Object.keys(issueFields).length} จุด — โปรดตรวจสอบข้อมูลก่อนบันทึก
              (ตรวจพบว่าเป็น: {DOC_TYPE_LABELS[result.doc_type] ?? result.doc_type})
            </div>
          ) : (
            <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
              ✅ อ่านไฟล์สำเร็จ — ตรวจพบว่าเป็น: {DOC_TYPE_LABELS[result.doc_type] ?? result.doc_type}
            </div>
          )}

          <div className="flex gap-6">
            <div className="w-2/5 rounded-xl border border-border-gray bg-card-bg p-4">
              <p className="mb-2 font-medium text-text-primary">🖼️ รูปต้นฉบับ</p>
              {/* eslint-disable-next-line @next/next/no-img-element -- blob URL ใช้ next/image ไม่ได้ */}
              <img src={previewUrl} alt="สลิปต้นฉบับ" className="w-full rounded-lg" />
            </div>

            <div className="w-3/5 rounded-xl border border-border-gray bg-card-bg p-4">
              <p className="mb-4 font-medium text-text-primary">📝 ตรวจสอบและแก้ไขข้อมูล</p>
              {Object.keys(displayFields).map((key) => (
                <div key={key} className="mb-4">
                  <label className="mb-1 block text-sm text-text-primary">
                    {FIELD_LABELS[key] ?? key}
                  </label>
                  <input
                    className="w-full rounded-lg border border-border-gray px-3 py-2 outline-none focus:border-emerald"
                    value={editedValues[key] ?? ""}
                    onChange={(e) =>
                      setEditedValues((prev) => ({ ...prev, [key]: e.target.value }))
                    }
                  />
                </div>
              ))}

              {validationErrors.length > 0 && (
                <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {validationErrors.map((msg) => (
                    <div key={msg}>{msg}</div>
                  ))}
                </div>
              )}

              <button
                onClick={handleSave}
                disabled={isSaving}
                className="w-full rounded-lg bg-emerald px-4 py-2 text-white transition-colors hover:bg-emerald-hover disabled:opacity-50"
              >
                {isSaving ? "กำลังบันทึก..." : "บันทึกลงฐานข้อมูล"}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
