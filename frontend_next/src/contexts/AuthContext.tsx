"use client";

import {
  createContext, useContext, useEffect, useState, ReactNode,
} from "react";
import { apiFetch, ApiRequestError } from "@/lib/api";
import type { TokenResponse, CurrentUser } from "@/types/auth";

interface AuthContextValue {
  user: CurrentUser | null;
  token: string | null;
  isLoading: boolean; // กำลังเช็ค token เดิมตอนเปิดแอปครั้งแรกอยู่ไหม
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const TOKEN_KEY = "ai_doc_assistant_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // ตอนเปิดแอปมาใหม่ (refresh หน้า) เช็คว่ามี token เก่าใน localStorage
  // ไหม ถ้ามีลองยิง /auth/me ดูว่ายัง valid อยู่หรือหมดอายุไปแล้ว
  useEffect(() => {
    const saved = localStorage.getItem(TOKEN_KEY);
    if (!saved) {
      setIsLoading(false);
      return;
    }
    apiFetch<CurrentUser>("/auth/me", { token: saved })
      .then((me) => {
        setToken(saved);
        setUser(me);
      })
      .catch(() => {
        localStorage.removeItem(TOKEN_KEY); // token หมดอายุ/ใช้ไม่ได้แล้ว
      })
      .finally(() => setIsLoading(false));
  }, []);

  const applyToken = (res: TokenResponse) => {
    localStorage.setItem(TOKEN_KEY, res.access_token);
    setToken(res.access_token);
    setUser({ username: res.username });
  };

  const login = async (username: string, password: string) => {
    const res = await apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    applyToken(res);
  };

  const register = async (username: string, password: string) => {
    // backend คืน token กลับมาด้วย แต่ตามที่ตกลงกันไว้ ไม่ auto-login --
    // ไม่เรียก applyToken ที่นี่ ปล่อยให้หน้า register พาไปหน้า login แทน
    await apiFetch<TokenResponse>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  };

  const logout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export { ApiRequestError };
