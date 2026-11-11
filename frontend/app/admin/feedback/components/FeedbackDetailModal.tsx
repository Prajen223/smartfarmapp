"use client";

import React, { useState } from "react";
import { FarmerFeedbackItem } from "../../types";

interface FeedbackDetailModalProps {
    feedback: FarmerFeedbackItem;
    onClose: () => void;
    onFlagForReview: (feedbackId: string, notes: string) => Promise<void>;
    isFlagging: boolean;
}

export function FeedbackDetailModal({
    feedback,
    onClose,
    onFlagForReview,
    isFlagging,
}: FeedbackDetailModalProps) {
    const [notes, setNotes] = useState("");
    const [flagSuccess, setFlagSuccess] = useState(false);
    const [showNotesInput, setShowNotesInput] = useState(false);

    const handleFlag = async () => {
        await onFlagForReview(feedback.feedback_id, notes);
        setFlagSuccess(true);
        setShowNotesInput(false);
    };

    const isNegative = feedback.rating === "negative";
    const hasReview = Boolean(feedback.review_id || feedback.review_detail);

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto bg-black/60 backdrop-blur-xs flex items-center justify-center p-4">
            <div className="relative w-full max-w-2xl rounded-2xl bg-white shadow-2xl border border-gray-100 overflow-hidden animate-fade-in">
                {/* Header */}
                <div className="px-6 py-4 bg-gradient-to-r from-emerald-800 to-green-900 text-white flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <span className="text-2xl">
                            {isNegative ? "👎" : "👍"}
                        </span>
                        <div>
                            <h2 className="text-base font-bold">Farmer Feedback Details</h2>
                            <p className="text-xs text-emerald-200">
                                ID: <span className="font-mono">{feedback.feedback_id}</span> · Session: <span className="font-mono">{feedback.session_id.slice(0, 8)}...</span>
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="rounded-lg p-1.5 text-emerald-200 hover:text-white hover:bg-emerald-700/50 transition"
                        aria-label="Close modal"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Content Body */}
                <div className="p-6 space-y-4 max-h-[75vh] overflow-y-auto text-sm text-gray-800">
                    {/* Metadata Badges */}
                    <div className="flex flex-wrap items-center gap-2 pb-2 border-b border-gray-100">
                        <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                            isNegative
                                ? "bg-rose-100 text-rose-800 border border-rose-200"
                                : "bg-emerald-100 text-emerald-800 border border-emerald-200"
                        }`}>
                            {isNegative ? "👎 Negative (Needs Review)" : "👍 Positive (Helpful)"}
                        </span>

                        <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-100 text-gray-700 border border-gray-200">
                            🌐 Language: {feedback.language.toUpperCase()}
                        </span>

                        {feedback.intent && (
                            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-200 capitalize">
                                🎯 {feedback.intent.replace(/_/g, " ")}
                            </span>
                        )}

                        <span className="text-xs text-gray-500 ml-auto">
                            📅 {new Date(feedback.created_at).toLocaleString()}
                        </span>
                    </div>

                    {/* Farmer Question */}
                    <div>
                        <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-1">
                            Farmer Question
                        </h3>
                        <div className="p-3 bg-gray-50 rounded-xl border border-gray-200 font-medium text-gray-900 leading-relaxed">
                            {feedback.query_text || "No recorded question text."}
                        </div>
                    </div>

                    {/* Assistant Response */}
                    <div>
                        <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-1">
                            Assistant Response
                        </h3>
                        <div className="p-3 bg-emerald-50/50 rounded-xl border border-emerald-100 text-gray-800 leading-relaxed max-h-48 overflow-y-auto whitespace-pre-wrap text-xs sm:text-sm">
                            {feedback.answer_text || "No recorded answer text."}
                        </div>
                    </div>

                    {/* Farmer Comment / Remarks */}
                    <div>
                        <h3 className="text-xs font-bold uppercase tracking-wider text-gray-500 mb-1">
                            Farmer Comment & Feedback Notes
                        </h3>
                        <div className={`p-3 rounded-xl border text-xs sm:text-sm ${
                            feedback.comment
                                ? "bg-amber-50/70 border-amber-200 text-amber-950 font-medium"
                                : "bg-gray-50 border-gray-200 text-gray-500 italic"
                        }`}>
                            {feedback.comment
                                ? feedback.comment
                                : "No additional written comment submitted by farmer."}
                        </div>
                        {feedback.comment && (
                            <p className="mt-1 text-[11px] text-gray-400">
                                🔒 PII Sanitized: Phone numbers, emails, and Aadhaar identifiers are scrubbed automatically.
                            </p>
                        )}
                    </div>

                    {/* Review Queue Status (if linked) */}
                    {(hasReview || flagSuccess) && (
                        <div className="p-3 rounded-xl bg-blue-50 border border-blue-200 text-blue-900 text-xs">
                            <div className="flex items-center justify-between font-bold mb-1">
                                <span className="flex items-center gap-1.5">
                                    <span>🔍</span>
                                    <span>Linked Human Review Record</span>
                                </span>
                                <span className="px-2 py-0.5 rounded bg-blue-600 text-white font-mono text-[10px]">
                                    {feedback.review_id || "Flagged"}
                                </span>
                            </div>
                            <p className="text-blue-800">
                                This feedback has been queued in the <strong>Unanswered Queries & Human Review Console</strong> for agricultural expert evaluation.
                            </p>
                            {feedback.review_detail?.reviewer_notes && (
                                <p className="mt-1 font-medium">
                                    Notes: {feedback.review_detail.reviewer_notes}
                                </p>
                            )}
                        </div>
                    )}

                    {/* Flag for Review Action */}
                    {!hasReview && !flagSuccess && (
                        <div className="pt-2">
                            {!showNotesInput ? (
                                <button
                                    type="button"
                                    onClick={() => setShowNotesInput(true)}
                                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-amber-600 hover:bg-amber-700 text-white font-bold transition shadow-xs"
                                >
                                    <span>⚠️</span>
                                    <span>Flag for Agricultural Expert Review</span>
                                </button>
                            ) : (
                                <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 space-y-2">
                                    <label className="block text-xs font-bold text-amber-950">
                                        Reviewer Notes / Guidance Context (Optional):
                                    </label>
                                    <textarea
                                        value={notes}
                                        onChange={(e) => setNotes(e.target.value)}
                                        placeholder="Add instructions for agricultural expert review..."
                                        rows={2}
                                        maxLength={500}
                                        className="w-full p-2 text-xs border border-amber-300 rounded-lg bg-white focus:outline-hidden focus:ring-2 focus:ring-amber-500"
                                    />
                                    <div className="flex justify-end gap-2">
                                        <button
                                            type="button"
                                            onClick={() => setShowNotesInput(false)}
                                            className="px-3 py-1.5 rounded-lg text-xs font-semibold text-gray-600 hover:bg-amber-100 transition"
                                        >
                                            Cancel
                                        </button>
                                        <button
                                            type="button"
                                            disabled={isFlagging}
                                            onClick={handleFlag}
                                            className="px-4 py-1.5 rounded-lg text-xs font-bold bg-amber-600 hover:bg-amber-700 text-white transition shadow-xs disabled:opacity-50"
                                        >
                                            {isFlagging ? "Flagging..." : "Confirm Flag to Review Queue"}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="px-6 py-3 bg-gray-50 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500">
                    <span>
                        Farmer ID: {feedback.farmer_id || "Anonymous Farmer"}
                    </span>
                    <button
                        onClick={onClose}
                        className="px-4 py-1.5 rounded-lg border border-gray-300 bg-white font-semibold text-gray-700 hover:bg-gray-100 transition"
                    >
                        Close
                    </button>
                </div>
            </div>
        </div>
    );
}
