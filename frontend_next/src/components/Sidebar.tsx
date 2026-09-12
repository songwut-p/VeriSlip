"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

const NAV_ITEMS = [
  { href: "/dashboard", label: "แดชบอร์ด" },
  { href: "/upload", label: "อัปโหลดสลิป" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col justify-between border-r border-border-gray bg-card-bg p-4">
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`rounded-lg px-3 py-2 text-sm transition-colors ${
                isActive
                  ? "bg-emerald text-white"
                  : "text-text-primary hover:bg-page-bg"
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-border-gray pt-3">
        <p className="mb-2 truncate px-3 text-sm text-text-primary">
          👤 {user?.username}
        </p>
        <button
          onClick={handleLogout}
          className="w-full rounded-lg border border-border-gray px-3 py-2 text-sm text-text-primary transition-colors hover:bg-page-bg"
        >
          ออกจากระบบ
        </button>
      </div>
    </aside>
  );
}
