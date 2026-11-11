"use client";

import React, { useState } from "react";

interface ReindexModalProps {
    isOpen: boolean;
    onClose: () => void;
    onCompleted: () => void;
}

interface ReindexResult {
    records_processed: number;
    chunks_indexed: number;
    duration_ms: number;
    backend: string;
}

export function ReindexModal({
    isOpen,
    onClose,
    onCompleted,
}: ReindexModalProps) {
    const [isReindexing, setIsReindexing] = useState(false);
    const [result, setResult] = useState<ReindexResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    if (!isOpen) return null;

    const handleReindex = async () => {
        setIsReindexing(true);
        setError(null);
        setResult(null);

        try {
            const token = localStorage.getItem("farmsaathi_admin_token");
            const res = await fetch("/api/admin/knowledge-base/reindex", {
                method: "POST",
                headers: {
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || "Re-indexing operation failed.");
            }

            const data = await res.json();
            setResult(data);
            onCompleted();
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Re-indexing failed.");
        } finally {
            setIsReindexing(false);
        }
    };

    const handleClose = () => {
        setResult(null);
        setError(null);
        onClose();
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
            <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-100 space-y-4 animate-in fade-in zoom-in-95 duration-150 text-xs">
                <div className="w-12 h-12 rounded-full bg-emerald-100 text-emerald-700 flex items-center justify-center text-xl font-bold mx-auto">
                    🔄
                </div>

                <div className="text-center space-y-1">
                    <h3 className="text-base font-bold text-gray-900">
                        Re-index Vector Database
                    </h3>
                    <p className="text-gray-500">
                        Synchronize and re-embed all authoritative knowledge records into the active vector store.
                    </p>
                </div>

                {!result ? (
                    <div className="space-y-3">
                        <div className="p-3.5 rounded-xl bg-amber-50/70 border border-amber-200 text-amber-900 text-[11px] space-y-1">
                            <span className="font-bold block">⚠️ Notice:</span>
                            <p>
                                This will clear the active vector index and regenerate embeddings for all documents in the corpus.
                                The agricultural RAG pipeline will remain operational during and after synchronization.
                            </p>
                        </div>

                        {error && (
                            <div className="p-3 rounded-lg bg-rose-50 border border-rose-200 text-rose-800 text-xs">
                                {error}
                            </div>
                        )}

                        <div className="flex items-center justify-end gap-2 pt-2">
                            <button
                                type="button"
                                onClick={handleClose}
                                disabled={isReindexing}
                                className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 font-semibold transition-colors disabled:opacity-50"
                            >
                                Cancel
                            </button>
                            <button
                                type="button"
                                onClick={handleReindex}
                                disabled={isReindexing}
                                className="px-4 py-2 rounded-lg bg-emerald-700 text-white hover:bg-emerald-800 font-semibold shadow-xs transition-colors flex items-center gap-1.5 disabled:opacity-50"
                            >
                                {isReindexing && (
                                    <svg className="w-3.5 h-3.5 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                                    </svg>
                                )}
                                <span>{isReindexing ? "Re-indexing..." : "Start Full Re-index"}</span>
                            </button>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-4">
                        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-900 space-y-2">
                            <span className="font-bold text-sm block">✓ Re-indexing Completed Successfully!</span>
                            <div className="grid grid-cols-2 gap-2 text-xs pt-1 border-t border-emerald-200/80">
                                <div>
                                    <span className="text-gray-500 block text-[10px]">Records Processed:</span>
                                    <span className="font-bold">{result.records_processed}</span>
                                </div>
                                <div>
                                    <span className="text-gray-500 block text-[10px]">Chunks Indexed:</span>
                                    <span className="font-bold">{result.chunks_indexed}</span>
                                </div>
                                <div>
                                    <span className="text-gray-500 block text-[10px]">Duration:</span>
                                    <span className="font-bold">{result.duration_ms} ms</span>
                                </div>
                                <div>
                                    <span className="text-gray-500 block text-[10px]">Vector Backend:</span>
                                    <span className="font-bold font-mono text-[11px]">{result.backend}</span>
                                </div>
                            </div>
                        </div>

                        <div className="flex justify-end">
                            <button
                                type="button"
                                onClick={handleClose}
                                className="px-4 py-2 rounded-lg bg-emerald-700 text-white hover:bg-emerald-800 font-semibold text-xs transition-colors"
                            >
                                Close & Refresh
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
