"use client";

import React, { useState } from "react";
import { KnowledgeRecordItem } from "../../types";

interface DeleteConfirmModalProps {
    record: KnowledgeRecordItem | null;
    isOpen: boolean;
    onClose: () => void;
    onDeleted: () => void;
}

export function DeleteConfirmModal({
    record,
    isOpen,
    onClose,
    onDeleted,
}: DeleteConfirmModalProps) {
    const [isDeleting, setIsDeleting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    if (!isOpen || !record) return null;

    const handleDelete = async () => {
        setIsDeleting(true);
        setError(null);
        try {
            const token = localStorage.getItem("farmsaathi_admin_token");
            const res = await fetch(`/api/admin/knowledge-base/${record.doc_id}`, {
                method: "DELETE",
                headers: {
                    ...(token ? { Authorization: `Bearer ${token}` } : {}),
                },
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || "Failed to delete knowledge record.");
            }

            onDeleted();
            onClose();
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : "Error deleting record.");
        } finally {
            setIsDeleting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs">
            <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl border border-gray-100 space-y-4 animate-in fade-in zoom-in-95 duration-150 text-xs">
                <div className="w-12 h-12 rounded-full bg-rose-100 text-rose-600 flex items-center justify-center text-xl font-bold mx-auto">
                    ⚠️
                </div>

                <div className="text-center space-y-1">
                    <h3 className="text-base font-bold text-gray-900">
                        Confirm Record Deletion
                    </h3>
                    <p className="text-gray-500">
                        Are you sure you want to delete <span className="font-semibold text-gray-800">{record.title}</span> (
                        <code className="text-emerald-700">{record.doc_id}</code>)?
                    </p>
                </div>

                <div className="p-3 rounded-xl bg-rose-50/70 border border-rose-200 text-rose-900 text-[11px] space-y-1">
                    <span className="font-bold block">Vector Index Impact:</span>
                    <p>
                        This will permanently remove the record from the authoritative repository and purge all corresponding
                        embeddings from the active vector store (ChromaDB / NumPy index).
                    </p>
                </div>

                {error && (
                    <div className="p-2.5 rounded-lg bg-rose-100 text-rose-900 text-xs">
                        {error}
                    </div>
                )}

                <div className="flex items-center justify-end gap-2 pt-2">
                    <button
                        type="button"
                        onClick={onClose}
                        disabled={isDeleting}
                        className="px-4 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-100 font-semibold transition-colors disabled:opacity-50"
                    >
                        Cancel
                    </button>
                    <button
                        type="button"
                        onClick={handleDelete}
                        disabled={isDeleting}
                        className="px-4 py-2 rounded-lg bg-rose-600 text-white hover:bg-rose-700 font-semibold shadow-xs transition-colors flex items-center gap-1.5 disabled:opacity-50"
                    >
                        {isDeleting && (
                            <svg className="w-3.5 h-3.5 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                            </svg>
                        )}
                        <span>{isDeleting ? "Deleting..." : "Confirm & Delete"}</span>
                    </button>
                </div>
            </div>
        </div>
    );
}
