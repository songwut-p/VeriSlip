"use client";

import { useEffect, useRef, useState } from "react";
import { MessageCircleQuestion, X } from "lucide-react";
import AskPanel from "./AskPanel";

const ANIMATION_MS = 300;

export default function AskTrigger() {
  const [shouldRender, setShouldRender] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!shouldRender) return;
    const id = requestAnimationFrame(() => setIsOpen(true));
    return () => cancelAnimationFrame(id);
  }, [shouldRender]);

  const handleToggle = () => {
    if (isOpen) {
      setIsOpen(false);
      setTimeout(() => setShouldRender(false), ANIMATION_MS);
      buttonRef.current?.focus();
    } else {
      setShouldRender(true);
    }
  };

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        onClick={handleToggle}
        aria-label={isOpen ? "ปิดกล่องถาม AI" : "เปิดกล่องถาม AI"}
        className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-600 text-white shadow-lg transition-transform hover:bg-emerald-700 active:scale-95"
      >
        {isOpen ? (
          <X size={24} aria-hidden="true" />
        ) : (
          <MessageCircleQuestion size={24} aria-hidden="true" />
        )}
      </button>

      {shouldRender && (
        <>
          <div
            className={`fixed inset-0 z-30 bg-black/40 transition-opacity duration-300 ${
              isOpen ? "opacity-100" : "opacity-0"
            }`}
            onClick={handleToggle}
            aria-hidden="true"
          />
          <AskPanel isOpen={isOpen} onClose={handleToggle} />
        </>
      )}
    </>
  );
}
