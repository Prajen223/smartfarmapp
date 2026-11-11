"use client";

import React from "react";
import { SupportedLanguage } from "../types";
import { translations } from "../lib/translations";

interface WelcomeCardProps {
  selectedLang: SupportedLanguage;
  onSelectSuggestion: (question: string) => void;
  disabled?: boolean;
}

export const WelcomeCard: React.FC<WelcomeCardProps> = ({
  selectedLang,
  onSelectSuggestion,
  disabled = false,
}) => {
  const t = translations[selectedLang];

  const suggestionList = [
    {
      icon: "🧪",
      label: t.suggestions.fertilizer,
      category: "Fertilizer",
    },
    {
      icon: "🍂",
      label: t.suggestions.yellowLeaves,
      category: "Pest & Disease",
    },
    {
      icon: "💧",
      label: t.suggestions.irrigation,
      category: "Irrigation",
    },
    {
      icon: "🌾",
      label: t.suggestions.marketPrice,
      category: "Mandi Rates",
    },
  ];

  return (
    <div className="flex flex-col items-center justify-center py-4 px-2 text-center sm:py-10 max-w-full">
      {/* Friendly Sprout Badge */}
      <div className="inline-flex h-14 w-14 sm:h-16 sm:w-16 items-center justify-center rounded-3xl bg-gradient-to-tr from-emerald-100 to-green-50 shadow-inner border border-emerald-200">
        <span className="text-2xl sm:text-3xl" role="img" aria-label="FarmSaathi Sprout">
          🌱
        </span>
      </div>

      <h2 className="mt-3 sm:mt-4 text-xl sm:text-3xl font-black tracking-tight text-emerald-950 px-2">
        {t.welcomeGreeting}
      </h2>
      <p className="mt-1.5 max-w-sm text-xs sm:text-sm font-semibold text-emerald-800 px-2">
        {t.welcomeSub}
      </p>
      <p className="mt-1.5 max-w-sm text-xs text-gray-500 px-2">
        {t.welcomeInstruction}
      </p>

      {/* Suggested Questions Grid */}
      <div className="mt-5 w-full max-w-sm space-y-2.5 text-left px-1">
        <p className="text-[11px] font-bold uppercase tracking-wider text-emerald-900/60 px-1">
          {t.suggestedTitle}
        </p>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {suggestionList.map((item, idx) => (
            <button
              key={idx}
              type="button"
              disabled={disabled}
              onClick={() => onSelectSuggestion(item.label)}
              className="group flex flex-col justify-between rounded-2xl border border-emerald-100 bg-white p-3.5 shadow-2xs transition hover:border-emerald-300 hover:bg-emerald-50/70 hover:shadow-xs active:scale-[0.98] disabled:opacity-50"
            >
              <div className="flex items-center gap-2 mb-1.5">
                <span className="text-lg">{item.icon}</span>
                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700">
                  {item.category}
                </span>
              </div>
              <p className="text-xs font-bold text-gray-800 group-hover:text-emerald-950 line-clamp-2">
                {item.label}
              </p>
              <span className="mt-2 inline-flex items-center text-[10px] font-bold text-emerald-800 group-hover:translate-x-0.5 transition-transform">
                Ask FarmSaathi →
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
};
