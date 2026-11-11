"use client";

import React from "react";
import { SupportedLanguage } from "../types";
import { translations } from "../lib/translations";

interface ConfirmModalProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  selectedLang: SupportedLanguage;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  onConfirm,
  onCancel,
  selectedLang,
}) => {
  const t = translations[selectedLang];

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-headline"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 backdrop-blur-xs animate-fade-in"
    >
      <div className="w-full max-w-sm rounded-3xl bg-white p-6 shadow-2xl border border-emerald-100 animate-scale-up text-center">
        {/* Warning Icon */}
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-100 text-amber-900 text-2xl">
          🔄
        </div>

        <h3 id="modal-headline" className="mt-3 text-lg font-black text-gray-900">
          {t.newChatConfirmTitle}
        </h3>
        <p className="mt-2 text-xs text-gray-600 leading-relaxed">
          {t.newChatConfirmText}
        </p>

        <div className="mt-5 flex gap-2.5">
          <button
            type="button"
            onClick={onCancel}
            className="flex-1 rounded-xl border border-gray-300 bg-white py-2.5 text-xs font-bold text-gray-700 shadow-2xs hover:bg-gray-50 active:scale-95 transition"
          >
            {t.cancel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className="flex-1 rounded-xl bg-emerald-700 py-2.5 text-xs font-bold text-white shadow-md hover:bg-emerald-800 active:scale-95 transition"
          >
            {t.confirm}
          </button>
        </div>
      </div>
    </div>
  );
};
