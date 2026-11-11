"use client";

import React, { useState } from "react";
import { ReviewRecordItem } from "../../types";

interface QueryDetailModalProps {
    query: ReviewRecordItem | null;
    onClose: () => void;
    onStatusUpdate: (
        queryId: string,
        status: "approved" | "rejected" | "corrected",
        notes: string,
        correctedAnswer?: string
    ) => Promise<void>;
    isUpdating: boolean;
}

export function QueryDetailModal({
    query,
    onClose,
    onStatusUpdate,
    isUpdating,
}: QueryDetailModalProps) {
    const [notes, setNotes] = useState(query?.reviewer_notes || "");
    const [correctedAnswer, setCorrectedAnswer] = useState(query?.corrected_answer || "");
    const [actionError, setActionError] = useState<string | null>(null);

    if (!query) return null;

    const handleAction = async (status: "approved" | "rejected" | "corrected") => {
        setActionError(null);
        if (status === "corrected" && !correctedAnswer.trim()) {
            setActionError("Please provide the corrected agricultural guidance text before submitting.");
            return;
        }

        try {
            await onStatusUpdate(
                query.review_id,
                status,
                notes.trim(),
                status === "corrected" ? correctedAnswer.trim() : undefined
            );
            onClose();
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : "Failed to update review status.";
            setActionError(msg);
        }
    };

    const statusBadges: Record<string, { bg: string; text: string; label: string }> = {
        pending: { bg: "bg-amber-50 border-amber-200", text: "text-amber-800", label: "Pending Review" },
        approved: { bg: "bg-emerald-50 border-emerald-200", text: "text-emerald-800", label: "Verified & Approved" },
        corrected: { bg: "bg-blue-50 border-blue-200", text: "text-blue-800", label: "Expert Corrected" },
        rejected: { bg: "bg-rose-50 border-rose-200", text: "text-rose-800", label: "Rejected" },
    };

    const currentBadge = statusBadges[query.status] || statusBadges.pending;

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/60 flex items-center justify-center p-4 sm:p-6">
            <div
                className="bg-white rounded-2xl max-w-3xl w-full shadow-2xl border border-gray-200 overflow-hidden transform transition-all my-8"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="bg-emerald-950 text-white px-6 py-4 flex items-center justify-between">
                    <div>
                        <div className="flex items-center gap-2.5">
                            <span className="font-mono text-xs text-emerald-300 font-semibold">
                                {query.review_id}
                            </span>
                            <span
                                className={`text-[11px] px-2 py-0.5 rounded-full font-semibold border ${currentBadge.bg} ${currentBadge.text}`}
                            >
                                {currentBadge.label}
                            </span>
                        </div>
                        <h2 className="text-sm font-bold text-white mt-1">
                            Agricultural Review & Verification Console
                        </h2>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-emerald-300 hover:text-white p-1 rounded-md transition-colors"
                        aria-label="Close modal"
                    >
                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto text-xs">
                    {actionError && (
                        <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium">
                            {actionError}
                        </div>
                    )}

                    {/* Metadata Strip */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-gray-50 p-3.5 rounded-xl border border-gray-200">
                        <div>
                            <span className="text-[10px] uppercase font-bold text-gray-500 block">Intent Domain</span>
                            <span className="font-semibold text-gray-800 capitalize mt-0.5 block">
                                {query.intent.replace("_", " ")}
                            </span>
                        </div>
                        <div>
                            <span className="text-[10px] uppercase font-bold text-gray-500 block">Language</span>
                            <span className="font-semibold text-gray-800 uppercase mt-0.5 block">
                                {query.language}
                            </span>
                        </div>
                        <div>
                            <span className="text-[10px] uppercase font-bold text-gray-500 block">Quality Score</span>
                            <span className="font-semibold text-gray-800 mt-0.5 block">
                                {Math.round(query.quality_score * 100)}%
                            </span>
                        </div>
                        <div>
                            <span className="text-[10px] uppercase font-bold text-gray-500 block">Logged Timestamp</span>
                            <span className="font-mono text-gray-600 mt-0.5 block">
                                {new Date(query.created_at).toLocaleDateString([], {
                                    month: "short",
                                    day: "numeric",
                                    hour: "2-digit",
                                    minute: "2-digit",
                                })}
                            </span>
                        </div>
                    </div>

                    {/* Flag Reason */}
                    <div className="bg-amber-50/70 border border-amber-200/80 p-3 rounded-lg text-amber-900">
                        <span className="font-bold text-[11px] uppercase tracking-wider block text-amber-800">
                            Reason Flagged for Expert Attention
                        </span>
                        <p className="mt-1 text-xs">{query.flag_reason}</p>
                    </div>

                    {/* Original Farmer Query */}
                    <div>
                        <span className="text-[11px] uppercase font-bold text-gray-600 block mb-1.5">
                            Original Farmer Question (Sanitized)
                        </span>
                        <div className="bg-emerald-50/50 border border-emerald-200 p-4 rounded-xl text-gray-900 font-medium text-sm leading-relaxed">
                            &ldquo;{query.query}&rdquo;
                        </div>
                        {query.canonical_text && query.canonical_text !== query.query && (
                            <p className="text-[11px] text-gray-500 mt-1 italic">
                                Canonical translation: &ldquo;{query.canonical_text}&rdquo;
                            </p>
                        )}
                    </div>

                    {/* System Generated Answer */}
                    <div>
                        <div className="flex items-center justify-between mb-1.5">
                            <span className="text-[11px] uppercase font-bold text-gray-600">
                                AI Generated Draft Answer (Under Review)
                            </span>
                            <span className="text-[10px] font-semibold text-rose-700 bg-rose-50 px-2 py-0.5 rounded border border-rose-200">
                                Unverified Draft
                            </span>
                        </div>
                        <div className="bg-gray-50 border border-gray-200 p-4 rounded-xl text-gray-700 leading-relaxed max-h-48 overflow-y-auto font-sans whitespace-pre-wrap">
                            {query.original_answer || "No response was generated (low confidence threshold triggered)."}
                        </div>
                        {query.sources && query.sources.length > 0 && (
                            <div className="mt-2 flex flex-wrap items-center gap-1.5">
                                <span className="text-[10px] font-bold text-gray-400 uppercase">Sources:</span>
                                {query.sources.map((s, i) => (
                                    <span key={i} className="text-[10px] bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                                        {s}
                                    </span>
                                ))}
                            </div>
                        )}
                    </div>

                    {/* Human Expert Correction */}
                    <div className="space-y-3 pt-2 border-t border-gray-100">
                        <div>
                            <label className="block text-[11px] uppercase font-bold text-gray-700 mb-1">
                                Corrected Agricultural Answer (Optional / Required for &apos;Corrected&apos;)
                            </label>
                            <textarea
                                rows={3}
                                value={correctedAnswer}
                                onChange={(e) => setCorrectedAnswer(e.target.value)}
                                placeholder="Enter ICAR-verified package of practices recommendation..."
                                className="w-full rounded-lg border border-gray-300 p-3 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 placeholder:text-gray-400"
                            />
                        </div>

                        <div>
                            <label className="block text-[11px] uppercase font-bold text-gray-700 mb-1">
                                Expert Reviewer Notes
                            </label>
                            <input
                                type="text"
                                value={notes}
                                onChange={(e) => setNotes(e.target.value)}
                                placeholder="e.g. Verified against ICAR tomato crop calendar; dosage adjusted."
                                className="w-full rounded-lg border border-gray-300 px-3 py-2 text-xs text-gray-900 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600 placeholder:text-gray-400"
                            />
                        </div>
                    </div>
                </div>

                {/* Footer Action Buttons */}
                <div className="bg-gray-50 px-6 py-4 border-t border-gray-200 flex flex-wrap items-center justify-between gap-3">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={isUpdating}
                        className="px-4 py-2 rounded-lg border border-gray-300 bg-white text-xs font-semibold text-gray-700 hover:bg-gray-100 transition-colors"
                    >
                        Cancel
                    </button>

                    <div className="flex flex-wrap items-center gap-2">
                        <button
                            type="button"
                            onClick={() => handleAction("rejected")}
                            disabled={isUpdating}
                            className="px-3.5 py-2 rounded-lg border border-rose-300 bg-rose-50 text-xs font-semibold text-rose-700 hover:bg-rose-100 disabled:opacity-50 transition-colors"
                        >
                            Reject Answer
                        </button>

                        <button
                            type="button"
                            onClick={() => handleAction("corrected")}
                            disabled={isUpdating}
                            className="px-3.5 py-2 rounded-lg border border-blue-300 bg-blue-50 text-xs font-semibold text-blue-700 hover:bg-blue-100 disabled:opacity-50 transition-colors"
                        >
                            Save Correction
                        </button>

                        <button
                            type="button"
                            onClick={() => handleAction("approved")}
                            disabled={isUpdating}
                            className="px-4 py-2 rounded-lg bg-emerald-700 text-xs font-semibold text-white hover:bg-emerald-800 shadow-xs disabled:opacity-50 transition-colors"
                        >
                            {isUpdating ? "Saving..." : "Approve as Verified"}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
