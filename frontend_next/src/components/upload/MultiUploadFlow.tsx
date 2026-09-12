"use client";

import { useState, useEffect } from "react";
import { apiFetch, ApiRequestError } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { FIELD_LABELS, NUMERIC_FIELDS, NAME_FIELDS } from "@/lib/constants";
import {
  prepareDisplayFields, getIssueFields, findSuspiciousNameFields,
} from "@/lib/slipFields";
import type { UploadSlipResponse, ParsedFields } from "@/types/slip";

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

  const updateFile = (id: number, patch: Partial<QueueFile>) => {
    setFiles((prev) => prev.map((f) => (f.id === id ? { ...f, ...patch } : f)));
  };

  const handleCancelFile = (id: number, filename: string) => {
    const confirmed = window.confirm(
      `ต้องการยกเลิกไฟล์ "${filename}" ใช่ไหม? ข้อมูลที่อ่าน/แก้ไขไปแล้วจะหายไปทั้งหมด กู้คืนไม่ได้`,
    );
    if (!confirmed) return;

    setFiles((prev) => {
      const remaining = prev.filter((f) => f.id !== id);
      if (activeId === id) {
        setActiveId(remaining.length > 0 ? remaining[0].id : null);
      }
      return remaining;
    });
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
            <p className="mb-4 text-text-primary">กำลังอ่านไฟล์ด้วย OCR...</p>
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

                <div className="flex gap-6">
                  <div className="w-2/5 rounded-xl border border-border-gray bg-card-bg p-4">
                    <p className="mb-2 font-medium text-text-primary">🖼️ รูปต้นฉบับ</p>
                    {/* eslint-disable-next-line @next/next/no-img-element -- blob URL */}
                    <img src={activeFile.previewUrl} alt="สลิปต้นฉบับ" className="w-full rounded-lg" />
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
                            onClick={() => handleCancelFile(f.id, f.file.name)}
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
    </div>
  );
}
