"use client";

import React, { useState, useEffect, useRef, useCallback } from "react";
import { Header } from "./components/Header";
import { MicButton } from "./components/MicButton";
import { WelcomeCard } from "./components/WelcomeCard";
import { MessageItem } from "./components/MessageItem";
import { ConfirmModal } from "./components/ConfirmModal";
import { InstallBanner } from "./components/InstallBanner";
import { SavedGuidanceModal } from "./components/SavedGuidanceModal";
import {
  saveLastConversation,
  getLastConversation,
  clearLastConversation,
} from "./lib/offline-storage";
import {
  SupportedLanguage,
  ChatMessage,
  ApiResponse,
  VoiceState,
} from "./types";
import { translations } from "./lib/translations";

export default function Home() {
  const [selectedLang, setSelectedLang] = useState<SupportedLanguage>("en");
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved =
          sessionStorage.getItem("farmsaathi_messages") ||
          localStorage.getItem("farmsaathi_persisted_messages");
        if (saved) {
          const parsed = JSON.parse(saved);
          if (Array.isArray(parsed)) return parsed;
        }
      } catch {
        return [];
      }
    }
    return [];
  });
  const [inputText, setInputText] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      try {
        return (
          sessionStorage.getItem("farmsaathi_session_id") ||
          localStorage.getItem("farmsaathi_persisted_session_id")
        );
      } catch {
        return null;
      }
    }
    return null;
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isBackendOnline, setIsBackendOnline] = useState(true);
  const [isOffline, setIsOffline] = useState(() => {
    if (typeof window !== "undefined") {
      return !navigator.onLine;
    }
    return false;
  });
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [isSavedGuidanceModalOpen, setIsSavedGuidanceModalOpen] = useState(false);

  // Restore conversation from IndexedDB if initial state was empty
  useEffect(() => {
    if (messages.length === 0) {
      getLastConversation().then((cached) => {
        if (cached && Array.isArray(cached.messages) && cached.messages.length > 0) {
          const tagged = cached.messages.map((m) => ({ ...m, isCached: true }));
          setMessages(tagged);
          if (cached.sessionId && !sessionId) {
            setSessionId(cached.sessionId);
          }
          if (cached.selectedLang) {
            setSelectedLang(cached.selectedLang);
          }
        }
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Microphone and voice recording states
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [activePlayingId, setActivePlayingId] = useState<string | null>(null);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [isSynthesizingId, setIsSynthesizingId] = useState<string | null>(null);

  // Refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const currentAudioUrlRef = useRef<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const recordingFormatRef = useRef<{ mimeType: string; fileExt: string }>({
    mimeType: "audio/webm",
    fileExt: "webm",
  });

  const t = translations[selectedLang];

  // Auto-scroll chat area to bottom when messages update
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  // Online / Offline window listeners
  useEffect(() => {
    const handleOnline = () => {
      setIsOffline(false);
      setError(null);
    };
    const handleOffline = () => {
      setIsOffline(true);
      if (audioPlayerRef.current) {
        audioPlayerRef.current.pause();
      }
      setIsPlayingAudio(false);
      setActivePlayingId(null);
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  // Check backend connectivity periodically while online
  useEffect(() => {
    if (isOffline) return;

    async function checkHealth() {
      try {
        const res = await fetch("/api/health");
        if (res.ok) {
          setIsBackendOnline(true);
        } else {
          setIsBackendOnline(false);
        }
      } catch {
        setIsBackendOnline(false);
      }
    }
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, [isOffline]);

  // Cleanup audio tracks and object URLs on unmount
  useEffect(() => {
    return () => {
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (currentAudioUrlRef.current) {
        URL.revokeObjectURL(currentAudioUrlRef.current);
      }
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
      }
    };
  }, []);

  // Format current local time for message bubble timestamps
  const getCurrentTimeFormatted = () => {
    return new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Helper to persist messages safely (stripping bulky audioBase64 to protect storage quotas)
  const updateMessagesAndStorage = (updater: (prev: ChatMessage[]) => ChatMessage[]) => {
    setMessages((prev) => {
      const next = updater(prev);
      try {
        const sanitized = next.map((msg) => {
          const copy = { ...msg };
          delete copy.audioBase64;
          return copy;
        });
        const serialized = JSON.stringify(sanitized);
        sessionStorage.setItem("farmsaathi_messages", serialized);
        localStorage.setItem("farmsaathi_persisted_messages", serialized);
      } catch {
        // Storage quota exceeded or disabled
      }
      // Asynchronously persist to browser IndexedDB for offline conversation restoration
      saveLastConversation(next, sessionId, selectedLang).catch((err) => {
        console.warn("[OfflineStorage] Could not persist to IndexedDB:", err);
      });
      return next;
    });
  };

  // Helper to update session ID
  const updateSessionId = (newId: string | null) => {
    setSessionId(newId);
    try {
      if (newId) {
        sessionStorage.setItem("farmsaathi_session_id", newId);
        localStorage.setItem("farmsaathi_persisted_session_id", newId);
      } else {
        sessionStorage.removeItem("farmsaathi_session_id");
        localStorage.removeItem("farmsaathi_persisted_session_id");
      }
    } catch {
      // Storage disabled
    }
  };

  // Stop any active audio playback and revoke object URL
  const stopAudioPlayback = useCallback(() => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current = null;
    }
    if (currentAudioUrlRef.current) {
      URL.revokeObjectURL(currentAudioUrlRef.current);
      currentAudioUrlRef.current = null;
    }
    setIsPlayingAudio(false);
    setActivePlayingId(null);
  }, []);

  // Play audio response with Blob / ObjectURL + fallback synthesis
  const handlePlayAudio = useCallback(
    async (
      messageId: string,
      text: string,
      audioBase64?: string,
      audioFormat = "wav"
    ) => {
      if (isOffline) {
        setError("Audio playback is unavailable while offline.");
        return;
      }

      // If clicking the currently playing message, toggle pause/play
      if (audioPlayerRef.current && activePlayingId === messageId) {
        if (isPlayingAudio) {
          audioPlayerRef.current.pause();
          setIsPlayingAudio(false);
          return;
        } else {
          try {
            await audioPlayerRef.current.play();
            setIsPlayingAudio(true);
            return;
          } catch {
            // Replay failed; proceed to re-create audio
          }
        }
      }

      // Stop any existing playback
      stopAudioPlayback();

      let base64ToPlay = audioBase64;
      let formatToUse = audioFormat;

      // Fallback: If audioBase64 is missing, fetch on-demand from /api/voice/synthesize
      if (!base64ToPlay && text) {
        try {
          setIsSynthesizingId(messageId);
          const synthRes = await fetch("/api/voice/synthesize", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              text: text.slice(0, 800),
              language_code: selectedLang,
            }),
          });

          if (!synthRes.ok) {
            let detailMsg = "Spoken audio is currently unavailable. Please read the response text guidance.";
            if (synthRes.status === 402) {
              detailMsg = "Spoken audio unavailable: Sarvam AI credits exhausted. Please read the response text guidance.";
            } else if (synthRes.status === 401) {
              detailMsg = "Spoken audio unavailable: Sarvam AI credentials invalid. Please read the response text guidance.";
            } else if (synthRes.status === 429) {
              detailMsg = "Spoken audio rate limit reached. Please wait a moment.";
            }
            throw new Error(detailMsg);
          }

          const synthData = await synthRes.json();
          if (synthData.audio_base64) {
            base64ToPlay = synthData.audio_base64;
            formatToUse = synthData.format || "wav";

            // Cache generated audioBase64 in memory state
            setMessages((prev) =>
              prev.map((m) =>
                m.id === messageId
                  ? { ...m, audioBase64: base64ToPlay, audioFormat: formatToUse }
                  : m
              )
            );
          }
        } catch (synthErr) {
          console.warn("TTS synthesis fallback error:", synthErr);
          const errorMsg =
            synthErr instanceof Error
              ? synthErr.message
              : "Spoken audio is currently unavailable. Please read the response text guidance.";
          setError(errorMsg);
          setIsSynthesizingId(null);
          return;
        } finally {
          setIsSynthesizingId(null);
        }
      }

      if (!base64ToPlay) return;

      try {
        const mime =
          formatToUse === "mp3"
            ? "audio/mpeg"
            : formatToUse === "ogg"
            ? "audio/ogg"
            : "audio/wav";

        // Sanitize base64 string (strip data-URI header and whitespace if present)
        const rawBase64 = base64ToPlay.includes(",")
          ? base64ToPlay.split(",")[1]
          : base64ToPlay;
        const cleanBase64 = rawBase64.replace(/\s+/g, "");
        const byteCharacters = atob(cleanBase64);
        const byteNumbers = new Uint8Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i++) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const audioBlob = new Blob([byteNumbers], { type: mime });
        const objectUrl = URL.createObjectURL(audioBlob);
        currentAudioUrlRef.current = objectUrl;

        const player = new Audio(objectUrl);
        audioPlayerRef.current = player;
        setActivePlayingId(messageId);
        setIsPlayingAudio(true);

        player.onended = () => {
          stopAudioPlayback();
        };

        player.onerror = () => {
          console.warn("Audio element error during playback");
          stopAudioPlayback();
        };

        try {
          await player.play();
        } catch (playErr) {
          console.warn("Autoplay or audio play restriction:", playErr);
          stopAudioPlayback();
        }
      } catch (err) {
        console.warn("Audio playback error:", err);
        stopAudioPlayback();
      }
    },
    [activePlayingId, isPlayingAudio, isOffline, selectedLang, stopAudioPlayback]
  );

  // Submit Text Query
  async function submitQuestion(overrideText?: string) {
    if (isOffline) {
      setError("Offline — reconnect to ask new questions.");
      return;
    }

    const textToSend = (overrideText || inputText).trim();
    if (!textToSend || loading || voiceState !== "idle") return;

    setError(null);
    setInputText("");

    // Create user message
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: "farmer",
      text: textToSend,
      timestamp: getCurrentTimeFormatted(),
      isVoice: false,
    };

    updateMessagesAndStorage((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      let response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: textToSend,
          session_id: sessionId,
          preferred_language: selectedLang,
          mode: "auto",
        }),
      });

      // If server is waking up from sleep (HTTP 502/503/504), perform one bounded retry after brief backoff
      if (response.status >= 502 && response.status <= 504 && !isOffline) {
        setError("FarmSaathi server is waking up, retrying your question in a moment...");
        await new Promise((res) => setTimeout(res, 2500));
        response = await fetch("/api/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: textToSend,
            session_id: sessionId,
            preferred_language: selectedLang,
            mode: "auto",
          }),
        });
        if (response.ok) {
          setError(null);
        }
      }

      const data: ApiResponse = await response.json();
      if (!response.ok) {
        // Handle expired session safely
        if (response.status === 404 || response.status === 400) {
          updateSessionId(null);
        }
        throw new Error(
          (data as { detail?: string }).detail || "Unable to retrieve guidance. Please try again."
        );
      }

      if (data.session_id) {
        updateSessionId(data.session_id);
      }

      // Create assistant message
      const assistantMessage: ChatMessage = {
        id: `assistant-${Date.now()}`,
        sender: "assistant",
        text: data.answer,
        timestamp: getCurrentTimeFormatted(),
        sources: data.sources,
        audioBase64: data.audio_base64,
        audioFormat: data.audio_format || "wav",
        retrievedDocuments: data.retrieved_documents,
        adapterData: data.adapter_data,
        entities: data.entities,
        intent: data.intent,
        messageId: data.message_id,
        sessionId: data.session_id,
      };

      updateMessagesAndStorage((prev) => [...prev, assistantMessage]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Connection failed. Please check backend connection."
      );
    } finally {
      setLoading(false);
    }
  }

  // Start Voice Recording via MediaRecorder with low-bandwidth opus bitrate
  async function handleStartRecording() {
    if (isOffline) {
      setError("Offline — reconnect to ask new questions.");
      return;
    }

    if (loading || voiceState !== "idle") return;
    setError(null);

    // Stop currently playing audio
    stopAudioPlayback();

    // Check browser MediaRecorder and mediaDevices support
    if (
      typeof window === "undefined" ||
      !navigator?.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      setError(t.micUnsupported);
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioStreamRef.current = stream;
      audioChunksRef.current = [];

      // Detect best supported audio MIME type across browsers (Chrome, Safari, iOS, Android, Firefox)
      const candidateTypes: Array<{ mime: string; ext: string }> = [
        { mime: "audio/webm;codecs=opus", ext: "webm" },
        { mime: "audio/webm", ext: "webm" },
        { mime: "audio/ogg;codecs=opus", ext: "ogg" },
        { mime: "audio/mp4", ext: "mp4" },
        { mime: "audio/aac", ext: "aac" },
        { mime: "audio/wav", ext: "wav" },
      ];

      let selectedCandidate: { mime: string; ext: string } | null = null;
      if (typeof MediaRecorder.isTypeSupported === "function") {
        for (const candidate of candidateTypes) {
          if (MediaRecorder.isTypeSupported(candidate.mime)) {
            selectedCandidate = candidate;
            break;
          }
        }
      }

      const mimeType = selectedCandidate ? selectedCandidate.mime : "";
      const fileExt = selectedCandidate ? selectedCandidate.ext : "wav";
      recordingFormatRef.current = { mimeType: mimeType || "audio/webm", fileExt };

      let mediaRecorder: MediaRecorder;
      try {
        if (mimeType) {
          mediaRecorder = new MediaRecorder(stream, {
            mimeType,
            audioBitsPerSecond: 24000,
          });
        } else {
          mediaRecorder = new MediaRecorder(stream);
        }
      } catch {
        try {
          if (mimeType) {
            mediaRecorder = new MediaRecorder(stream, { mimeType });
          } else {
            mediaRecorder = new MediaRecorder(stream);
          }
        } catch {
          // Native browser recorder without custom options (safest for mobile Safari)
          mediaRecorder = new MediaRecorder(stream);
        }
      }

      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        // Release mic tracks immediately
        stream.getTracks().forEach((track) => track.stop());
        audioStreamRef.current = null;

        const chunks = audioChunksRef.current;
        const totalSize = chunks.reduce((acc, chunk) => acc + chunk.size, 0);

        // Handle empty or too small recordings (< 150 bytes)
        if (chunks.length === 0 || totalSize < 150) {
          setError(t.emptyRecording);
          setVoiceState("idle");
          return;
        }

        const audioBlob = new Blob(chunks, { type: mimeType });
        await processRecordedAudio(audioBlob, fileExt);
      };

      mediaRecorder.start(250); // collect timeslices every 250ms
      setVoiceState("recording");
      setRecordingSeconds(0);

      // Auto-stop timer after 60 seconds
      timerIntervalRef.current = setInterval(() => {
        setRecordingSeconds((prev) => {
          if (prev >= 60) {
            handleStopRecording();
            return 60;
          }
          return prev + 1;
        });
      }, 1000);
    } catch (err: unknown) {
      if (audioStreamRef.current) {
        audioStreamRef.current.getTracks().forEach((track) => track.stop());
        audioStreamRef.current = null;
      }
      setVoiceState("idle");
      const errorObj = err as { name?: string; message?: string };
      if (
        errorObj.name === "NotAllowedError" ||
        errorObj.name === "PermissionDeniedError"
      ) {
        setError(t.micDenied);
      } else if (
        errorObj.name === "NotFoundError" ||
        errorObj.name === "DevicesNotFoundError"
      ) {
        setError(t.noMicAvailable);
      } else {
        setError(t.micDenied);
      }
    }
  }

  // Stop Voice Recording
  function handleStopRecording() {
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }

    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      setVoiceState("processing");
      try {
        mediaRecorderRef.current.stop();
      } catch (e) {
        console.warn("Error stopping media recorder:", e);
        setVoiceState("idle");
      }
    } else {
      setVoiceState("idle");
    }
  }

  // Process Recorded Audio via /api/ask-voice with network timeout handling
  async function processRecordedAudio(blob: Blob, fileExt: string) {
    if (isOffline) {
      setError("Offline — reconnect to ask new questions.");
      setVoiceState("idle");
      return;
    }

    try {
      const reader = new FileReader();
      reader.readAsDataURL(blob);
      reader.onloadend = async () => {
        const resultStr = reader.result as string;
        const base64Data = resultStr ? resultStr.split(",")[1] : "";
        if (!base64Data) {
          setError(t.emptyRecording);
          setVoiceState("idle");
          return;
        }

        // 45-second network abort controller for slow rural connections and cold starts
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 45000);

        try {
          const response = await fetch("/api/ask-voice", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            signal: controller.signal,
            body: JSON.stringify({
              audio_base64: base64Data,
              filename: `recording.${fileExt}`,
              session_id: sessionId,
              language_hint: selectedLang,
            }),
          });
          clearTimeout(timeoutId);

          const data = await response.json();

          if (!response.ok) {
            let errorMsg = t.voiceError;
            if (response.status === 400) {
              errorMsg = t.emptyTranscript;
            } else if (response.status === 404) {
              updateSessionId(null);
              errorMsg = "Previous session expired. Please tap the microphone again to ask your question.";
            } else if (response.status === 429) {
              errorMsg = t.rateLimited;
            } else if (response.status === 502 || response.status === 504) {
              errorMsg = t.backendUnavailable;
            } else if (data.detail && typeof data.detail === "string") {
              errorMsg = data.detail;
            }
            throw new Error(errorMsg);
          }

          const recognizedText = data.transcript || data.question || "Spoken query";
          const answerText = data.answer || data.analysis?.answer || "No response received.";

          // Persist session ID
          if (data.session_id) {
            updateSessionId(data.session_id);
          }

          const currentTime = getCurrentTimeFormatted();

          // User turn
          const userMsg: ChatMessage = {
            id: `user-voice-${Date.now()}`,
            sender: "farmer",
            text: recognizedText,
            timestamp: currentTime,
            isVoice: true,
            transcript: recognizedText,
          };

          // Assistant turn
          const assistantMsg: ChatMessage = {
            id: `assistant-voice-${Date.now() + 1}`,
            sender: "assistant",
            text: answerText,
            timestamp: currentTime,
            isVoice: true,
            sources: data.sources || data.analysis?.sources,
            audioBase64: data.audio_base64,
            audioFormat: data.audio_format || "wav",
            retrievedDocuments: data.retrieved_documents || data.analysis?.retrieved_documents,
            adapterData: data.adapter_data || data.analysis?.adapter_data,
            entities: data.entities || data.analysis?.entities,
            intent: data.intent || data.analysis?.intent,
            messageId: data.message_id || data.analysis?.message_id,
            sessionId: data.session_id || sessionId || undefined,
          };

          updateMessagesAndStorage((prev) => [...prev, userMsg, assistantMsg]);

          // Automatically play audio response if returned
          if (data.audio_base64) {
            handlePlayAudio(
              assistantMsg.id,
              assistantMsg.text,
              data.audio_base64,
              data.audio_format || "wav"
            );
          }
        } catch (fetchErr: unknown) {
          clearTimeout(timeoutId);
          const isAbort = (fetchErr as { name?: string }).name === "AbortError";
          const msg = isAbort
            ? "Voice upload timed out on slow network. Please check your connection and tap mic again."
            : fetchErr instanceof Error
            ? fetchErr.message
            : t.voiceError;
          setError(msg);
        } finally {
          setVoiceState("idle");
        }
      };

      reader.onerror = () => {
        setError(t.voiceError);
        setVoiceState("idle");
      };
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t.voiceError);
      setVoiceState("idle");
    }
  }

  // Clear conversation & start new session
  function handleConfirmNewChat() {
    stopAudioPlayback();
    if (timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach((track) => track.stop());
      audioStreamRef.current = null;
    }

    setMessages([]);
    updateSessionId(null);
    setInputText("");
    setError(null);
    setVoiceState("idle");
    setRecordingSeconds(0);
    setIsConfirmModalOpen(false);

    clearLastConversation().catch(() => {});

    try {
      sessionStorage.removeItem("farmsaathi_messages");
      sessionStorage.removeItem("farmsaathi_session_id");
      localStorage.removeItem("farmsaathi_persisted_messages");
      localStorage.removeItem("farmsaathi_persisted_session_id");
    } catch {
      // Storage unavailable
    }
  }

  return (
    <div className="flex h-screen max-h-screen w-full flex-col bg-gradient-to-b from-emerald-50/50 via-white to-emerald-50/30 text-gray-900 font-sans antialiased overflow-hidden">
      {/* PWA Install Banner */}
      <InstallBanner selectedLang={selectedLang} />

      {/* Offline Alert Strip */}
      {isOffline && (
        <div
          role="status"
          className="bg-amber-600 text-white px-3 sm:px-4 py-2 text-xs font-bold shadow-xs animate-fade-in"
        >
          <div className="mx-auto max-w-4xl flex flex-col sm:flex-row items-center justify-between gap-1.5 text-center sm:text-left">
            <div className="flex items-center gap-1.5 flex-wrap justify-center sm:justify-start">
              <span className="text-sm">⚠️</span>
              <span className="font-extrabold uppercase tracking-wide">
                Offline — reconnect to ask new questions
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setIsSavedGuidanceModalOpen(true)}
                className="rounded-lg bg-amber-700/80 hover:bg-amber-800 px-2 py-0.5 text-2xs text-amber-100 font-bold border border-amber-500/60 transition"
              >
                🔖 {t.savedGuidance || "Saved Guidance"}
              </button>
            </div>
          </div>
          <p className="mx-auto max-w-4xl text-[10px] text-amber-100 font-normal mt-0.5 text-center sm:text-left">
            {t.offlineAdvisory ||
              "Live voice input, speech synthesis (Sarvam AI), and real-time mandi/weather data require an internet connection. You can still read past answers and browse your saved guidance."}
          </p>
        </div>
      )}

      {/* Sticky Header */}
      <Header
        selectedLang={selectedLang}
        onLanguageChange={setSelectedLang}
        isBackendOnline={isBackendOnline}
        onNewChat={() => setIsConfirmModalOpen(true)}
        hasMessages={messages.length > 0}
        isOffline={isOffline}
        onOpenSavedGuidance={() => setIsSavedGuidanceModalOpen(true)}
      />

      {/* Main Conversation Feed */}
      <main className="flex-1 overflow-y-auto px-3 sm:px-6 py-4">
        <div className="mx-auto max-w-2xl">
          {/* Empty Conversation Welcome State */}
          {messages.length === 0 && (
            <WelcomeCard
              selectedLang={selectedLang}
              onSelectSuggestion={(q) => submitQuestion(q)}
              disabled={loading || voiceState !== "idle" || isOffline}
            />
          )}

          {/* Active Messages List (Readable even when offline!) */}
          {messages.map((msg) => (
            <MessageItem
              key={msg.id}
              message={msg}
              selectedLang={selectedLang}
              onPlayAudio={handlePlayAudio}
              isPlaying={isPlayingAudio}
              activePlayingId={activePlayingId}
              isSynthesizingId={isSynthesizingId}
              sessionId={sessionId}
              onFeedbackSubmitted={(msgId, r, c) => {
                updateMessagesAndStorage((prev) =>
                  prev.map((m) =>
                    m.id === msgId ? { ...m, feedbackRating: r, feedbackComment: c } : m
                  )
                );
              }}
            />
          ))}

          {/* Loading Indicator Bubble */}
          {loading && (
            <div className="flex w-full items-center gap-2.5 my-3 justify-start animate-fade-in">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-2xl bg-emerald-700 text-white shadow-xs">
                <span className="text-base">🌾</span>
              </div>
              <div className="flex items-center gap-2 rounded-3xl rounded-tl-sm border border-emerald-100 bg-white px-4 py-3 shadow-xs">
                <span className="flex h-2 w-2 rounded-full bg-emerald-600 animate-ping" />
                <span className="text-xs font-bold text-emerald-900">
                  {t.thinking}
                </span>
              </div>
            </div>
          )}

          {/* Scroll anchor */}
          <div ref={messagesEndRef} className="h-2" />
        </div>
      </main>

      {/* Error Alert Toast (if present) */}
      {error && !isOffline && (
        <div className="mx-auto max-w-xl px-4 pb-2 w-full animate-fade-in">
          <div
            role="alert"
            className="flex items-start justify-between gap-2 rounded-2xl border border-red-200 bg-red-50 p-3 text-xs text-red-800 shadow-sm"
          >
            <div className="flex items-start gap-2">
              <span className="text-base shrink-0">⚠️</span>
              <div>
                <span className="font-bold">{t.errorPrefix}: </span>
                <span>{error}</span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setError(null)}
              className="text-red-600 hover:text-red-900 font-black text-sm shrink-0 px-1"
              aria-label="Dismiss error"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Bottom Sticky Action Area: Microphone & Text Input */}
      <footer className="border-t border-emerald-100 bg-white/95 px-3 sm:px-6 pt-2.5 sm:pt-3 pb-3 sm:pb-5 shadow-lg backdrop-blur-md w-full shrink-0">
        <div className="mx-auto max-w-2xl w-full flex flex-col items-center gap-2 sm:gap-3">
          {/* Prominent Circular Microphone Button */}
          <MicButton
            voiceState={voiceState}
            recordingSeconds={recordingSeconds}
            onStartRecording={handleStartRecording}
            onStopRecording={handleStopRecording}
            disabled={loading || isOffline}
            selectedLang={selectedLang}
            stream={audioStreamRef.current}
            isOffline={isOffline}
          />

          {/* Fallback Text Input Form */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              submitQuestion();
            }}
            className="flex w-full items-center gap-2"
          >
            <div className="relative flex-1 min-w-0">
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={
                  isOffline
                    ? "Offline — reconnect to ask new questions."
                    : t.placeholder
                }
                disabled={loading || voiceState !== "idle" || isOffline}
                className="w-full rounded-2xl border border-emerald-200 bg-emerald-50/40 px-3 sm:px-4 py-2.5 sm:py-3 text-xs sm:text-sm text-gray-900 shadow-inner outline-none transition focus:border-emerald-600 focus:bg-white focus:ring-2 focus:ring-emerald-200 disabled:opacity-50"
              />
            </div>

            <button
              type="submit"
              disabled={loading || voiceState !== "idle" || !inputText.trim() || isOffline}
              className="flex h-10 sm:h-11 items-center justify-center rounded-2xl bg-emerald-700 px-3.5 sm:px-5 font-bold text-white shadow-md transition hover:bg-emerald-800 active:scale-95 disabled:cursor-not-allowed disabled:opacity-50 text-xs sm:text-sm shrink-0"
              aria-label={t.send}
            >
              <span>{t.send}</span>
              <span className="ml-1">→</span>
            </button>
          </form>
        </div>
      </footer>

      {/* New Chat Confirmation Modal */}
      <ConfirmModal
        isOpen={isConfirmModalOpen}
        onConfirm={handleConfirmNewChat}
        onCancel={() => setIsConfirmModalOpen(false)}
        selectedLang={selectedLang}
      />

      {/* Saved Offline Guidance Modal */}
      <SavedGuidanceModal
        isOpen={isSavedGuidanceModalOpen}
        onClose={() => setIsSavedGuidanceModalOpen(false)}
        selectedLang={selectedLang}
      />
    </div>
  );
}
