"use client";

import { useState, ChangeEvent } from "react";
import SingleUploadFlow from "@/components/upload/SingleUploadFlow";
import MultiUploadFlow from "@/components/upload/MultiUploadFlow";

export default function UploadPage() {
  const [selectedFiles, setSelectedFiles] = useState<File[] | null>(null);
  // เปลี่ยนทุกครั้งที่เลือกไฟล์ใหม่ -- ใช้เป็น key บังคับให้ component
  // ข้างล่าง mount ใหม่ทั้งหมด (รีเซ็ต state เดิมทิ้ง) แม้จะเลือกไฟล์ชื่อเดิมซ้ำ
  const [uploadKey, setUploadKey] = useState(0);

  const handleFilesChange = (e: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (files.length === 0) return;
    setSelectedFiles(files);
    setUploadKey((k) => k + 1);
  };

  return (
    <div className="min-h-screen bg-page-bg p-8">
      <h1 className="mb-6 text-xl font-semibold text-text-primary">อัปโหลดสลิป</h1>

      <input
        type="file"
        accept="image/*"
        multiple
        onChange={handleFilesChange}
        className="mb-6"
      />

      {selectedFiles && selectedFiles.length === 1 && (
        <SingleUploadFlow key={uploadKey} file={selectedFiles[0]} />
      )}

      {selectedFiles && selectedFiles.length > 1 && (
        <MultiUploadFlow key={uploadKey} files={selectedFiles} />
      )}
    </div>
  );
}
