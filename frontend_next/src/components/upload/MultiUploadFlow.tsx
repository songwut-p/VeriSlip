"use client";

import { useState, useEffect } from "react";
import { apiFetch, ApiRequestError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { FIELD_LABELS, NUMERIC_FIELDS, NAME_FIELDS } from "@/lib/constants";
import {
  prepareDisplayFields, getIssueFields, findSuspiciousNameFields,
} from "@/lib/slipFields";
import type { UploadSlipResponse, ParsedFields } from "@/types/slip";
import { Loader2 } from "lucide-react";
import ConfirmDialog from "@/components/ConfirmDialog";

const DOC_TYPE_LABELS: Record<string, string> = {
  bank_slip: "สลิปโอนเงิน",
  stock_confirmation: "คำสั่งซื้อหุ้น",
  unknown: "ไม่ทราบประเภท",
};

interface QueueFile {
  id: number;
  file: File;
  previewUrl: string;
  isLoading: boolean;
  error: string | null;
  result: UploadSlipResponse | null;
  editedValues: Record<string, string>;
  // transaction_type (13 ก.ย. 2026): แยกเก็บต่อไฟล์ในคิว เพราะแต่ละไฟล์
  // เป็นรายรับ/รายจ่ายไม่เหมือนกันได้ -- ต่างจาก SingleUploadFlow ที่มีแค่
  // ไฟล์เดียวจึงใช้ state เดี่ยวได้ ที่นี่ต้องผูกกับ QueueFile แต่ละตัวแทน
  transactionType: "income" | "expense" | "";
}

interface SaveSlipResponse {
  filename: string;
  status: string;
  db_row: { id: number; [key: string]: unknown };
}

function buildFinalParsed(
  original: ParsedFields,
  edited: Record<string, string>,
): { finalParsed: ParsedFields; editedAny: boolean } {
  const finalParsed: ParsedFields = { ...original };
  let editedAny = false;
  for (const [key, value] of Object.entries(edited)) {
    const baseline = original[key] === null ? "" : String(original[key]);
    if (value !== baseline) editedAny = true;
    if (value.trim() === "") {
      finalParsed[key] = null;
    } else if (NUMERIC_FIELDS.has(key)) {
      finalParsed[key] = Number(value);
    } else {
      finalParsed[key] = value;
    }
  }
  return { finalParsed, editedAny };
}

export default function MultiUploadFlow({ files: initialFiles }: { files: File[] }) {
  const { token } = useAuth();
  const [files, setFiles] = useState<QueueFile[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [confirmedAll, setConfirmedAll] = useState(false);
  const [isSavingAll, setIsSavingAll] = useState(false);
  const [saveAllErrors, setSaveAllErrors] = useState<string[]>([]);
  const [batchSummary, setBatchSummary] = useState<string | null>(null);
  // แยกไว้กันสับสนระหว่าง "ยังโหลดคิวเริ่มต้นไม่เสร็จ" กับ "cancel จนคิวว่างสนิท"
  // -- ไม่งั้นข้อความคิวว่างจะกระพริบโผล่มาแวบนึงตอน mount ก่อน useEffect ทำงาน
  const [initialized, setInitialized] = useState(false);
  // pendingCancel (18 ก.ย. 2026): ไฟล์ในคิวที่รอยืนยันยกเลิก (null = modal ปิด)
  // แทน window.confirm เดิม -- เก็บแค่ id กับชื่อ เพราะ modal ต้องใช้แค่นี้
  const [pendingCancel, setPendingCancel] = useState<{ id: number; name: string } | null>(null);

  const updateFile = (id: number, patch: Partial<QueueFile>) => {
    setFiles((prev) => prev.map((f) => (f.id === id ? { ...f, ...patch } : f)));
  };

  const handleConfirmCancel = () => {
    if (!pendingCancel) return;
    const id = pendingCancel.id;

    setFiles((prev) => {
      const remaining = prev.filter((f) => f.id !== id);
      if (activeId === id) {
        setActiveId(remaining.length > 0 ? remaining[0].id : null);
      }
      return remaining;
    });
    setPendingCancel(null);
  };

  const runOcr = async (item: QueueFile) => {
    const formData = new FormData();
    formData.append("file", item.file);
    try {
      const data = await apiFetch<UploadSlipResponse>("/upload-slip", {
        method: "POST",
        body: formData,
        token,
      });
      const displayFields = prepareDisplayFields(data.parsed);
      const initial: Record<string, string> = {};
      for (const [key, value] of Object.entries(displayFields)) {
        initial[key] = value === null ? "" : String(value);
      }
      updateFile(item.id, { result: data, editedValues: initial, isLoading: false });
    } catch (err) {
      const message = err instanceof ApiRequestError ? err.message : "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้";
      updateFile(item.id, { error: message, isLoading: false });
    }
  };

  useEffect(() => {
    const newQueue: QueueFile[] = initialFiles.map((file, index) => ({
      id: Date.now() + index,
      file,
      previewUrl: URL.createObjectURL(file),
      isLoading: true,
      error: null,
      result: null,
      editedValues: {},
      transactionType: "",
    }));

    setFiles(newQueue);
    setActiveId(newQueue[0]?.id ?? null);
    newQueue.forEach((item) => runOcr(item));
    setInitialized(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ตั้งใจรันแค่ครั้งเดียวตอน mount ต่อชุดไฟล์
  }, []);

  const handleSaveAll = async () => {
    if (!confirmedAll) {
      setSaveAllErrors(['กรุณาติ๊ก "ตรวจสอบข้อมูลทุกไฟล์ในคิวแล้ว ถูกต้องทั้งหมด" ก่อนบันทึก']);
      return;
    }

    const errors: string[] = [];
    files.forEach((f, idx) => {
      if (!f.result) {
        errors.push(`แท็บ ${idx + 1} (${f.file.name}): ยังอ่าน OCR ไม่เสร็จ`);
        return;
      }
      // บังคับเลือกรายรับ/รายจ่ายก่อนบันทึกทุกไฟล์ในคิว (13 ก.ย. 2026) --
      // เช็คก่อนเข้า loop field อื่นของแท็บนั้น เหมือน pattern ใน Single
      if (!f.transactionType) {
        errors.push(`แท็บ ${idx + 1} (${f.file.name}): กรุณาเลือกประเภทรายการ (รายรับ / รายจ่าย)`);
      }
      for (const [key, value] of Object.entries(f.editedValues)) {
        if (value.trim() && NUMERIC_FIELDS.has(key) && Number.isNaN(Number(value))) {
          errors.push(`แท็บ ${idx + 1} (${f.file.name}): '${FIELD_LABELS[key] ?? key}' ต้องเป็นตัวเลข (ได้รับ: ${value})`);
        }
        if (NAME_FIELDS.has(key) && value && /^\s*\d/.test(value)) {
          errors.push(`แท็บ ${idx + 1} (${f.file.name}): '${FIELD_LABELS[key] ?? key}' ดูเหมือนขึ้นต้นด้วยตัวเลข (ได้รับ: ${value})`);
        }
      }
    });

    if (errors.length > 0) {
      setSaveAllErrors(errors);
      return;
    }
    setSaveAllErrors([]);
    setIsSavingAll(true);

    let savedCount = 0;
    const failed: QueueFile[] = [];
    const failReasons: string[] = [];

    for (const f of files) {
      if (!f.result) continue;
      try {
        const { finalParsed, editedAny } = buildFinalParsed(f.result.parsed, f.editedValues);
        const saveResult = await apiFetch<SaveSlipResponse>("/save-slip", {
          method: "POST",
          token,
          body: JSON.stringify({
            filename: f.result.filename,
            doc_type: f.result.doc_type,
            parsed: finalParsed,
            ocr_text: f.result.ocr_text,
            extraction_flag: editedAny ? "user_edited" : "ai_extract_100",
            transaction_type: f.transactionType,
          }),
        });

        const imageForm = new FormData();
        imageForm.append("file", f.file);
        await apiFetch(`/slips/${saveResult.db_row.id}/image`, {
          method: "POST",
          token,
          body: imageForm,
        });

        savedCount++;
      } catch (err) {
        const message = err instanceof ApiRequestError ? err.message : "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้";
        failed.push(f);
        failReasons.push(`${f.file.name}: ${message}`);
      }
    }

    setFiles(failed);
    setActiveId(failed.length > 0 ? failed[0].id : null);
    setConfirmedAll(false);
    setIsSavingAll(false);
    if (failed.length === 0) {
      setBatchSummary(`🎉 บันทึกครบ ${savedCount}/${savedCount} ไฟล์แล้ว`);
    } else {
      setBatchSummary(`เสร็จสิ้นคิว: บันทึกสำเร็จ ${savedCount}/${savedCount + failed.length} ไฟล์`);
      setSaveAllErrors(failReasons);
    }
  };

  const activeFile = files.find((f) => f.id === activeId) ?? null;
  const anyLoading = files.some((f) => f.isLoading);

  return (
    <div>
      {batchSummary && (
        <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
          {batchSummary}
        </div>
      )}

      {/* คิวว่างสนิท (cancel จนหมดทุกไฟล์) -- เดิมตรงนี้ปล่อยโล่งเปล่าไม่มีอะไรเลย
          บอกทางออกให้ผู้ใช้แทนที่จะเจอหน้าว่างงงๆ */}
      {initialized && files.length === 0 && (
        <div className="rounded-lg border border-border-gray bg-card-bg px-4 py-6 text-center text-sm text-text-primary">
          ยกเลิกไฟล์ครบทุกไฟล์ในคิวแล้ว กรุณาเลือกไฟล์ใหม่จากด้านบนเพื่อเริ่มอัปโหลดอีกครั้ง
        </div>
      )}

      {activeFile && (
        <>
          {activeFile.isLoading && (
            <div className="mb-4 flex items-center gap-2">
              <Loader2 className="animate-spin text-emerald" size={18} />
              <p className="text-text-primary">กำลังอ่านไฟล์ด้วย OCR...</p>
            </div>
      )}

          {activeFile.error && (
            <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
              {activeFile.error}
            </div>
          )}

          {activeFile.result && (() => {
            const displayFields = prepareDisplayFields(activeFile.result.parsed);
            const issueFields = getIssueFields(activeFile.result.parsed);
            const suspiciousNameFields = findSuspiciousNameFields(displayFields);
            const docTypeLabel =
              DOC_TYPE_LABELS[activeFile.result.doc_type] ?? activeFile.result.doc_type;

            return (
              <>
                {suspiciousNameFields.length > 0 ? (
                  <div className="mb-4 rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-700">
                    ⚠️ ตรวจพบข้อความสุ่มเสี่ยง: โปรดตรวจสอบ {suspiciousNameFields.join(" และ ")} (มีตัวเลขนำหน้า)
                  </div>
                ) : Object.keys(issueFields).length > 0 ? (
                  <div className="mb-4 rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-700">
                    ⚠️ ตรวจพบจุดที่ AI อ่านไม่มั่นใจ {Object.keys(issueFields).length} จุด (ตรวจพบว่าเป็น: {docTypeLabel})
                  </div>
                ) : (
                  <div className="mb-4 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
                    ✅ อ่านไฟล์สำเร็จ — ตรวจพบว่าเป็น: {docTypeLabel}
                  </div>
                )}

                <div className="flex items-start gap-6">
                  <div className="w-2/5 rounded-xl border border-border-gray bg-card-bg p-4">
                    <p className="mb-2 font-medium text-text-primary">🖼️ รูปต้นฉบับ</p>
                    {/* eslint-disable-next-line @next/next/no-img-element -- blob URL */}
                    <img src={activeFile.previewUrl} alt="สลิปต้นฉบับ" className="w-full rounded-lg" />
                  </div>

                  {/* sticky + max-h + overflow-y-auto (13 ก.ย. 2026): แก้จากรอบ
                      ก่อน -- pattern เดียวกับ SingleUploadFlow (max-h เฉยๆ ไม่
                      พอเพราะ align-items:stretch เดิมทำให้ความสูงทั้งแถวถูก
                      กำหนดจากกล่องรูปที่สูงกว่าเสมอ) เปลี่ยน parent เป็น
                      items-start + กล่องฟอร์ม sticky top-4 ให้ลอยค้างอยู่
                      ตำแหน่งเดิมของจอ ไม่ขยับตามความยาวของกล่องรูป -- tab bar
                      ยังอยู่ในกล่องนี้ด้วย จึงอยู่ในพื้นที่ scroll เดียวกัน
                      ไม่ได้ fix แยกออกไปต่างหาก */}
                  <div className="w-3/5 sticky top-4 max-h-[calc(100vh-2rem)] overflow-y-auto scrollbar-hover-only rounded-xl border border-border-gray bg-card-bg p-4">
                    <p className="mb-4 font-medium text-text-primary">📝 ตรวจสอบและแก้ไขข้อมูล</p>

                    {/* ประเภทรายการ (13 ก.ย. 2026): วางบนสุดของฟอร์ม แยกจาก
                        ฟิลด์ที่มาจาก OCR เหมือน pattern ใน SingleUploadFlow --
                        ผูกกับ activeFile.transactionType เพราะแต่ละไฟล์ใน
                        คิวเลือกไม่เหมือนกันได้

                        แก้ตาม feedback 13 ก.ย. 2026 (UX polish) -- เหมือน
                        SingleUploadFlow ทุกประการ: (1) สีแยกจากปุ่ม Save
                        (เขียว=รายรับ, แดง=รายจ่าย) (2) เพิ่ม spacing
                        (3) ห่อด้วยกรอบ+พื้นหลังแยกต่างหากให้ดูเป็น widget */}
                    <div className="mb-6 rounded-lg border border-border-gray bg-page-bg p-3">
                      <label className="mb-2 block text-sm font-medium text-text-primary">ประเภทรายการ</label>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => updateFile(activeFile.id, { transactionType: "income" })}
                          className={`flex-1 rounded-lg border px-3 py-2 text-sm transition-colors ${
                            activeFile.transactionType === "income"
                              ? "border-green-600 bg-green-600 text-white"
                              : "border-border-input bg-card-bg text-text-primary hover:bg-soft-green-bg"
                          }`}
                        >
                          รายรับ
                        </button>
                        <button
                          type="button"
                          onClick={() => updateFile(activeFile.id, { transactionType: "expense" })}
                          className={`flex-1 rounded-lg border px-3 py-2 text-sm transition-colors ${
                            activeFile.transactionType === "expense"
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
                          value={activeFile.editedValues[key] ?? ""}
                          onChange={(e) =>
                            updateFile(activeFile.id, {
                              editedValues: { ...activeFile.editedValues, [key]: e.target.value },
                            })
                          }
                        />
                      </div>
                    ))}

                    <div className="mt-6 flex gap-2">
                      {files.map((f, index) => (
                        <div key={f.id} className="flex-1">
                          <button
                            onClick={() => setActiveId(f.id)}
                            className={`mb-1 w-full rounded-lg px-3 py-2 text-sm transition-colors ${
                              f.id === activeId
                                ? "bg-emerald text-white"
                                : "border border-border-gray bg-card-bg text-text-primary hover:bg-soft-green-bg"
                            }`}
                          >
                            {index + 1}/{files.length}
                            {f.isLoading && " ⏳"}
                          </button>
                          <button
                            onClick={() => setPendingCancel({ id: f.id, name: f.file.name })}
                            className="w-full rounded-lg border border-red-200 px-3 py-1 text-xs text-red-600 hover:bg-red-50"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </>
            );
          })()}

          <div className="mt-6">
            {saveAllErrors.length > 0 && (
              <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                {saveAllErrors.map((msg) => (
                  <div key={msg}>{msg}</div>
                ))}
              </div>
            )}

            <label className="mb-3 flex items-center gap-2 text-sm text-text-primary">
              <input
                type="checkbox"
                checked={confirmedAll}
                onChange={(e) => setConfirmedAll(e.target.checked)}
              />
              ตรวจสอบข้อมูลทุกไฟล์ในคิวแล้ว ถูกต้องทั้งหมด
            </label>

            <button
              onClick={handleSaveAll}
              disabled={isSavingAll || anyLoading}
              className="w-full rounded-lg bg-emerald px-4 py-2 text-white transition-colors hover:bg-emerald-hover disabled:opacity-50"
            >
              {isSavingAll ? "กำลังบันทึก..." : "บันทึกทั้งหมด"}
            </button>
          </div>
        </>
      )}

      {/* วางนอก activeFile && เพื่อให้ modal ยังอยู่ครบแม้ยกเลิกไฟล์สุดท้ายจนคิวว่าง
          ปุ่มฝั่งซ้ายใช้ "เก็บไว้" แทน "ยกเลิก" เพราะปุ่มยืนยันคือ "ยกเลิกไฟล์"
          ถ้าใช้คำว่า "ยกเลิก" ทั้งสองปุ่มจะสับสนว่าอันไหนคืออันไหน */}
      <ConfirmDialog
        open={pendingCancel !== null}
        title="ยกเลิกไฟล์นี้ออกจากคิว?"
        message="ข้อมูลที่อ่าน/แก้ไขไปแล้วจะหายไปทั้งหมด กู้คืนไม่ได้"
        itemName={pendingCancel?.name}
        confirmLabel="ยกเลิกไฟล์"
        cancelLabel="เก็บไว้"
        onConfirm={handleConfirmCancel}
        onCancel={() => setPendingCancel(null)}
      />
    </div>
  );
}
