"use client";

import { useState, useEffect } from "react";
import { apiFetch, ApiRequestError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { FIELD_LABELS, NUMERIC_FIELDS } from "@/lib/constants";
import { prepareDisplayFields, getWarningItems, getCurrentIssueFlags } from "@/lib/slipFields";
import type { UploadSlipResponse, ParsedFields } from "@/types/slip";
import { Loader2 } from "lucide-react";
import ImageLightbox from "@/components/ImageLightbox";

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
//
// เอา prop onCancel ออก (23 ก.ย. 2026): ทางออกเดียวคือปุ่ม "ยกเลิก" บนแถบ
// "เปลี่ยนไฟล์" ใน upload/page.tsx (ถามยืนยันทุกครั้ง) -- ปุ่ม "ยกเลิก" ตอน
// โหลดกับปุ่ม "เลือกไฟล์ใหม่" ที่เคยอยู่ในนี้ซ้ำหน้าที่กัน จึงลบทิ้งทั้งคู่
//
// onQueueChange (23 ก.ย. 2026): แจ้งจำนวนไฟล์ที่เหลือให้หน้าแม่ แบบเดียวกับ
// MultiUploadFlow -- บันทึกสำเร็จแล้วส่ง 0 แถบด้านบนจะเปลี่ยนเป็น "ไม่มีไฟล์ในคิว"
export default function SingleUploadFlow({
  file,
  onQueueChange,
}: {
  file: File;
  onQueueChange?: (count: number) => void;
}) {
  const { token } = useAuth();
  const [previewUrl] = useState<string>(() => URL.createObjectURL(file));
  const [result, setResult] = useState<UploadSlipResponse | null>(null);
  const [editedValues, setEditedValues] = useState<Record<string, string>>({});
  const [baselineValues, setBaselineValues] = useState<Record<string, string>>({});
  // transaction_type (13 ก.ย. 2026): "income"/"expense" ที่ผู้ใช้เลือกเอง
  // ในฟอร์ม human-in-the-loop -- ไม่ใช่ field ที่มาจาก OCR/displayFields
  // เหมือนฟิลด์อื่น จึงแยก state ต่างหาก ไม่ผ่าน editedValues loop
  const [transactionType, setTransactionType] = useState<"income" | "expense" | "">("");
  const [error, setError] = useState<string | null>(null);
  // เริ่มเป็น true (23 ก.ย. 2026) -- component นี้ถูกสร้างมาเพื่อ OCR ทันที
  // ที่ mount อยู่แล้ว เดิม runOcr เรียก setIsLoading(true) ใน effect ซึ่งผิด
  // กฎ react-hooks/set-state-in-effect (ตัวเดียวกับที่แก้ใน dashboard)
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  // สรุปสลิปที่เพิ่งบันทึก (23 ก.ย. 2026) -- หลังบันทึกฟอร์มจะหายไป ผู้ใช้จะไม่
  // เห็นอีกว่าบันทึกค่าไหนไป จึงเก็บจำนวนเงิน/วันที่/ธนาคารจากค่าที่แก้ล่าสุด
  // ไว้โชว์ใน banner (multi ใช้แค่จำนวนไฟล์ เพราะสรุปทีละใบจะยาวเกิน)
  const [savedSummary, setSavedSummary] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  // (29 ก.ย. 2026) คลิกรูปสลิปแล้วขยายเต็มจอ -- รูปในกล่องซ้ายเล็กลงหลังจัดหน้าพอดีจอ
  const [isLightboxOpen, setIsLightboxOpen] = useState(false);

  // เดิมทำงานตอน onChange ของ <input> -- ตอนนี้ทำตอน component นี้ mount
  // แทน เพราะพ่อแม่ (หน้ารวม) เลือกไฟล์มาให้ก่อนแล้วถึงสร้าง component นี้
  useEffect(() => {
    // abort ตอน unmount (23 ก.ย. 2026): กด "ยกเลิก" บนแถบแล้ว component นี้
    // ถูกถอดออก -- เดิมคำขอ OCR วิ่งต่อจนจบทั้งที่ไม่มีใครรอผลแล้ว
    // controller เป็นตัวแปรในรอบ effect นี้เอง ไม่ต้องใช้ ref อีกแล้ว
    const controller = new AbortController();

    const runOcr = async () => {
      const formData = new FormData();
      formData.append("file", file);
      try {
        const data = await apiFetch<UploadSlipResponse>("/upload-slip", {
          method: "POST",
          body: formData,
          token,
          signal: controller.signal,
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
        // ถูก abort (ยกเลิก/unmount) -- ไม่ใช่ error จริง ไม่ต้องโชว์กล่องแดง
        if (err instanceof Error && err.name === "AbortError") return;
        setError(err instanceof ApiRequestError ? err.message : "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้");
      } finally {
        // เช็ค aborted ก่อน -- ตอน dev React StrictMode รัน effect 2 รอบ
        // (mount → cleanup → mount) รอบแรกโดน abort แล้วถ้ายัง set false
        // ตรงนี้ spinner จะหายทั้งที่รอบสองยังโหลดอยู่
        if (!controller.signal.aborted) setIsLoading(false);
      }
    };
    runOcr();

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSave = async () => {
    if (!result) return;

    const errors: string[] = [];
    // บังคับเลือกรายรับ/รายจ่ายก่อนบันทึกเสมอ (13 ก.ย. 2026) -- pattern
    // เดียวกับฟิลด์อื่นที่ห้ามว่าง เช็คก่อนเข้า loop ตัวเลขด้านล่าง
    if (!transactionType) {
      errors.push("กรุณาเลือกประเภทรายการ (รายรับ / รายจ่าย) ก่อนบันทึก");
    }
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

    if (result.doc_type === "bank_slip") {
      Object.assign(finalParsed, getCurrentIssueFlags(result.parsed, editedValues));
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
          transaction_type: transactionType,
        }),
      });

      const imageForm = new FormData();
      imageForm.append("file", file);
      await apiFetch(`/slips/${saveResult.db_row.id}/image`, {
        method: "POST",
        token,
        body: imageForm,
      });

      const amountText = editedValues.amount?.trim();
      const summaryParts = [
        amountText
          ? `${Number(amountText).toLocaleString("th-TH", { maximumFractionDigits: 2 })} บาท`
          : "",
        editedValues.datetime_raw?.trim() ?? "",
        editedValues.bank_name?.trim() ?? "",
      ].filter(Boolean);
      setSavedSummary(summaryParts.length > 0 ? summaryParts.join(" · ") : null);
      setSaveSuccess(true);
      onQueueChange?.(0);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "บันทึกไม่สำเร็จ เชื่อมต่อเซิร์ฟเวอร์ไม่ได้");
    } finally {
      setIsSaving(false);
    }
  };

  const displayFields = result ? prepareDisplayFields(result.parsed) : {};
  const warnings = result ? getWarningItems(result.parsed, editedValues) : [];

  return (
    // (29 ก.ย. 2026) จอ lg: โครงเดียวกับ MultiUploadFlow -- flow สูงเท่ากล่องที่
    // page.tsx ส่งมา ส่วนบน/ล่างสูงตามเนื้อหา (shrink-0) แถวรูป+ฟอร์มกินที่เหลือ
    // ลูกใน <>...</> ด้านล่างเป็น flex item ของ div นี้โดยตรง
    <div className="lg:flex lg:h-full lg:flex-col">
      {isLoading && (
        <div className="mb-4 flex shrink-0 items-center gap-3">
          <Loader2 className="animate-spin text-emerald" size={18} />
          <p className="text-text-primary">กำลังอ่านไฟล์ด้วย OCR...</p>
        </div>
      )}

      {/* (29 ก.ย. 2026) บนสุดโชว์เฉพาะ error ตอนยังไม่มีผล OCR (OCR พัง) --
          error ตอนบันทึกไม่สำเร็จย้ายไปโชว์เหนือปุ่มบันทึกด้านล่าง ให้อยู่ที่
          เดียวกับที่ผู้ใช้กด (เดิมอยู่บนสุด ส่วนปุ่มอยู่ล่าง อาจมองไม่เห็น) */}
      {error && !result && (
        <div className="mb-4 shrink-0 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      {saveSuccess && (
        <div className="mb-4 shrink-0 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
          ✅ บันทึกแล้ว{savedSummary ? `: ${savedSummary}` : ""}
        </div>
      )}

      {/* !saveSuccess (23 ก.ย. 2026): บันทึกสำเร็จแล้วซ่อน banner เตือน รูป และ
          ฟอร์มทั้งหมด เหลือแค่ banner สรุปด้านบน ให้เหมือน MultiUploadFlow หลัง
          บันทึกครบ -- เดิมทุกอย่างค้างอยู่และกดบันทึกซ้ำได้ ถ้าบันทึกไม่สำเร็จ
          saveSuccess ยังเป็น false ฟอร์มจึงยังอยู่ให้แก้แล้วกดใหม่ได้ */}
      {result && !saveSuccess && (
        <>
          {warnings.length > 0 ? (
            // (29 ก.ย. 2026) lg: จำกัดความสูง กันแถบเตือนยาวๆ ดันกล่องรูป/ฟอร์มจนเตี้ย
            <div className="mb-4 shrink-0 rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-700 lg:max-h-28 lg:overflow-y-auto">
              <p>
                ⚠️ ตรวจพบจุดที่ควรเช็ก {warnings.length} จุด (ตรวจพบว่าเป็น: {DOC_TYPE_LABELS[result.doc_type] ?? result.doc_type})
              </p>
              <ul className="mt-1 list-disc pl-5">
                {warnings.map((w) => (
                  <li key={w.field}>
                    <span className="font-medium">{w.label}:</span> {w.message}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="mb-4 shrink-0 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
              ✅ อ่านไฟล์สำเร็จ — ตรวจพบว่าเป็น: {DOC_TYPE_LABELS[result.doc_type] ?? result.doc_type}
            </div>
          )}

          {/* (29 ก.ย. 2026) lg: แถวนี้กินความสูงที่เหลือ (flex-1 min-h-0) และ
              ยืดสองกล่องให้สูงเท่ากัน (items-stretch) -- กล่องรูปย่อรูปให้เห็นทั้งใบ
              กล่องฟอร์มเลื่อนในตัวเอง */}
          <div className="flex items-start gap-6 lg:min-h-0 lg:flex-1 lg:items-stretch">
            <div className="w-2/5 rounded-xl border border-border-gray bg-card-bg p-4 lg:flex lg:min-h-0 lg:flex-col">
              <p className="mb-2 shrink-0 font-medium text-text-primary">
                🖼️ รูปต้นฉบับ{" "}
                <span className="text-xs font-normal text-text-secondary">(คลิกรูปเพื่อขยาย)</span>
              </p>
              {/* (29 ก.ย. 2026) ห่อรูปด้วย <button> ให้กดเปิดรูปขยายได้ทั้งเมาส์และคีย์บอร์ด
                  (Tab มาที่รูปแล้วกด Enter) -- lg: ปุ่มรับหน้าที่ flex-1 min-h-0 แทนรูป
                  ส่วนรูปข้างในเต็มความสูงปุ่ม (h-full) แล้วย่อให้พอดี (object-contain) */}
              <button
                type="button"
                onClick={() => setIsLightboxOpen(true)}
                aria-label="ขยายรูปสลิป"
                className="block w-full cursor-zoom-in rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring lg:min-h-0 lg:flex-1"
              >
                {/* eslint-disable-next-line @next/next/no-img-element -- blob URL ใช้ next/image ไม่ได้ */}
                <img
                  src={previewUrl}
                  alt="สลิปต้นฉบับ"
                  className="w-full rounded-lg lg:h-full lg:object-contain"
                />
              </button>
            </div>

            {/* sticky + max-h + overflow-y-auto (13 ก.ย. 2026): แก้จากรอบก่อน
                (max-h เฉยๆ ไม่พอ เพราะ flex row เดิม align-items:stretch ทำให้
                ความสูงทั้งแถวถูกกำหนดจากกล่องรูปที่สูงกว่าเสมอ ต่อให้กล่องฟอร์ม
                เองไม่ล้นก็ตาม -- หน้าเว็บเลย scroll รวมกันแทนที่จะแยกกล่อง)

                วิธีนี้: เปลี่ยน parent เป็น items-start (กล่องรูปไม่ถูกบังคับยืด
                ตามกล่องฟอร์มอีกต่อไป) แล้วให้กล่องฟอร์ม sticky top-4 -- ทำให้
                กล่องฟอร์ม "ลอยค้าง" อยู่ตำแหน่งเดิมของจอเสมอ ไม่ว่ากล่องรูปจะ
                ยาวแค่ไหน (หน้าเว็บยัง scroll ผ่านรูปได้ปกติ แต่กล่องฟอร์มไม่ขยับ
                ตาม) พร้อม scrollbar อิสระของตัวเองเมื่อเนื้อหาฟอร์มเกิน
                max-h ที่กำหนด

                (29 ก.ย. 2026) ข้างบนนี้ใช้กับจอเล็กกว่า lg เท่านั้นแล้ว -- จอ lg
                ยกเลิก sticky/max-h (lg:static lg:max-h-none) เพราะแถวแม่กำหนด
                ความสูงให้แล้ว */}
            <div className="w-3/5 sticky top-4 max-h-[calc(100vh-2rem)] overflow-y-auto scrollbar-hover-only rounded-xl border border-border-gray bg-card-bg p-4 lg:static lg:max-h-none lg:min-h-0">
              <p className="mb-4 font-medium text-text-primary">📝 ตรวจสอบและแก้ไขข้อมูล</p>

              {/* ประเภทรายการ (13 ก.ย. 2026): วางบนสุดของฟอร์ม แยกจากฟิลด์ที่
                  มาจาก OCR ให้ชัดเจนว่าเป็นการยืนยันของผู้ใช้เอง ไม่ใช่ค่าที่
                  AI อ่านได้ -- อยู่บนสุดเพื่อลดโอกาสข้ามไปโดยไม่ตั้งใจก่อนกด
                  บันทึก (บังคับเลือกจริงใน handleSave ด้านบนอยู่แล้ว)

                  แก้ตาม feedback 13 ก.ย. 2026 (UX polish):
                  (1) สีแยกจากปุ่ม Save ชัดเจน -- เขียว=รายรับ, แดง=รายจ่าย
                      (เดิมใช้ emerald เดียวกับปุ่ม Save ทำให้แยกไม่ออกว่า
                      อันไหนคือ action button อันไหนคือ state toggle)
                  (2) เพิ่ม spacing (mb-6 แทน mb-4, label เพิ่ม mb-2)
                  (3) ห่อด้วยกรอบ+พื้นหลังแยกต่างหาก ให้ดูเป็น widget ของ
                      ตัวเอง ไม่ใช่ฟิลด์ลอยปนกับฟิลด์ OCR ด้านล่าง */}
              <div className="mb-6 rounded-lg border border-border-gray bg-page-bg p-3">
                <label className="mb-2 block text-sm font-medium text-text-primary">ประเภทรายการ</label>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setTransactionType("income")}
                    className={`flex-1 rounded-lg border px-3 py-2 text-sm transition-colors ${
                      transactionType === "income"
                        ? "border-green-600 bg-green-600 text-white"
                        : "border-border-input bg-card-bg text-text-primary hover:bg-soft-green-bg"
                    }`}
                  >
                    รายรับ
                  </button>
                  <button
                    type="button"
                    onClick={() => setTransactionType("expense")}
                    className={`flex-1 rounded-lg border px-3 py-2 text-sm transition-colors ${
                      transactionType === "expense"
                        ? "border-red-600 bg-red-600 text-white"
                        : "border-border-input bg-card-bg text-text-primary hover:bg-red-50"
                    }`}
                  >
                    รายจ่าย
                  </button>
                </div>
              </div>

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
            </div>
          </div>

          {/* (29 ก.ย. 2026) ย้ายกล่อง error + ปุ่มบันทึกออกจากท้ายกล่องฟอร์มมาไว้
              ล่างสุดเต็มความกว้าง เหมือน MultiUploadFlow -- จอ lg ติดล่างจอตลอด
              (shrink-0) ไม่ต้องเลื่อนฟอร์มลงไปหาปุ่ม และ error ทั้งแบบ validation
              กับบันทึกไม่สำเร็จอยู่เหนือปุ่มที่เดียวกัน */}
          <div className="mt-6 shrink-0">
            {(validationErrors.length > 0 || error) && (
              <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 lg:max-h-24 lg:overflow-y-auto">
                {validationErrors.map((msg) => (
                  <div key={msg}>{msg}</div>
                ))}
                {error && <div>{error}</div>}
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

          <ImageLightbox
            open={isLightboxOpen}
            src={previewUrl}
            alt="สลิปต้นฉบับ (ขยาย)"
            onClose={() => setIsLightboxOpen(false)}
          />
        </>
      )}
    </div>
  );
}
