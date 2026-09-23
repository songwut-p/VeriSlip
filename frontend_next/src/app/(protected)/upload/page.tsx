"use client";

import { useState, useEffect, useRef, ChangeEvent, DragEvent } from "react";
import { UploadCloud } from "lucide-react";
import SingleUploadFlow from "@/components/upload/SingleUploadFlow";
import MultiUploadFlow from "@/components/upload/MultiUploadFlow";
import ConfirmDialog from "@/components/ConfirmDialog";

export default function UploadPage() {
  const [selectedFiles, setSelectedFiles] = useState<File[] | null>(null);
  const [uploadKey, setUploadKey] = useState(0);
  const [queueCount, setQueueCount] = useState<number | null>(null);
  // รีเซ็ต queueCount ด้วย (23 ก.ย. 2026) -- ไม่งั้นค่าจากคิว multi รอบก่อน
  // ค้างอยู่จนกว่าจะเลือกไฟล์ใหม่ (acceptFiles ก็รีเซ็ตแบบเดียวกัน)
  const handleCancel = () => {
    setSelectedFiles(null);
    setQueueCount(null);
  };
  // ปุ่ม "ยกเลิก" บนแถบ (23 ก.ย. 2026): ถามยืนยันทุกครั้ง ไม่เช็คว่าแก้ฟอร์ม
  // ไปหรือยัง -- page นี้มองไม่เห็น state ข้างใน Single/Multi และกดเพิ่ม
  // ครั้งเดียวปลอดภัยกว่าลืมส่งสถานะขึ้นมาตอนเพิ่มช่องในฟอร์มวันหลัง
  const [isConfirmingCancel, setIsConfirmingCancel] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  // ข้อความเตือนแบบใช้ร่วมกัน: ไฟล์ผิดประเภท / ปล่อยไฟล์นอกกล่อง
  const [warningMessage, setWarningMessage] = useState<string | null>(null);
  const warningTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const triggerWarning = (message: string) => {
    if (warningTimeoutRef.current) clearTimeout(warningTimeoutRef.current);
    setWarningMessage(message);
    warningTimeoutRef.current = setTimeout(() => setWarningMessage(null), 3000);
  };

  useEffect(() => {
    return () => {
      if (warningTimeoutRef.current) clearTimeout(warningTimeoutRef.current);
    };
  }, []);

  // กันเบราว์เซอร์เปิดไฟล์เองเวลาปล่อยไฟล์นอกกล่องที่กำหนด (ทั้งหน้า)
  useEffect(() => {
    const handleWindowDragOver = (e: Event) => {
      e.preventDefault();
    };
    const handleWindowDrop = (e: Event) => {
      e.preventDefault();
      // ถ้าปล่อยถูก drop target ที่ถูกต้อง handler ของ target นั้น
      // จะ stopPropagation ไปแล้ว โค้ดนี้เลยรันเฉพาะตอนปล่อยพลาดกล่องเท่านั้น
      triggerWarning("กรุณาลากไฟล์มาวางในกล่องที่กำหนด");
    };

    window.addEventListener("dragover", handleWindowDragOver);
    window.addEventListener("drop", handleWindowDrop);
    return () => {
      window.removeEventListener("dragover", handleWindowDragOver);
      window.removeEventListener("drop", handleWindowDrop);
    };
  }, []);

  const acceptFiles = (files: File[]) => {
    if (files.length === 0) return;
    setSelectedFiles(files);
    setUploadKey((k) => k + 1);
    setQueueCount(null);
    if (warningTimeoutRef.current) clearTimeout(warningTimeoutRef.current);
    setWarningMessage(null);
  };

  const handleFilesChange = (e: ChangeEvent<HTMLInputElement>) => {
    acceptFiles(Array.from(e.target.files ?? []));
  };

  const handleDragOver = (e: DragEvent<HTMLElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLElement>) => {
    if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLElement>) => {
    e.preventDefault();
    e.stopPropagation(); // กัน window listener ทำงานซ้ำตอนปล่อยถูกกล่องแล้ว
    setIsDragging(false);
    const imageFiles = Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith("image/"));
    if (imageFiles.length === 0 && e.dataTransfer.files.length > 0) {
      triggerWarning("รองรับเฉพาะไฟล์รูปภาพ (JPG, PNG)");
      return;
    }
    acceptFiles(imageFiles);
  };

  return (
    <div className="min-h-screen bg-page-bg p-8">
      <h1 className="mb-6 text-xl font-semibold text-text-primary">อัปโหลดสลิป</h1>

      {!selectedFiles && (
        <>
          <label
            htmlFor="slip-upload-input"
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`mb-2 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-16 text-center transition-colors hover:border-emerald hover:bg-soft-green-bg ${
              isDragging ? "border-emerald bg-soft-green-bg" : "border-border-input bg-card-bg"
            }`}
          >
            <UploadCloud className="mb-3 text-text-secondary" size={40} />
            <p className="text-sm font-medium text-text-primary">คลิกหรือลากไฟล์สลิปมาวางที่นี่</p>
            <p className="mt-1 text-sm text-text-secondary">
              รองรับไฟล์รูปภาพ (JPG, PNG) เลือกได้หลายไฟล์พร้อมกัน
            </p>
            <input
              id="slip-upload-input"
              type="file"
              accept="image/*"
              multiple
              onChange={handleFilesChange}
              className="hidden"
            />
          </label>
          {warningMessage && (
            <p className="mb-4 rounded-md bg-warning-bg px-3 py-2 text-sm text-warning">{warningMessage}</p>
          )}
        </>
      )}

      {selectedFiles && (
        <div className="mb-6">
          <div
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className="flex items-center justify-between rounded-lg border border-border-input bg-card-bg px-4 py-3"
          >
            <p className="text-sm text-text-primary">
              {(queueCount ?? selectedFiles.length) === 0
                ? "ไม่มีไฟล์ในคิว"
                : `เลือกไว้ ${queueCount ?? selectedFiles.length} ไฟล์`}
            </p>
            <div className="flex items-center gap-4">
              <label htmlFor="slip-upload-input" className="cursor-pointer text-sm text-emerald hover:underline">
                เปลี่ยนไฟล์
                <input
                  id="slip-upload-input"
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={handleFilesChange}
                  className="hidden"
                />
              </label>
              <button
                type="button"
                onClick={() => setIsConfirmingCancel(true)}
                className="rounded text-sm text-danger hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring"
              >
                ยกเลิก
              </button>
            </div>
          </div>
          {warningMessage && (
            <p className="mt-2 rounded-md bg-warning-bg px-3 py-2 text-sm text-warning">{warningMessage}</p>
          )}
        </div>
      )}

      {selectedFiles && selectedFiles.length === 1 && (
        <SingleUploadFlow key={uploadKey} file={selectedFiles[0]} onQueueChange={setQueueCount} />
      )}

      {selectedFiles && selectedFiles.length > 1 && (
        <MultiUploadFlow key={uploadKey} files={selectedFiles} onQueueChange={setQueueCount} />
      )}

      <ConfirmDialog
        open={isConfirmingCancel}
        title="ยกเลิกการอัปโหลด?"
        message="ไฟล์ที่เลือกและข้อมูลที่แก้ไว้จะหายทั้งหมด (สลิปที่บันทึกแล้วไม่ได้รับผลกระทบ)"
        confirmLabel="ยกเลิกการอัปโหลด"
        // "เก็บไว้" แทนค่าเริ่มต้น "ยกเลิก" (23 ก.ย. 2026) -- ตอนเทสกดปุ่มแดง
        // พลาดไป 2 รอบ เพราะในคำถาม "ยกเลิกการอัปโหลด?" ปุ่มชื่อ "ยกเลิก"
        // อ่านได้ว่า "ใช่ ยกเลิกเลย" ใช้คำเดียวกับ dialog ของปุ่ม × ใน MultiUploadFlow
        cancelLabel="เก็บไว้"
        isBusy={false}
        onConfirm={() => {
          setIsConfirmingCancel(false);
          handleCancel();
        }}
        onCancel={() => setIsConfirmingCancel(false)}
      />
    </div>
  );
}
