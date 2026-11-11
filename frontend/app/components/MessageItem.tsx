"use client";

import React, { useState } from "react";
import { ChatMessage, SupportedLanguage } from "../types";
import { translations } from "../lib/translations";

interface MessageItemProps {
  message: ChatMessage;
  selectedLang: SupportedLanguage;
  onPlayAudio?: (messageId: string, text: string, audioBase64?: string, audioFormat?: string) => void;
  isPlaying?: boolean;
  activePlayingId?: string | null;
  isSynthesizingId?: string | null;
  sessionId?: string | null;
  onFeedbackSubmitted?: (messageId: string, rating: "positive" | "negative", comment?: string) => void;
}

export const MessageItem: React.FC<MessageItemProps> = ({
  message,
  selectedLang,
  onPlayAudio,
  isPlaying = false,
  activePlayingId = null,
  isSynthesizingId = null,
  sessionId = null,
  onFeedbackSubmitted,
}) => {
  const t = translations[selectedLang];
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const isAssistant = message.sender === "assistant";
  const isCurrentAudioPlaying = isPlaying && activePlayingId === message.id;
  const isCurrentSynthesizing = isSynthesizingId === message.id;

  // Feedback state
  const storageKey = `farmsaathi_fb_${message.messageId || message.id}`;
  const [rating, setRating] = useState<"positive" | "negative" | null>(() => {
    if (message.feedbackRating) return message.feedbackRating;
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem(storageKey);
        if (saved === "positive" || saved === "negative") return saved;
      } catch {}
    }
    return null;
  });
  const [commentDrawerOpen, setCommentDrawerOpen] = useState(false);
  const [commentText, setCommentText] = useState(message.feedbackComment || "");
  const [submittingFeedback, setSubmittingFeedback] = useState(false);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);

  const handleSendFeedback = async (voteRating: "positive" | "negative", voteComment?: string) => {
    const effectiveSessionId =
      message.sessionId ||
      sessionId ||
      (typeof window !== "undefined" ? sessionStorage.getItem("farmsaathi_session_id") : null);

    if (!effectiveSessionId) {
      setRating(voteRating);
      setCommentDrawerOpen(false);
      return;
    }

    setSubmittingFeedback(true);
    setFeedbackError(null);
    try {
      const res = await fetch("/api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: effectiveSessionId,
          message_id: message.messageId,
          rating: voteRating,
          comment: voteComment || undefined,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to submit feedback.");
      }

      setRating(voteRating);
      setCommentDrawerOpen(false);
      try {
        localStorage.setItem(storageKey, voteRating);
      } catch {}
      onFeedbackSubmitted?.(message.id, voteRating, voteComment);
    } catch (err: unknown) {
      setFeedbackError(err instanceof Error ? err.message : "Failed to record feedback.");
    } finally {
      setSubmittingFeedback(false);
    }
  };

  return (
    <div
      className={`flex w-full gap-2.5 my-3 ${
        isAssistant ? "justify-start" : "justify-end"
      }`}
    >
      {/* Assistant Avatar */}
      {isAssistant && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-tr from-emerald-600 to-green-700 text-white shadow-xs">
          <span className="text-base" role="img" aria-label="FarmSaathi Avatar">
            🌾
          </span>
        </div>
      )}

      {/* Message Bubble Container */}
      <div
        className={`flex max-w-[88%] sm:max-w-[80%] flex-col rounded-3xl p-4 shadow-xs ${
          isAssistant
            ? "border border-emerald-100 bg-white text-gray-900 rounded-tl-sm"
            : "bg-emerald-700 text-white rounded-tr-sm"
        }`}
      >
        {/* Header: Sender Label & Timestamp */}
        <div
          className={`flex items-center justify-between gap-3 text-[11px] font-semibold mb-1.5 ${
            isAssistant ? "text-emerald-800" : "text-emerald-100"
          }`}
        >
          <div className="flex items-center gap-1.5">
            <span>{isAssistant ? "FarmSaathi" : "You (Farmer)"}</span>
            {message.isVoice && (
              <span
                className={`rounded-full px-1.5 py-0.2 text-[10px] font-bold ${
                  isAssistant
                    ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                    : "bg-emerald-800 text-emerald-100"
                }`}
              >
                🎙️ Voice
              </span>
            )}
          </div>
          <span>{message.timestamp}</span>
        </div>

        {/* Spoken Transcript Callout (if message had voice transcript) */}
        {message.transcript && message.transcript !== message.text && (
          <div className="mb-2 rounded-xl bg-emerald-50/80 px-2.5 py-1 text-xs text-emerald-950 border border-emerald-200/60">
            <span className="font-bold">{t.transcriptLabel}: </span>
            <span>&ldquo;{message.transcript}&rdquo;</span>
          </div>
        )}

        {/* Message Main Body */}
        <div className="text-sm leading-relaxed sm:text-base font-normal whitespace-pre-wrap">
          {message.text}
        </div>

        {/* Audio Listen Aloud Player (for Assistant Responses) */}
        {isAssistant && onPlayAudio && (
          <div className="mt-3 pt-2.5 border-t border-emerald-100/80 flex items-center justify-between">
            <button
              type="button"
              onClick={() => onPlayAudio(message.id, message.text, message.audioBase64, message.audioFormat)}
              disabled={isCurrentSynthesizing}
              className={`flex items-center gap-2 rounded-xl px-3 py-1.5 text-xs font-bold transition shadow-2xs active:scale-95 disabled:opacity-60 ${
                isCurrentAudioPlaying
                  ? "bg-rose-100 text-rose-800 border border-rose-300"
                  : isCurrentSynthesizing
                  ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                  : "bg-emerald-50 text-emerald-900 border border-emerald-200 hover:bg-emerald-100"
              }`}
              aria-label={
                isCurrentAudioPlaying
                  ? t.stopAudio
                  : isCurrentSynthesizing
                  ? t.synthesizingAudio
                  : t.listenAloud
              }
            >
              {isCurrentSynthesizing ? (
                <>
                  <svg className="h-3 w-3 animate-spin text-emerald-700" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  <span>{t.synthesizingAudio}</span>
                </>
              ) : isCurrentAudioPlaying ? (
                <>
                  <span>⏹️</span>
                  <span>{t.stopAudio}</span>
                  <span className="flex h-1.5 w-1.5 rounded-full bg-rose-600 animate-ping ml-1" />
                </>
              ) : (
                <>
                  <span>🔊</span>
                  <span>{t.listenAloud}</span>
                </>
              )}
            </button>
            <span className="text-[10px] text-gray-400 font-medium">
              Sarvam Bulbul TTS
            </span>
          </div>
        )}

        {/* AGMARKNET Live Mandi Rates Card (if available) */}
        {isAssistant && message.adapterData?.live_records && message.adapterData.live_records.length > 0 && (
          <div className="mt-3 rounded-2xl border border-emerald-200 bg-emerald-50/60 p-3 text-xs">
            <div className="flex items-center justify-between font-bold text-emerald-950 mb-2">
              <span className="flex items-center gap-1.5">
                <span>🌾</span>
                <span>{t.mandiRatesTitle}: {message.adapterData.commodity}</span>
              </span>
              <span className="rounded bg-emerald-600 px-2 py-0.5 text-[10px] font-bold text-white">
                Live Mandi
              </span>
            </div>

            <div className="space-y-2">
              {message.adapterData.live_records.slice(0, 3).map((rec, i) => (
                <div key={i} className="rounded-xl border border-emerald-100 bg-white p-2.5 shadow-2xs">
                  <div className="flex items-center justify-between font-bold text-gray-900">
                    <span>{rec.market} ({rec.variety})</span>
                    <span className="text-emerald-800 text-sm">
                      ₹{rec.modal_price.toLocaleString("en-IN")}{" "}
                      <span className="text-[10px] font-normal text-gray-500">/{rec.price_unit || "Q"}</span>
                    </span>
                  </div>
                  <div className="mt-1 flex items-center justify-between text-[11px] text-gray-500">
                    <span>Min: ₹{rec.min_price} · Max: ₹{rec.max_price}</span>
                    <span>{rec.arrival_date}</span>
                  </div>
                </div>
              ))}
            </div>

            {message.adapterData.post_harvest_advice && (
              <p className="mt-2 text-[11px] text-emerald-900 bg-emerald-100/70 p-2 rounded-lg">
                💡 {message.adapterData.post_harvest_advice}
              </p>
            )}
          </div>
        )}

        {/* Live Weather Card (if available) */}
        {isAssistant && message.adapterData?.current_temp_c != null && (
          <div className="mt-3 rounded-2xl border border-sky-200 bg-sky-50/60 p-3 text-xs text-sky-950">
            <div className="flex items-center justify-between font-bold text-sky-950 mb-2">
              <span className="flex items-center gap-1.5">
                <span>🌦️</span>
                <span>{t.weatherTitle} ({message.adapterData.location || "Local"})</span>
              </span>
              <span className="rounded bg-sky-600 px-2 py-0.5 text-[10px] font-bold text-white">
                IMD / WMO
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-xl bg-white p-2 border border-sky-100 shadow-2xs">
                <span className="text-[10px] text-gray-500 block">{t.temperature}</span>
                <span className="font-bold text-sm text-sky-900">{message.adapterData.current_temp_c}°C</span>
              </div>
              <div className="rounded-xl bg-white p-2 border border-sky-100 shadow-2xs">
                <span className="text-[10px] text-gray-500 block">{t.humidity}</span>
                <span className="font-bold text-sm text-sky-900">{message.adapterData.humidity_pct}%</span>
              </div>
              <div className="rounded-xl bg-white p-2 border border-sky-100 shadow-2xs">
                <span className="text-[10px] text-gray-500 block">{t.windSpeed}</span>
                <span className="font-bold text-sm text-sky-900">{message.adapterData.wind_speed_kmh} km/h</span>
              </div>
            </div>
            {message.adapterData.spray_advisory && (
              <p className="mt-2 rounded-lg bg-white p-2 text-[11px] border border-sky-100 text-gray-800">
                🧪 <span className="font-bold">{t.chemicalSpray}:</span> {message.adapterData.spray_advisory}
              </p>
            )}
          </div>
        )}

        {/* Collapsible Verified Sources Accordion */}
        {isAssistant && message.retrievedDocuments && message.retrievedDocuments.length > 0 && (
          <div className="mt-2.5 pt-2 border-t border-emerald-100/70 text-xs">
            <button
              type="button"
              onClick={() => setSourcesOpen(!sourcesOpen)}
              className="flex items-center gap-1 text-[11px] font-bold text-emerald-800 hover:text-emerald-950"
            >
              <span>{sourcesOpen ? "▾" : "▸"}</span>
              <span>{t.sourcesVerified} ({message.retrievedDocuments.length})</span>
            </button>
            {sourcesOpen && (
              <ul className="mt-1.5 space-y-1 pl-2 text-[11px] text-gray-600">
                {message.retrievedDocuments.map((doc, idx) => (
                  <li key={idx} className="flex items-center justify-between gap-1">
                    <span className="line-clamp-1">• {doc.title} ({doc.source})</span>
                    {doc.url && (
                      <a
                        href={doc.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-emerald-700 font-bold underline shrink-0 ml-1"
                      >
                        ↗
                      </a>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {/* Farmer Feedback Widget (Thumbs Up / Thumbs Down) */}
        {isAssistant && (
          <div className="mt-3 pt-2.5 border-t border-emerald-100/70">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-medium text-gray-500">
                {rating ? t.feedbackThanks : t.feedbackPrompt}
              </span>
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  disabled={rating !== null || submittingFeedback}
                  onClick={() => handleSendFeedback("positive")}
                  aria-label={t.helpful}
                  title={t.helpful}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-xl text-xs font-semibold transition active:scale-95 disabled:cursor-default ${
                    rating === "positive"
                      ? "bg-emerald-100 text-emerald-800 border border-emerald-300 font-bold"
                      : rating === "negative"
                      ? "opacity-40 grayscale"
                      : "bg-emerald-50/70 text-emerald-900 border border-emerald-200/80 hover:bg-emerald-100/80"
                  }`}
                >
                  <span>👍</span>
                  <span className="hidden sm:inline text-[11px]">{t.helpful}</span>
                </button>
                <button
                  type="button"
                  disabled={rating !== null || submittingFeedback}
                  onClick={() => {
                    if (!rating) {
                      setCommentDrawerOpen(!commentDrawerOpen);
                    }
                  }}
                  aria-label={t.notHelpful}
                  title={t.notHelpful}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-xl text-xs font-semibold transition active:scale-95 disabled:cursor-default ${
                    rating === "negative"
                      ? "bg-rose-100 text-rose-800 border border-rose-300 font-bold"
                      : rating === "positive"
                      ? "opacity-40 grayscale"
                      : "bg-gray-50 text-gray-700 border border-gray-200 hover:bg-gray-100"
                  }`}
                >
                  <span>👎</span>
                  <span className="hidden sm:inline text-[11px]">{t.notHelpful}</span>
                </button>
              </div>
            </div>

            {/* Thumbs Down Comment Input Drawer */}
            {commentDrawerOpen && !rating && (
              <div className="mt-2.5 rounded-2xl bg-amber-50/60 p-3 border border-amber-200/70 text-xs">
                <label className="block text-[11px] font-semibold text-amber-950 mb-1">
                  {t.feedbackCommentPlaceholder}
                </label>
                <textarea
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value.slice(0, 500))}
                  placeholder={t.feedbackCommentPlaceholder}
                  rows={2}
                  maxLength={500}
                  className="w-full rounded-xl border border-amber-300/80 bg-white p-2 text-xs text-gray-900 focus:outline-hidden focus:ring-2 focus:ring-amber-500"
                />
                <div className="mt-1.5 flex items-center justify-between text-[10px] text-gray-500">
                  <span>{commentText.length} / 500</span>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setCommentDrawerOpen(false)}
                      className="px-2.5 py-1 rounded-lg text-gray-600 hover:bg-amber-100 font-medium transition"
                    >
                      {t.cancel}
                    </button>
                    <button
                      type="button"
                      disabled={submittingFeedback}
                      onClick={() => handleSendFeedback("negative", commentText)}
                      className="px-3 py-1 rounded-lg bg-amber-600 hover:bg-amber-700 text-white font-bold transition shadow-2xs disabled:opacity-50"
                    >
                      {submittingFeedback ? "..." : t.feedbackSubmit}
                    </button>
                  </div>
                </div>
                {feedbackError && (
                  <p className="mt-1 text-[11px] text-rose-600">{feedbackError}</p>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Farmer Avatar */}
      {!isAssistant && (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-emerald-800 text-white shadow-xs">
          <span className="text-sm font-bold" role="img" aria-label="Farmer User">
            👨‍🌾
          </span>
        </div>
      )}
    </div>
  );
};
