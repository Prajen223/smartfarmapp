"use client";

import React from "react";
import { SupportedLanguage } from "../types";
import { translations } from "../lib/translations";

interface HeaderProps {
  selectedLang: SupportedLanguage;
  onLanguageChange: (lang: SupportedLanguage) => void;
  isBackendOnline: boolean;
  onNewChat: () => void;
  hasMessages: boolean;
  isOffline?: boolean;
  onOpenSavedGuidance?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  selectedLang,
  onLanguageChange,
  isBackendOnline,
  onNewChat,
  hasMessages,
  isOffline = false,
  onOpenSavedGuidance,
}) => {
  const t = translations[selectedLang];
  const isActuallyOnline = !isOffline && isBackendOnline;

  return (
    <header className="sticky top-0 z-30 border-b border-emerald-100 bg-white/95 px-3 sm:px-4 py-2.5 sm:py-3 shadow-xs backdrop-blur-md w-full">
      <div className="mx-auto flex max-w-4xl items-center justify-between gap-2">
        {/* FarmSaathi Brand Area */}
        <div className="flex items-center gap-2 min-w-0">
          <div className="flex h-9 w-9 sm:h-10 sm:w-10 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-600 to-green-700 text-white shadow-md shadow-emerald-700/20">
            <span className="text-lg sm:text-xl leading-none" role="img" aria-label="FarmSaathi Sprout">
              🌾
            </span>
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <h1 className="text-base sm:text-xl font-black tracking-tight text-emerald-950 truncate">
                FarmSaathi
              </h1>
              {/* Connection Status Pill */}
              <span
                className={`inline-flex items-center gap-1 rounded-full px-1.5 sm:px-2 py-0.5 text-[10px] font-bold shrink-0 ${
                  isActuallyOnline
                    ? "bg-emerald-100 text-emerald-800"
                    : isOffline
                    ? "bg-gray-200 text-gray-700"
                    : "bg-amber-100 text-amber-900"
                }`}
                title={
                  isOffline
                    ? "Device is offline"
                    : isBackendOnline
                    ? "FastAPI Backend Connected"
                    : "Connecting to backend..."
                }
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    isActuallyOnline
                      ? "bg-emerald-500 animate-pulse"
                      : isOffline
                      ? "bg-gray-500"
                      : "bg-amber-500 animate-ping"
                  }`}
                />
                <span>
                  {isOffline
                    ? t.offline
                    : !isBackendOnline
                    ? (t.connecting || "Connecting...")
                    : t.online}
                </span>
              </span>
            </div>
            <p className="text-[10px] sm:text-[11px] font-medium text-emerald-800/80 truncate">
              {t.tagline}
            </p>
          </div>
        </div>

        {/* Right Controls: Language Selector & New Chat */}
        <div className="flex items-center gap-1.5 shrink-0">
          {/* Language Selector */}
          <div className="relative">
            <label htmlFor="language-select" className="sr-only">
              Select Language
            </label>
            <select
              id="language-select"
              value={selectedLang}
              onChange={(e) => onLanguageChange(e.target.value as SupportedLanguage)}
              className="appearance-none rounded-xl border border-emerald-200 bg-emerald-50/70 py-1 pl-2.5 pr-6 text-xs font-bold text-emerald-900 shadow-2xs outline-none transition hover:bg-emerald-100 focus:border-emerald-600 focus:ring-2 focus:ring-emerald-200"
            >
              <option value="en">English</option>
              <option value="hi">हिंदी</option>
              <option value="kn">ಕನ್ನಡ</option>
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-1.5 text-emerald-800">
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
              </svg>
            </div>
          </div>

          {/* Saved Guidance Button */}
          {onOpenSavedGuidance && (
            <button
              type="button"
              onClick={onOpenSavedGuidance}
              className="flex items-center gap-1 rounded-xl border border-emerald-200 bg-emerald-50 px-2 sm:px-2.5 py-1 text-xs font-bold text-emerald-800 shadow-2xs transition hover:bg-emerald-100 hover:text-emerald-950 active:scale-95"
              title={t.savedGuidance || "Saved Guidance"}
              aria-label={t.savedGuidance || "Saved Guidance"}
            >
              <span>🔖</span>
              <span className="hidden sm:inline">{t.savedGuidance || "Saved"}</span>
            </button>
          )}

          {/* New Chat Button */}
          {hasMessages && (
            <button
              type="button"
              onClick={onNewChat}
              className="flex items-center gap-1 rounded-xl border border-emerald-200 bg-white px-2.5 py-1 text-xs font-bold text-emerald-800 shadow-2xs transition hover:bg-emerald-50 hover:text-emerald-950 active:scale-95"
              title={t.newChat}
              aria-label={t.newChat}
            >
              <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 4v16m8-8H4" />
              </svg>
              <span className="hidden sm:inline">{t.newChat}</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
