"use client";

import React, { useState, useEffect } from "react";
import { SupportedLanguage } from "../types";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

interface InstallBannerProps {
  selectedLang: SupportedLanguage;
}

export const InstallBanner: React.FC<InstallBannerProps> = ({ selectedLang }) => {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [showManualGuide, setShowManualGuide] = useState(false);
  const [isStandalone, setIsStandalone] = useState(() => {
    if (typeof window !== "undefined") {
      return (
        window.matchMedia("(display-mode: standalone)").matches ||
        (navigator as unknown as { standalone?: boolean }).standalone === true
      );
    }
    return false;
  });

  useEffect(() => {
    if (isStandalone) {
      return;
    }

    // Check if previously dismissed within 7 days
    try {
      const dismissedAt = localStorage.getItem("farmsaathi_pwa_dismissed");
      if (dismissedAt) {
        const diffDays = (Date.now() - parseInt(dismissedAt, 10)) / (1000 * 60 * 60 * 24);
        if (diffDays < 7) {
          return;
        }
      }
    } catch {
      // Storage unavailable
    }

    const handleBeforeInstallPrompt = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setIsVisible(true);
    };

    const handleAppInstalled = () => {
      setIsVisible(false);
      setDeferredPrompt(null);
      setIsStandalone(true);
      console.log("[PWA] FarmSaathi installed successfully!");
    };

    window.addEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
    window.addEventListener("appinstalled", handleAppInstalled);

    return () => {
      window.removeEventListener("beforeinstallprompt", handleBeforeInstallPrompt);
      window.removeEventListener("appinstalled", handleAppInstalled);
    };
  }, [isStandalone]);

  const handleInstallClick = async () => {
    if (!deferredPrompt) {
      // Fallback: show manual install instructions (for iOS Safari or non-Chrome browsers)
      setShowManualGuide(true);
      return;
    }

    try {
      await deferredPrompt.prompt();
      const choice = await deferredPrompt.userChoice;
      if (choice.outcome === "accepted") {
        setIsVisible(false);
      }
      setDeferredPrompt(null);
    } catch (err) {
      console.warn("[PWA] Installation prompt error:", err);
    }
  };

  const handleDismiss = () => {
    setIsVisible(false);
    setShowManualGuide(false);
    try {
      localStorage.setItem("farmsaathi_pwa_dismissed", Date.now().toString());
    } catch {
      // Storage unavailable
    }
  };

  if (isStandalone || (!isVisible && !showManualGuide)) {
    return null;
  }

  const translations = {
    en: {
      installTitle: "Install FarmSaathi App",
      installDesc: "Add to home screen for faster voice access and offline support.",
      installBtn: "Install App",
      guideTitle: "How to Install FarmSaathi",
      guideAndroid: "On Android Chrome: Tap menu (⋮) and select 'Install app' or 'Add to Home screen'.",
      guideIos: "On iPhone / iPad: Tap Share (⎙) and select 'Add to Home Screen'.",
      close: "Close",
    },
    hi: {
      installTitle: "फार्मसाथी ऐप इंस्टॉल करें",
      installDesc: "तेज़ आवाज़ और ऑफ़लाइन उपयोग के लिए होम स्क्रीन पर जोड़ें।",
      installBtn: "ऐप इंस्टॉल करें",
      guideTitle: "फार्मसाथी कैसे इंस्टॉल करें",
      guideAndroid: "एंड्रॉइड क्रोम में: मेनू (⋮) दबाएं और 'ऐप इंस्टॉल करें' चुनें।",
      guideIos: "आईफोन पर: शेयर (⎙) दबाएं और 'होम स्क्रीन में जोड़ें' चुनें।",
      close: "बंद करें",
    },
    kn: {
      installTitle: "ಫಾರ್ಮ್‌ಸಾಥಿ ಆ್ಯಪ್ ಇನ್‌ಸ್ಟಾಲ್ ಮಾಡಿ",
      installDesc: "ವೇಗದ ಧ್ವನಿ ಪ್ರವೇಶ ಮತ್ತು ಆಫ್‌ಲೈನ್ ಬಳಕೆಗಾಗಿ ಹೋಮ್ ಸ್ಕ್ರೀನ್‌ಗೆ ಸೇರಿಸಿ.",
      installBtn: "ಆ್ಯಪ್ ಇನ್‌ಸ್ಟಾಲ್ ಮಾಡಿ",
      guideTitle: "ಫಾರ್ಮ್‌ಸಾಥಿ ಇನ್‌ಸ್ಟಾಲ್ ಮಾಡುವುದು ಹೇಗೆ",
      guideAndroid: "ಆಂಡ್ರಾಯ್ಡ್ Chrome ನಲ್ಲಿ: ಮೆನು (⋮) ಒತ್ತಿ ಮತ್ತು 'ಆ್ಯಪ್ ಇನ್‌ಸ್ಟಾಲ್ ಮಾಡಿ' ಆಯ್ಕೆಮಾಡಿ.",
      guideIos: "iPhone ನಲ್ಲಿ: ಶೇರ್ (⎙) ಒತ್ತಿ 'ಹೋಮ್ ಸ್ಕ್ರೀನ್‌ಗೆ ಸೇರಿಸಿ' ಆಯ್ಕೆಮಾಡಿ.",
      close: "ಮುಚ್ಚಿ",
    },
  };

  const t = translations[selectedLang] || translations.en;

  return (
    <div className="bg-gradient-to-r from-emerald-800 to-green-700 text-white px-3 py-2 text-xs shadow-md border-b border-emerald-900/30 flex items-center justify-between gap-2 z-40 relative animate-fade-in">
      {showManualGuide ? (
        <div className="flex-1 py-1">
          <p className="font-bold text-emerald-100 mb-0.5">{t.guideTitle}:</p>
          <p className="text-[11px] text-emerald-200">{t.guideAndroid}</p>
          <p className="text-[11px] text-emerald-200">{t.guideIos}</p>
        </div>
      ) : (
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <span className="text-base shrink-0">📲</span>
          <div className="min-w-0">
            <p className="font-bold truncate text-emerald-50">{t.installTitle}</p>
            <p className="text-[11px] text-emerald-200/90 truncate">{t.installDesc}</p>
          </div>
        </div>
      )}

      <div className="flex items-center gap-1.5 shrink-0">
        {!showManualGuide && (
          <button
            type="button"
            onClick={handleInstallClick}
            className="rounded-lg bg-white px-2.5 py-1 text-xs font-bold text-emerald-900 shadow-xs hover:bg-emerald-50 active:scale-95 transition"
          >
            {t.installBtn}
          </button>
        )}
        <button
          type="button"
          onClick={handleDismiss}
          className="rounded-lg p-1 text-emerald-200 hover:text-white hover:bg-emerald-900/40 transition"
          aria-label={t.close}
        >
          ✕
        </button>
      </div>
    </div>
  );
};
