"use client";

import { useState, ChangeEvent, DragEvent } from "react";
import { UploadCloud } from "lucide-react";
import SingleUploadFlow from "@/components/upload/SingleUploadFlow";
import MultiUploadFlow from "@/components/upload/MultiUploadFlow";

export default function UploadPage() {
  const [selectedFiles, setSelectedFiles] = useState<File[] | null>(null);
  // เปลี่ยนทุกครั้งที่เลือกไฟล์ใหม่ -- ใช้เป็น key บังคับให้ component
  // ข้างล่าง mount ใหม่ทั้งหมด (รีเซ็ต state เดิมทิ้ง) แม้จะเลือกไฟล์ชื่อเดิมซ้ำ
  const [uploadKey, setUploadKey] = useState(0);
  // จำนวนไฟล์ที่เหลือในคิวของ MultiUploadFlow (null = ยังไม่มีรายงาน ใช้จำนวนที่เลือกไว้)
  const [queueCount, setQueueCount] = useState<number | null>(null);

  const handleCancel = () => setSelectedFiles(null);
    // ไฮไลต์กล่องตอนลากไฟล์มาค้างอยู่ด้านบน
  const [isDragging, setIsDragging] = useState(false);

  // ทางเข้ากลางของไฟล์ ทั้งจากการกดเลือกและลากวาง
  const acceptFiles = (files: File[]) => {
    if (files.length === 0) return;
    setSelectedFiles(files);
    setUploadKey((k) => k + 1);
    setQueueCount(null);
  };

  const handleFilesChange = (e: ChangeEvent<HTMLInputElement>) => {
    acceptFiles(Array.from(e.target.files ?? []));
  };

  const handleDragOver = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault(); // ต้องมี ไม่งั้นเบราว์เซอร์ไม่ยอมให้วาง
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLLabelElement>) => {
    // ตอนเมาส์ผ่านข้อความ/ไอคอนข้างใน จะยิง dragleave ด้วย ให้ข้ามไป กันไฮไลต์กะพริบ
    if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setIsDragging(false);
    // การลากวางไม่ผ่าน accept="image/*" ของ input จึงต้องกรองเอง
    acceptFiles(Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith("image/")));
  };

  return (
    <div className="min-h-screen bg-page-bg p-8">
      <h1 className="mb-6 text-xl font-semibold text-text-primary">อัปโหลดสลิป</h1>

      {!selectedFiles && (
                <label
          htmlFor="slip-upload-input"
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          className={`mb-6 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-16 text-center transition-colors hover:border-emerald hover:bg-soft-green-bg ${
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
      )}

      {selectedFiles && (
        <div className="mb-6 flex items-center justify-between rounded-lg border border-border-input bg-card-bg px-4 py-3">
                    <p className="text-sm text-text-primary">
            {(queueCount ?? selectedFiles.length) === 0
              ? "ไม่มีไฟล์ในคิว"
              : `เลือกไว้ ${queueCount ?? selectedFiles.length} ไฟล์`}
          </p>
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
        </div>
      )}

      {selectedFiles && selectedFiles.length === 1 && (
        <SingleUploadFlow key={uploadKey} file={selectedFiles[0]} onCancel={handleCancel} />
      )}

      {selectedFiles && selectedFiles.length > 1 && (
        <MultiUploadFlow key={uploadKey} files={selectedFiles} onQueueChange={setQueueCount} />
      )}
    </div>
  );
}
