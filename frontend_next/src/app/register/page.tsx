"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { useAuth, ApiRequestError } from "@/contexts/AuthContext";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    // เช็คฝั่ง frontend ก่อนยิง API เลย -- ไม่ต้องรอ backend บอก
    // (backend เองก็เช็คความยาวขั้นต่ำ 8 ตัวอักษรอยู่แล้ว แต่ไม่เช็คตรงกันของ 2 ช่องนี้ให้)
    if (password !== confirmPassword) {
      setError("รหัสผ่านทั้งสองช่องไม่ตรงกัน");
      return;
    }

    setIsSubmitting(true);
    try {
      await register(username, password);
      router.push("/login"); // ตามที่ตกลงกันไว้: ไม่ auto-login, ไม่มีข้อความสำเร็จเพิ่ม
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "เชื่อมต่อเซิร์ฟเวอร์ไม่ได้");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-page-bg">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm rounded-xl bg-card-bg p-8 shadow-sm"
      >
        <h1 className="mb-6 text-xl font-semibold text-text-primary">สมัครสมาชิก</h1>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        <label className="mb-1 block text-sm text-text-primary">ชื่อผู้ใช้</label>
        <input
          className="mb-4 w-full rounded-lg border border-border-gray px-3 py-2 outline-none focus:border-emerald"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />

        <label className="mb-1 block text-sm text-text-primary">รหัสผ่าน</label>
        <input
          type="password"
          className="mb-4 w-full rounded-lg border border-border-gray px-3 py-2 outline-none focus:border-emerald"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={8}
          required
        />

        <label className="mb-1 block text-sm text-text-primary">ยืนยันรหัสผ่าน</label>
        <input
          type="password"
          className="mb-6 w-full rounded-lg border border-border-gray px-3 py-2 outline-none focus:border-emerald"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          minLength={8}
          required
        />

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-lg bg-emerald px-4 py-2 text-white transition-colors hover:bg-emerald-hover disabled:opacity-50"
        >
          {isSubmitting ? "กำลังสมัครสมาชิก..." : "สมัครสมาชิก"}
        </button>
      </form>
    </div>
  );
}
