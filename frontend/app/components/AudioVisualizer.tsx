"use client";

import React, { useEffect, useRef } from "react";

interface AudioVisualizerProps {
  stream: MediaStream | null;
  isRecording: boolean;
}

export const AudioVisualizer: React.FC<AudioVisualizerProps> = ({
  stream,
  isRecording,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);

  useEffect(() => {
    if (!isRecording || !stream) {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close().catch(() => {});
        audioContextRef.current = null;
      }
      return;
    }

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Check prefers-reduced-motion
    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (prefersReducedMotion) {
      // Draw static ambient indicator
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "#059669";
      ctx.fillRect(canvas.width / 2 - 20, canvas.height / 2 - 2, 40, 4);
      return;
    }

    let isSubscribed = true;

    try {
      const AudioContextClass =
        window.AudioContext ||
        (window as unknown as { webkitAudioContext: typeof AudioContext })
          .webkitAudioContext;

      if (!AudioContextClass) return;

      const audioCtx = new AudioContextClass();
      audioContextRef.current = audioCtx;

      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 64;
      analyser.smoothingTimeConstant = 0.8;

      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      const draw = () => {
        if (!isSubscribed) return;

        animationFrameRef.current = requestAnimationFrame(draw);
        analyser.getByteFrequencyData(dataArray);

        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const barCount = 18;
        const barWidth = 4;
        const barGap = 3;
        const totalWidth = barCount * barWidth + (barCount - 1) * barGap;
        const startX = (canvas.width - totalWidth) / 2;

        for (let i = 0; i < barCount; i++) {
          const sampleIndex = Math.floor((i / barCount) * (bufferLength / 2));
          const val = dataArray[sampleIndex] || 0;
          const barHeight = Math.max(3, (val / 255) * (canvas.height - 4));

          const x = startX + i * (barWidth + barGap);
          const y = (canvas.height - barHeight) / 2;

          const gradient = ctx.createLinearGradient(0, y, 0, y + barHeight);
          gradient.addColorStop(0, "#34d399"); // emerald-400
          gradient.addColorStop(1, "#059669"); // emerald-600

          ctx.fillStyle = gradient;
          ctx.beginPath();
          ctx.roundRect(x, y, barWidth, barHeight, 2);
          ctx.fill();
        }
      };

      draw();
    } catch (e) {
      console.warn("[Visualizer] Web Audio API init error:", e);
    }

    return () => {
      isSubscribed = false;
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      if (audioContextRef.current && audioContextRef.current.state !== "closed") {
        audioContextRef.current.close().catch(() => {});
        audioContextRef.current = null;
      }
    };
  }, [isRecording, stream]);

  if (!isRecording) return null;

  return (
    <div className="flex flex-col items-center justify-center my-1 animate-fade-in">
      <canvas
        ref={canvasRef}
        width={180}
        height={32}
        className="rounded-lg bg-emerald-50/70 border border-emerald-200/50 shadow-inner"
        aria-label="Live audio frequency waveform"
      />
    </div>
  );
};
