"use client";

import React from "react";
import { VoiceState, SupportedLanguage } from "../types";
import { translations } from "../lib/translations";
import { AudioVisualizer } from "./AudioVisualizer";

interface MicButtonProps {
  voiceState: VoiceState;
  recordingSeconds: number;
  onStartRecording: () => void;
  onStopRecording: () => void;
  disabled?: boolean;
  selectedLang: SupportedLanguage;
  stream?: MediaStream | null;
  isOffline?: boolean;
}

export const MicButton: React.FC<MicButtonProps> = ({
  voiceState,
  recordingSeconds,
  onStartRecording,
  onStopRecording,
  disabled = false,
  selectedLang,
  stream = null,
  isOffline = false,
}) => {
  const t = translations[selectedLang];

  const formatSeconds = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const remaining = sec % 60;
    return `${mins}:${remaining < 10 ? "0" : ""}${remaining}`;
  };

  const isButtonDisabled = disabled || isOffline || voiceState === "processing";

  return (
    <div className="flex flex-col items-center justify-center">
      {/* Visual Status Indicator Text */}
      <div className="mb-1.5 h-5 text-center">
        {voiceState === "recording" && (
          <div className="inline-flex items-center gap-1.5 rounded-full bg-rose-100 px-3 py-0.5 text-xs font-bold text-rose-800 animate-pulse">
            <span className="h-2 w-2 rounded-full bg-rose-600 animate-ping" />
            <span>{t.listening} ({formatSeconds(recordingSeconds)})</span>
          </div>
        )}
        {voiceState === "processing" && (
          <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-0.5 text-xs font-bold text-emerald-800">
            <svg className="h-3 w-3 animate-spin text-emerald-700" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            <span>{t.processingVoice}</span>
          </div>
        )}
        {voiceState === "idle" && (
          <span className="text-xs font-medium text-gray-500">
            {isOffline ? "Offline — reconnect to speak" : t.tapToSpeak}
          </span>
        )}
      </div>

      {/* Live Audio Spectrum Waveform Visualizer during recording */}
      {voiceState === "recording" && (
        <AudioVisualizer stream={stream} isRecording={true} />
      )}

      {/* Main Circular Button with Concentric Animated Rings */}
      <div className="relative flex items-center justify-center">
        {/* Pulsing Concentric Ripple Rings in Recording State */}
        {voiceState === "recording" && (
          <>
            <span className="absolute h-24 w-24 rounded-full bg-rose-500/20 animate-ping" />
            <span className="absolute h-20 w-20 rounded-full bg-rose-400/30 animate-pulse" />
          </>
        )}

        {/* Ambient Ring in Idle State */}
        {voiceState === "idle" && !isButtonDisabled && (
          <span className="absolute h-18 w-18 rounded-full bg-emerald-500/10 transition-transform duration-500 hover:scale-110" />
        )}

        <button
          type="button"
          onClick={voiceState === "recording" ? onStopRecording : onStartRecording}
          disabled={isButtonDisabled}
          title={isOffline ? "Offline — reconnect to ask new questions." : undefined}
          aria-label={
            isOffline
              ? "Offline"
              : voiceState === "recording"
              ? t.tapToStop
              : voiceState === "processing"
              ? t.processingVoice
              : t.tapToSpeak
          }
          className={`relative z-10 flex h-16 w-16 items-center justify-center rounded-full shadow-lg transition-all duration-300 focus:outline-none focus:ring-4 ${
            isOffline
              ? "bg-gray-300 text-gray-500 shadow-none cursor-not-allowed"
              : voiceState === "recording"
              ? "bg-rose-600 text-white shadow-rose-600/40 hover:bg-rose-700 focus:ring-rose-300 active:scale-95 animate-bounce-subtle"
              : voiceState === "processing"
              ? "bg-emerald-800 text-white shadow-emerald-800/30 cursor-wait opacity-90"
              : "bg-gradient-to-tr from-emerald-600 to-green-500 text-white shadow-emerald-600/35 hover:scale-105 hover:from-emerald-700 hover:to-green-600 focus:ring-emerald-300 active:scale-95"
          } ${isButtonDisabled ? "opacity-50 cursor-not-allowed" : ""}`}
        >
          {voiceState === "recording" ? (
            /* Stop Square Icon */
            <svg className="h-7 w-7 text-white" fill="currentColor" viewBox="0 0 24 24">
              <rect x="6" y="6" width="12" height="12" rx="2" />
            </svg>
          ) : voiceState === "processing" ? (
            /* Spinner */
            <svg className="h-7 w-7 animate-spin text-white" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
          ) : (
            /* Microphone SVG Icon */
            <svg className="h-8 w-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2.2"
                d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
              />
            </svg>
          )}
        </button>
      </div>

      {/* Button Sub-Label */}
      <span className="mt-1.5 text-[11px] font-bold text-emerald-950">
        {isOffline
          ? "Offline"
          : voiceState === "recording"
          ? t.tapToStop
          : voiceState === "processing"
          ? t.processingVoice
          : t.tapToSpeak}
      </span>
    </div>
  );
};
