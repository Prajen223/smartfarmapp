"use client";

import React, { useEffect, useState } from "react";
import { SavedGuidanceItem, SupportedLanguage } from "../types";
import { getSavedGuidanceList, removeSavedGuidance } from "../lib/offline-storage";
import { translations } from "../lib/translations";

interface SavedGuidanceModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedLang: SupportedLanguage;
}

export const SavedGuidanceModal: React.FC<SavedGuidanceModalProps> = ({
  isOpen,
  onClose,
  selectedLang,
}) => {
  const [items, setItems] = useState<SavedGuidanceItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const t = translations[selectedLang];

  useEffect(() => {
    let active = true;
    if (isOpen) {
      getSavedGuidanceList()
        .then((list) => {
          if (active) {
            setItems(list);
            setLoading(false);
          }
        })
        .catch(() => {
          if (active) setLoading(false);
        });
    }
    return () => {
      active = false;
    };
  }, [isOpen]);

  if (!isOpen) return null;

  async function handleDelete(id: string) {
    await removeSavedGuidance(id);
    setItems((prev) => prev.filter((item) => item.id !== id));
  }

  function handleCopy(id: string, text: string) {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2000);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="saved-guidance-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-3 sm:p-4 animate-fade-in"
    >
      <div className="relative w-full max-w-2xl max-h-[90vh] flex flex-col rounded-3xl bg-white shadow-2xl border border-emerald-100 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-emerald-100 bg-emerald-50/70 px-5 py-4">
          <div className="flex items-center gap-2.5">
            <span className="flex h-9 w-9 items-center justify-center rounded-2xl bg-emerald-700 text-white text-base shadow-xs">
              🔖
            </span>
            <div>
              <h2 id="saved-guidance-title" className="text-base sm:text-lg font-black text-emerald-950">
                {t.savedGuidance || "Saved Guidance"}
              </h2>
              <p className="text-2xs sm:text-xs text-emerald-700 font-medium">
                {items.length} {items.length === 1 ? "advisory" : "advisories"} available offline in browser storage
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-xl bg-white/80 hover:bg-emerald-100 text-gray-500 hover:text-emerald-900 transition font-bold text-sm"
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        {/* Content list */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
          {loading ? (
            <div className="py-12 text-center text-sm font-semibold text-emerald-800">
              Loading offline guidance...
            </div>
          ) : items.length === 0 ? (
            <div className="py-12 text-center px-4">
              <span className="text-4xl inline-block mb-3">🌾</span>
              <p className="text-sm font-bold text-gray-800 mb-1">
                {t.savedGuidance || "No saved guidance"}
              </p>
              <p className="text-xs text-gray-500 max-w-sm mx-auto">
                {t.noSavedGuidance ||
                  "Click the bookmark icon on any answer to save it for reading anytime, even without an internet connection."}
              </p>
            </div>
          ) : (
            items.map((item) => (
              <div
                key={item.id}
                className="rounded-2xl border border-emerald-100 bg-white p-4 shadow-2xs hover:shadow-xs transition"
              >
                {/* Status & Date bar */}
                <div className="flex items-center justify-between gap-2 pb-2 mb-2 border-b border-gray-100">
                  <div className="flex items-center gap-1.5">
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-2xs font-bold text-emerald-800">
                      <span>💾</span> {t.guidanceSaved || "Saved Offline"}
                    </span>
                    {item.intent && (
                      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-2xs font-semibold text-gray-700 capitalize">
                        {item.intent.replace(/_/g, " ")}
                      </span>
                    )}
                  </div>
                  <span className="text-2xs text-gray-400">
                    {new Date(item.savedAt).toLocaleDateString(undefined, {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                </div>

                {/* Farmer Question */}
                <div className="text-xs font-bold text-emerald-900 mb-1.5 flex items-start gap-1.5">
                  <span className="text-emerald-700">Q:</span>
                  <span>{item.question}</span>
                </div>

                {/* Guidance Answer */}
                <div className="text-xs text-gray-800 leading-relaxed whitespace-pre-wrap bg-emerald-50/40 rounded-xl p-3 border border-emerald-100/60 mb-3">
                  {item.answer}
                </div>

                {/* Source Citations */}
                {item.sources && item.sources.length > 0 && (
                  <div className="mb-3">
                    <span className="text-2xs font-bold uppercase tracking-wider text-emerald-800 block mb-1">
                      {t.sourcesVerified}:
                    </span>
                    <div className="flex flex-wrap gap-1">
                      {item.sources.map((src, idx) => (
                        <span
                          key={idx}
                          className="rounded-md bg-white border border-emerald-200 px-2 py-0.5 text-2xs font-medium text-emerald-900"
                        >
                          ✓ {src}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions: Copy & Delete */}
                <div className="flex items-center justify-end gap-2 pt-2 border-t border-gray-100 text-xs">
                  <button
                    type="button"
                    onClick={() => handleCopy(item.id, item.answer)}
                    className="flex items-center gap-1 rounded-lg px-2.5 py-1 text-2xs font-bold text-gray-600 hover:text-emerald-800 hover:bg-emerald-50 transition"
                  >
                    <span>{copiedId === item.id ? "✓ Copied" : "📋 Copy"}</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(item.id)}
                    className="flex items-center gap-1 rounded-lg px-2.5 py-1 text-2xs font-bold text-red-600 hover:text-red-800 hover:bg-red-50 transition"
                  >
                    <span>🗑️ {t.removeSaved || "Remove"}</span>
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-emerald-100 bg-gray-50 px-5 py-3 flex items-center justify-between text-2xs text-gray-500">
          <span>Protected offline in browser IndexedDB</span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl bg-emerald-700 px-4 py-1.5 font-bold text-white hover:bg-emerald-800 transition"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
