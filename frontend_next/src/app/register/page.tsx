"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ShieldCheck, Eye, EyeOff } from "lucide-react";
import { useAuth, ApiRequestError } from "@/contexts/AuthContext";
import Link from "next/link";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirmPassword) {
      setError("รหัสผ่านทั้งสองช่องไม่ตรงกัน");
      return;
    }

    setIsSubmitting(true);
    try {
      await register(username, password);
      router.push("/login");
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
        className="w-full max-w-sm rounded-xl border border-border-gray bg-card-bg p-8 shadow-xl"
      >
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-soft-green-bg">
            <ShieldCheck className="text-emerald" size={24} />
          </div>
          <h2 className="text-2xl font-extrabold tracking-tight text-emerald">
            VeriSlip
          </h2>
          <h1 className="mt-4 text-xl font-semibold text-text-primary">สมัครสมาชิก</h1>
          <p className="mt-2 text-sm text-text-secondary">สร้างบัญชีเพื่อเริ่มใช้งาน</p>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        )}

        <label className="mb-1 block text-sm text-text-primary">ชื่อผู้ใช้</label>
        <input
          className="mb-4 w-full rounded-lg border border-border-input px-3 py-2 outline-none focus:border-emerald"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />

        <label className="mb-1 block text-sm text-text-primary">รหัสผ่าน</label>
        <div className="relative mb-4">
          <input
            type={showPassword ? "text" : "password"}
            className="w-full rounded-lg border border-border-input px-3 py-2 pr-10 outline-none focus:border-emerald"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
          <button
            type="button"
            onClick={() => setShowPassword((prev) => !prev)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary"
            tabIndex={-1}
          >
            {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        </div>

        <label className="mb-1 block text-sm text-text-primary">ยืนยันรหัสผ่าน</label>
        <div className="relative mb-8">
          <input
            type={showConfirmPassword ? "text" : "password"}
            className="w-full rounded-lg border border-border-input px-3 py-2 pr-10 outline-none focus:border-emerald"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            minLength={8}
            required
          />
          <button
            type="button"
            onClick={() => setShowConfirmPassword((prev) => !prev)}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary"
            tabIndex={-1}
          >
            {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
          </button>
        </div>

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full rounded-lg bg-emerald px-4 py-2 text-white transition-colors hover:bg-emerald-hover disabled:opacity-50"
        >
          {isSubmitting ? "กำลังสมัครสมาชิก..." : "สมัครสมาชิก"}
        </button>
        
        <p className="mt-4 text-center text-sm text-text-primary">
          มีบัญชีอยู่แล้ว?{" "}
          <Link href="/login" className="text-emerald hover:underline">
          เข้าสู่ระบบ
          </Link>
        </p>
      </form>
    </div>
  );
}
